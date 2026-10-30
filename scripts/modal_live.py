"""Live 7B experiment for the Space: base versus ablated, on demand.

    modal deploy scripts/modal_live.py

The web app exposes POST /run, GET /status/{id} and GET /result/{id}. A run loads Qwen
2.5 7B, generates 32 panel probes and 32 harmful requests for the base, computes the
refusal direction, ablates it at every layer, and generates the same suites again.
"""

from __future__ import annotations

import json
import time
import uuid

import modal

MODEL = "Qwen/Qwen2.5-7B-Instruct"
app = modal.App("keel-live")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)
status = modal.Dict.from_name("keel-live-status", create_if_missing=True)

image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install(
        "transformers",
        "accelerate",
        "safetensors",
        "sentencepiece",
        "fastapi",
    )
    .add_local_file("src/keel/data/panel-v0.1.jsonl", "/app/panel.jsonl")
    .add_local_file(".tools/data/harmful-requests.jsonl", "/app/harmful.jsonl")
)


def _set(job: str, **fields) -> None:
    current = status.get(job, {})
    current.update(fields)
    current["updated"] = time.time()
    status[job] = current


def _load_prompts() -> tuple[list[dict], list[dict]]:
    panel = [
        json.loads(line)
        for line in open("/app/panel.jsonl", encoding="utf-8")
        if line.strip()
    ]
    harmful = [
        json.loads(line)
        for line in open("/app/harmful.jsonl", encoding="utf-8")
        if line.strip()
    ]
    return panel, harmful


@app.function(gpu="A10G", image=image, volumes={"/hf": hf, "/data": data}, timeout=2400)
def run(job: str) -> None:
    import os

    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    started = time.time()
    _set(job, state="running", phase="loading model", done=0, total=0, started=started)
    try:
        panel, harmful = _load_prompts()
        tokenizer = AutoTokenizer.from_pretrained(MODEL, cache_dir="/hf")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
        )
        model.eval()

        def generate(prompts, phase):
            rows = []
            for index, prompt in enumerate(prompts, 1):
                text = tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt["text"]}],
                    add_generation_prompt=True,
                    tokenize=False,
                )
                inputs = tokenizer(text, return_tensors="pt").to(model.device)
                with torch.no_grad():
                    out = model.generate(
                        **inputs,
                        max_new_tokens=192,
                        do_sample=False,
                        pad_token_id=tokenizer.eos_token_id,
                    )
                reply = tokenizer.decode(
                    out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
                )
                rows.append(
                    {"probe_id": prompt.get("id") or prompt.get("probe_id"), "text": reply}
                )
                _set(job, phase=phase, done=index, total=len(prompts))
            return rows

        base_panel = generate(panel, "base panel")
        base_harmful = generate(harmful, "base harmful")

        _set(job, phase="computing refusal direction", done=0, total=64)
        layers = None
        for _, module in model.named_modules():
            if module.__class__.__name__ == "ModuleList" and len(module) > 20:
                layers = module
        if layers is None:
            raise RuntimeError("no decoder layers found")
        layer = layers[len(layers) // 2]
        captured = []

        def grab(_module, _args, output):
            hidden = output[0] if isinstance(output, tuple) else output
            captured.append(hidden[:, -1, :].detach().float().mean(dim=0))

        handle = layer.register_forward_hook(grab)

        def mean(prompts):
            vectors = []
            for prompt in prompts:
                text = tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt["text"]}],
                    add_generation_prompt=True,
                    tokenize=False,
                )
                inputs = tokenizer(text, return_tensors="pt").to(model.device)
                captured.clear()
                with torch.no_grad():
                    model(**inputs)
                vectors.append(captured[-1].cpu())
            return torch.stack(vectors).mean(dim=0)

        direction = mean(harmful) - mean(panel)
        direction = (direction / direction.norm()).to(
            device=next(model.parameters()).device, dtype=torch.bfloat16
        )
        handle.remove()

        handles = []

        def ablate(_module, args):
            hidden = args[0]
            projection = (hidden * direction).sum(-1, keepdim=True) * direction
            return (hidden - projection, *args[1:])

        for _, module in model.named_modules():
            if module.__class__.__name__ == "ModuleList" and len(module) > 20:
                for layer in module:
                    handles.append(layer.register_forward_pre_hook(ablate))

        abl_panel = generate(panel, "ablated panel")
        abl_harmful = generate(harmful, "ablated harmful")
        for handle in handles:
            handle.remove()

        result = {
            "base_panel": base_panel,
            "base_harmful": base_harmful,
            "ablated_panel": abl_panel,
            "ablated_harmful": abl_harmful,
            "model": MODEL,
            "layers": len(layers),
            "seconds": round(time.time() - started, 1),
        }
        path = f"/data/live/{job}.json"
        os.makedirs("/data/live", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle_out:
            json.dump(result, handle_out)
        data.commit()
        _set(job, state="done", phase="done", done=64, total=64, path=path)
    except Exception as exc:  # noqa: BLE001
        import traceback

        _set(
            job,
            state="failed",
            phase="failed",
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-700:]}",
        )


@app.function(image=image, volumes={"/data": data})
def read_result(job: str) -> dict:
    path = status.get(job, {}).get("path")
    if not path:
        return {}
    return json.loads(open(path, encoding="utf-8").read())


@app.function(image=image)
@modal.asgi_app()
def api():
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware

    web = FastAPI()
    web.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @web.post("/run")
    def start() -> dict:
        job = uuid.uuid4().hex[:12]
        status[job] = {
            "state": "queued",
            "phase": "queued",
            "done": 0,
            "total": 0,
            "created": time.time(),
        }
        run.spawn(job)
        return {"id": job}

    @web.get("/status/{job}")
    def get_status(job: str) -> dict:
        entry = status.get(job)
        if not entry:
            raise HTTPException(404, "unknown job")
        return entry

    @web.get("/result/{job}")
    def get_result(job: str) -> dict:
        entry = status.get(job)
        if not entry:
            raise HTTPException(404, "unknown job")
        if entry.get("state") != "done":
            raise HTTPException(409, "not finished")
        return read_result.remote(job)

    @web.get("/healthz")
    def health() -> dict:
        return {"ok": True}

    return web
