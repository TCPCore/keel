"""Gate 3: replay derivative C by recovering its per-module lambda.

    modal run scripts/replay_lambda.py

Streams the derivative's shards, recovers lambda for every o_proj and down_proj against the
base, applies the recovered rank-one edit to the base in GPU memory, and generates the
harmful suite. Writes the profile and the responses to the data volume.
"""

from __future__ import annotations

import json
import pathlib

import modal

BASE = "meta-models/Muse-Glimmer-30B"
CANDIDATE = "darkc0de/Muse-Glimmer-30B-heretic"
ROOT = pathlib.Path(__file__).resolve().parents[1]

app = modal.App("keel-replay-lambda")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)

image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install(
        "transformers==5.15.0", "accelerate", "safetensors", "sentencepiece", "huggingface_hub"
    )
    .add_local_file("src/keel/invert.py", "/app/invert.py")
    .add_local_file(".tools/data/harmful-requests.jsonl", "/app/harmful.jsonl")
)


def _top_direction(delta, iters=30):
    import torch

    vector = torch.randn(delta.shape[0], device=delta.device, dtype=torch.float32)
    vector /= vector.norm()
    for _ in range(iters):
        vector = delta @ (delta.T @ vector)
        vector /= vector.norm()
    return vector


@app.function(gpu="A100-80GB", image=image, volumes={"/hf": hf, "/data": data}, timeout=5400)
def run() -> str:
    import os
    import sys

    os.environ["HF_HOME"] = "/hf"
    sys.path.insert(0, "/app")
    import torch
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    model = AutoModelForImageTextToText.from_pretrained(
        BASE, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
    )
    model.eval()
    params = dict(model.named_parameters())

    targets = [
        name
        for name in params
        if name.endswith((".self_attn.o_proj.weight", ".mlp.down_proj.weight"))
    ]
    index = json.load(
        open(hf_hub_download(CANDIDATE, "model.safetensors.index.json", cache_dir="/hf"))
    )
    shards: dict[str, object] = {}
    profile = {}
    for index_no, name in enumerate(targets, 1):
        shard_name = index["weight_map"][name]
        path = hf_hub_download(CANDIDATE, shard_name, cache_dir="/hf")
        if path not in shards:
            shards[path] = safe_open(path, framework="pt", device="cpu")
        candidate = shards[path].get_tensor(name).to("cuda")
        base = params[name].detach().float()
        delta = candidate.float() - base
        vector = _top_direction(delta)
        row = vector @ base
        outer = torch.outer(vector, row)
        lam = -float((delta * outer).sum() / (outer * outer).sum())
        residual = float((delta + lam * outer).norm() / max(delta.norm(), 1e-9))
        with torch.no_grad():
            params[name].copy_((base - lam * outer).to(params[name].dtype))
        profile[name] = {"lambda": round(lam, 5), "residual": round(residual, 4)}
        if index_no % 12 == 0:
            print(f"{index_no}/{len(targets)} modules edited", flush=True)

    hf.commit()
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

    tokenizer = AutoTokenizer.from_pretrained(BASE, cache_dir="/hf")
    prompts = [
        json.loads(line)
        for line in open("/app/harmful.jsonl", encoding="utf-8")
        if line.strip()
    ]
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
        reply = tokenizer.decode(
            out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )
        rows.append({"probe_id": prompt["probe_id"], "text": reply})
        if i % 8 == 0:
            print(f"{i}/{len(prompts)} generated", flush=True)

    with open("/data/responses-replay-lambda-harmful.jsonl", "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    with open("/data/replay-lambda-profile.json", "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "modules": profile}, handle, indent=1)
    data.commit()
    return json.dumps(summary)


@app.local_entrypoint()
def main() -> None:
    print(run.remote())
