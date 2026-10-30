"""Gate 3 revised: build an M1 weight-edit, recover lambda, replay it.

    modal run scripts/replay_m1.py

Step 1 builds the pure directional weight edit at intensity 1.0, recovers lambda for every
o_proj and down_proj, writes the profile, and generates the target suite.
Step 2 reloads the base, applies the recovered profile, and generates the replay suite.
"""

from __future__ import annotations

import json
import pathlib

import modal

BASE = "meta-models/Muse-Glimmer-30B"
ROOT = pathlib.Path(__file__).resolve().parents[1]

app = modal.App("keel-replay-m1")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)
image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install(
        "transformers==5.15.0", "accelerate", "safetensors", "sentencepiece", "huggingface_hub"
    )
    .add_local_file(".tools/data/harmful-requests.jsonl", "/app/harmful.jsonl")
    .add_local_file("src/keel/data/panel-v0.1.jsonl", "/app/panel.jsonl")
    .add_local_file("src/keel/invert.py", "/app/invert.py")
)


def _load():
    import os

    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(BASE, cache_dir="/hf")
    model = AutoModelForImageTextToText.from_pretrained(
        BASE, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
    )
    model.eval()
    return model, tokenizer


def _direction(model, tokenizer) -> object:
    import torch

    panel = [json.loads(line) for line in open("/app/panel.jsonl") if line.strip()]
    harmful = [json.loads(line) for line in open("/app/harmful.jsonl") if line.strip()]
    layers = None
    for _, module in model.named_modules():
        if module.__class__.__name__ == "ModuleList" and len(module) > 20:
            layers = module
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

    vector = mean(harmful) - mean(panel)
    handle.remove()
    vector = vector / vector.norm()
    return vector.to(device=next(model.parameters()).device, dtype=torch.bfloat16)


def _generate(model, tokenizer, tag: str) -> list[dict]:
    import torch

    prompts = [json.loads(line) for line in open("/app/harmful.jsonl") if line.strip()]
    rows = []
    for i, prompt in enumerate(prompts, 1):
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
        rows.append({"probe_id": prompt["probe_id"], "text": reply})
        if i % 8 == 0:
            print(f"{tag} {i}/{len(prompts)}", flush=True)
    return rows


def _targets(model) -> list[tuple[str, object]]:
    return [
        (name, param)
        for name, param in model.named_parameters()
        if name.endswith((".self_attn.o_proj.weight", ".mlp.down_proj.weight"))
    ]


@app.function(gpu="A100-80GB", image=image, volumes={"/hf": hf, "/data": data}, timeout=7200)
def build() -> str:
    import torch

    model, tokenizer = _load()
    vector = _direction(model, tokenizer)
    targets = _targets(model)
    profile = {}
    for name, param in targets:
        with torch.no_grad():
            weight = param.detach().float()
            outer = torch.outer(vector.float(), vector.float() @ weight)
            param.copy_((weight - outer).to(param.dtype))
            profile[name] = {"lambda": 1.0, "direction": vector.float().cpu()}
    data.commit()
    rows = _generate(model, tokenizer, "target")
    with open("/data/responses-m1-weight-target.jsonl", "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    torch.save(profile, "/data/m1-weight-direction.pt")
    data.commit()
    print("built and generated target:", len(rows), flush=True)
    return json.dumps({"modules": len(targets), "target_rows": len(rows)})


@app.function(gpu="A100-80GB", image=image, volumes={"/hf": hf, "/data": data}, timeout=7200)
def recover_and_replay() -> str:
    import sys

    sys.path.insert(0, "/app")
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open

    model, tokenizer = _load()
    targets = dict(_targets(model))
    index = json.load(open(hf_hub_download(BASE, "model.safetensors.index.json", cache_dir="/hf")))
    shards: dict[str, object] = {}
    profile = {}
    recovered = {}
    for name in targets:
        shard = index["weight_map"][name]
        path = hf_hub_download(BASE, shard, cache_dir="/hf")
        if path not in shards:
            shards[path] = safe_open(path, framework="pt", device="cpu")
        base = shards[path].get_tensor(name).float().to("cuda")
        edited = targets[name].detach().float()
        delta = edited - base
        vector = torch.randn(delta.shape[0], device="cuda")
        vector /= vector.norm()
        for _ in range(30):
            vector = delta @ (delta.T @ vector)
            vector /= vector.norm()
        row = vector @ base
        outer = torch.outer(vector, row)
        lam = -float((delta * outer).sum() / (outer * outer).sum())
        residual = float((delta + lam * outer).norm() / max(delta.norm(), 1e-9))
        profile[name] = {"lambda": round(lam, 5), "residual": round(residual, 4)}
        recovered[name] = (vector.cpu(), lam)
    lambdas = [v["lambda"] for v in profile.values()]
    residuals = [v["residual"] for v in profile.values()]
    summary = {
        "modules": len(profile),
        "lambda_median": round(sorted(lambdas)[len(lambdas) // 2], 4),
        "lambda_min": round(min(lambdas), 4),
        "lambda_max": round(max(lambdas), 4),
        "residual_median": round(sorted(residuals)[len(residuals) // 2], 4),
        "clean_under_0.30": sum(1 for r in residuals if r <= 0.30),
    }
    print(summary, flush=True)
    del model
    torch.cuda.empty_cache()

    model, tokenizer = _load()
    params = dict(model.named_parameters())
    for name, (vector, lam) in recovered.items():
        with torch.no_grad():
            weight = params[name].detach().float()
            outer = torch.outer(vector.to("cuda").float(), (vector.to("cuda").float() @ weight))
            params[name].copy_((weight - lam * outer).to(params[name].dtype))
    rows = _generate(model, tokenizer, "replay")
    with open("/data/responses-m1-weight-replay.jsonl", "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    with open("/data/m1-replay-profile.json", "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "modules": profile}, handle, indent=1)
    data.commit()
    return json.dumps(summary)


@app.local_entrypoint()
def main() -> None:
    print(build.remote())
    print(recover_and_replay.remote())
