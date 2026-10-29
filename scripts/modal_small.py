"""Third-family control: a small non-Meta model, base and ablated.

    modal run scripts/modal_small.py

Generates panel and harmful responses for the base, computes the refusal direction from
harmful against benign at a middle layer, ablates it, and generates the same suites for
the ablated model. Four runs, one job.
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

MODEL = "Qwen/Qwen2.5-7B-Instruct"
ROOT = Path(__file__).resolve().parents[1]

app = modal.App("keel-small")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)

image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install("transformers", "accelerate", "safetensors", "sentencepiece")
)


def _generate(model, tokenizer, prompts, tag):
    import torch

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
        reply = tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        rows.append({"probe_id": prompt["id"], "text": reply})
        print(f"{tag} {index}/{len(prompts)}", flush=True)
    return rows


def _direction(model, tokenizer, harmful, benign):
    import torch

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

    direction = mean(harmful) - mean(benign)
    handle.remove()
    return direction / direction.norm()


@app.function(gpu="A10G", image=image, volumes={"/hf": hf, "/data": data}, timeout=5400)
def run(panel: list[dict], harmful: list[dict]) -> dict:
    import os

    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL, cache_dir="/hf")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
    )
    model.eval()

    def save(name: str, rows: list[dict]) -> None:
        path = f"/data/responses-{name}.jsonl"
        with open(path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        data.commit()
        print("wrote", path, flush=True)

    base_panel = _generate(model, tokenizer, panel, "base-panel")
    save("qwen-base-panel", base_panel)
    base_harmful = _generate(model, tokenizer, harmful, "base-harmful")
    save("qwen-base-harmful", base_harmful)

    direction = _direction(model, tokenizer, harmful, panel).to(
        device=next(model.parameters()).device, dtype=torch.bfloat16
    )
    handles = []

    def ablate(_module, args):
        hidden = args[0]
        projection = (hidden * direction).sum(-1, keepdim=True) * direction
        return (hidden - projection, *args[1:])

    for _, module in model.named_modules():
        if module.__class__.__name__ == "ModuleList" and len(module) > 20:
            for layer in module:
                handles.append(layer.register_forward_pre_hook(ablate))
    print(f"ablating at {len(handles)} layers", flush=True)

    abl_panel = _generate(model, tokenizer, panel, "abl-panel")
    save("qwen-abl-panel", abl_panel)
    abl_harmful = _generate(model, tokenizer, harmful, "abl-harmful")
    save("qwen-abl-harmful", abl_harmful)
    for handle in handles:
        handle.remove()
    return {"layers": len(handles)}


@app.local_entrypoint()
def main() -> None:
    panel = [
        json.loads(line)
        for line in (ROOT / "src/keel/data/panel-v0.1.jsonl").read_text().splitlines()
        if line.strip()
    ]
    harmful = [
        {"id": row["probe_id"], "text": row["text"]}
        for row in (
            json.loads(line)
            for line in (ROOT / ".tools/data/harmful-requests.jsonl").read_text().splitlines()
            if line.strip()
        )
    ]
    print(run.remote(panel, harmful))
