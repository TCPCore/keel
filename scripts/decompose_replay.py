"""Decomposition replay: apply P, L or P+L to the base and generate.

    modal run scripts/decompose_replay.py --variant P
"""

from __future__ import annotations

import json
import math

import modal

BASE = "meta-models/Muse-Glimmer-30B"
CANDIDATE = "darkc0de/Muse-Glimmer-30B-heretic"
app = modal.App("keel-decompose")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)
image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install(
        "transformers==5.15.0", "accelerate", "safetensors", "sentencepiece", "huggingface_hub"
    )
    .add_local_file(".tools/data/harmful-requests.jsonl", "/app/harmful.jsonl")
)


@app.function(gpu="A100-80GB", image=image, volumes={"/hf": hf, "/data": data}, timeout=7200)
def run(variant: str) -> str:
    import os

    os.environ["HF_HOME"] = "/hf"
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
    resid_norms = []
    skipped = 0
    for i, name in enumerate(targets, 1):
        shard = index["weight_map"][name]
        path = hf_hub_download(CANDIDATE, shard, cache_dir="/hf")
        if path not in shards:
            shards[path] = safe_open(path, framework="pt", device="cpu")
        candidate = shards[path].get_tensor(name).to("cuda")
        base = params[name].detach().float()
        delta = candidate.float() - base
        vector = torch.randn(delta.shape[0], device="cuda")
        vector /= vector.norm()
        for _ in range(30):
            vector = delta @ (delta.T @ vector)
            vector /= vector.norm()
        outer = torch.outer(vector, vector @ base)
        denominator = float((outer * outer).sum())
        lam = -float((delta * outer).sum() / denominator) if denominator > 0 else float("nan")
        if not math.isfinite(lam) or abs(lam) > 10:
            skipped += 1
            continue
        projection = -lam * outer
        residual = delta - projection
        if not torch.isfinite(projection).all() or not torch.isfinite(residual).all():
            skipped += 1
            continue
        resid_norms.append(float(residual.norm() / max(delta.norm(), 1e-9)))
        with torch.no_grad():
            if variant == "P":
                params[name].copy_((base + projection).to(params[name].dtype))
            elif variant == "L":
                params[name].copy_((base + residual).to(params[name].dtype))
            else:
                params[name].copy_((base + projection + residual).to(params[name].dtype))
        if i % 24 == 0:
            print(f"{variant} {i}/{len(targets)}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(BASE, cache_dir="/hf")
    prompts = [
        json.loads(line) for line in open("/app/harmful.jsonl") if line.strip()
    ]
    rows = []
    for i, prompt in enumerate(prompts, 1):
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt["text"]}],
            add_generation_prompt=True,
            tokenize=False,
            reasoning_strength="low",
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
            print(f"{variant} generated {i}/{len(prompts)}", flush=True)

    path = f"/data/responses-decomp-{variant}.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    summary = {
        "variant": variant,
        "modules": len(targets),
        "residual_median": round(sorted(resid_norms)[len(resid_norms) // 2], 4)
        if resid_norms
        else None,
        "skipped_modules": skipped,
    }
    with open(f"/data/decomp-{variant}-summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    data.commit()
    return json.dumps(summary)


@app.local_entrypoint()
def main(variant: str = "P") -> None:
    print(run.remote(variant))
