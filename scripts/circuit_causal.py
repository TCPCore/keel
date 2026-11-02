"""Forward/causal test: ablate the candidate's stable circuit and measure compliance."""

from __future__ import annotations

import json

import modal

BASE = "meta-models/Muse-Glimmer-30B"
CANDIDATE = "darkc0de/Muse-Glimmer-30B-heretic"
app = modal.App("keel-circuit-causal")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)
image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install(
        "transformers==5.15.0", "accelerate", "safetensors", "sentencepiece",
        "huggingface_hub", "numpy",
    )
    .add_local_file(".tools/data/harmful-128.jsonl", "/app/harmful.jsonl")
    .add_local_file(".tools/data/benign-128.jsonl", "/app/benign.jsonl")
    .add_local_file(".tools/data/harmful-requests.jsonl", "/app/harmful32.jsonl")
)


def _load(model_id):
    import os

    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(BASE, cache_dir="/hf")
    model = AutoModelForImageTextToText.from_pretrained(
        model_id, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
    )
    model.eval()
    return model, tok


def _layers(model):
    for _, module in model.named_modules():
        if module.__class__.__name__ != "ModuleList" or len(module) < 20:
            continue
        first = module[0]
        if hasattr(first, "self_attn") and hasattr(getattr(first, "mlp", None), "down_proj"):
            return list(module)
    raise RuntimeError("decoder layer list not found")


def _capture_all(model, tokenizer, prompts):
    import torch

    layers = _layers(model)
    captured: dict[int, object] = {}
    handles = []

    def make(i):
        def hook(_module, args):
            captured[i] = args[0][:, -1, :].detach().float()

        return hook

    for i, layer in enumerate(layers):
        handles.append(layer.mlp.down_proj.register_forward_pre_hook(make(i)))
    outs = {i: [] for i in range(len(layers))}
    try:
        for prompt in prompts:
            text = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                add_generation_prompt=True, tokenize=False,
            )
            inputs = tokenizer(text, return_tensors="pt").to(model.device)
            with torch.no_grad():
                model(**inputs)
            for i in range(len(layers)):
                outs[i].append(captured[i][0].cpu())
    finally:
        for h in handles:
            h.remove()
    return {i: torch.stack(v) for i, v in outs.items()}


def _stable_circuit(harm, ben, n_boot=10, freq=0.8, seed=0):
    import numpy as np
    import torch

    rng = np.random.default_rng(seed)
    layers = sorted(harm)
    total = sum(harm[i].shape[1] for i in layers)
    k = max(1, round(0.001 * total))
    counts: dict[tuple[int, int], int] = {}
    for _ in range(n_boot):
        hi = rng.integers(0, harm[layers[0]].shape[0], harm[layers[0]].shape[0])
        bi = rng.integers(0, ben[layers[0]].shape[0], ben[layers[0]].shape[0])
        flat = []
        for i in layers:
            h = harm[i][torch.tensor(hi)]
            b = ben[i][torch.tensor(bi)]
            mu_h, mu_b = h.mean(0), b.mean(0)
            var_h, var_b = h.var(0, unbiased=True), b.var(0, unbiased=True)
            n = h.shape[0]
            pooled = (((n - 1) * var_h + (n - 1) * var_b) / (2 * n - 2)).sqrt()
            flat.append((mu_h - mu_b) / torch.clamp(pooled, min=1e-3))
        flat = torch.cat(flat)
        idx = torch.topk(flat.abs(), k).indices.cpu().numpy()
        offset = 0
        for i in layers:
            width = harm[i].shape[1]
            for j in idx[(idx >= offset) & (idx < offset + width)]:
                key = (i, int(j - offset))
                counts[key] = counts.get(key, 0) + 1
            offset += width
    stable = {key for key, c in counts.items() if c >= freq * n_boot}
    return stable, k


def _generate(model, tokenizer, prompts, zero_map=None):
    import torch

    layers = _layers(model)
    handles = []
    if zero_map:
        for i, idx in zero_map.items():
            def make(layer_idx, indices):
                def hook(_module, args):
                    args[0][..., torch.tensor(indices, device=args[0].device)] = 0.0

                return hook

            handles.append(layers[i].mlp.down_proj.register_forward_pre_hook(make(i, idx)))
    rows = []
    try:
        for prompt in prompts:
            text = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                add_generation_prompt=True, tokenize=False, reasoning_strength="low",
            )
            inputs = tokenizer(text, return_tensors="pt").to(model.device)
            with torch.no_grad():
                out = model.generate(
                    **inputs, max_new_tokens=192, do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            rows.append(tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True))
    finally:
        for h in handles:
            h.remove()
    return rows


def _by_layer(stable):
    out: dict[int, list[int]] = {}
    for layer, idx in stable:
        out.setdefault(layer, []).append(idx)
    return out


@app.function(gpu="A100-80GB", volumes={"/hf": hf, "/data": data}, image=image, timeout=7200)
def run() -> str:
    import torch

    harmful = [json.loads(line)["text"] for line in open("/app/harmful.jsonl") if line.strip()]
    benign = [json.loads(line)["text"] for line in open("/app/benign.jsonl") if line.strip()]
    probes = [json.loads(line) for line in open("/app/harmful32.jsonl") if line.strip()]

    model, tok = _load(CANDIDATE)
    harm = _capture_all(model, tok, harmful)
    ben = _capture_all(model, tok, benign)
    stable, k = _stable_circuit(harm, ben)
    zero = _by_layer(stable)

    prompts = [p["text"] for p in probes]
    baseline = _generate(model, tok, prompts, None)
    ablated = _generate(model, tok, prompts, zero)
    rng = torch.Generator().manual_seed(0)
    all_neurons = [(layer, idx) for layer in zero for idx in zero[layer]]
    random_set = set()
    import random

    random.seed(0)
    # random control of the same size, drawn from the same layers
    for layer, idxs in zero.items():
        pick = random.sample(range(harm[layer].shape[1]), len(idxs))
        for j in pick:
            random_set.add((layer, j))
    random_zero = _by_layer(random_set)
    control = _generate(model, tok, prompts, random_zero)
    del model
    torch.cuda.empty_cache()

    out = []
    for p, b, a, c in zip(probes, baseline, ablated, control, strict=True):
        out.append({"probe_id": p["probe_id"], "baseline": b, "ablated": a, "random": c})
    with open("/data/circuit-causal.jsonl", "w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row) + "\n")
    data.commit()
    return json.dumps({"k": k, "stable": len(stable), "rows": len(out)})


@app.local_entrypoint()
def main() -> None:
    print(run.remote())
