"""Stability-aware circuit extraction (bootstrap selection) and comparison."""

from __future__ import annotations

import json

import modal

BASE = "meta-models/Muse-Glimmer-30B"
CANDIDATE = "darkc0de/Muse-Glimmer-30B-heretic"
app = modal.App("keel-circuit-stable")
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
)

SIGNATURE = [
    "Explain how a bicycle brake works.", "Write a short poem about the sea.",
    "What is the capital of Portugal?", "Give me three tips for better sleep.",
    "Explain what a prime number is.", "Describe the water cycle for a child.",
    "How do I bake bread at home?", "What causes the seasons?",
    "Explain how a refrigerator keeps food cold.", "Write a sentence about autumn leaves.",
    "What is the difference between a frog and a toad?", "How does a compass point north?",
    "Give an example of a metaphor.", "Explain the rules of chess in one paragraph.",
    "What is the boiling point of water at sea level?", "Describe a healthy breakfast.",
]


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
    return {i: torch.stack(v) for i, v in outs.items()}, len(layers)


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
    freqs = sorted(counts.values(), reverse=True)
    return stable, k, (np.mean(freqs[:k]) if freqs else 0.0)


def _signature_matrix(model, tokenizer, prompts, neurons):
    import torch

    outs, _ = _capture_all(model, tokenizer, prompts)
    pairs = sorted(neurons)
    mat = torch.stack([outs[layer][:, idx] for layer, idx in pairs], dim=1)
    return mat  # [n_prompts, n_neurons]


def _zcos(a, b):
    import numpy as np

    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    a = (a - a.mean(0)) / (a.std(0) + 1e-9)
    b = (b - b.mean(0)) / (b.std(0) + 1e-9)
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-12))


@app.function(gpu="A100-80GB", volumes={"/hf": hf, "/data": data}, image=image, timeout=7200)
def run() -> str:
    import torch

    harmful = [json.loads(line)["text"] for line in open("/app/harmful.jsonl") if line.strip()]
    benign = [json.loads(line)["text"] for line in open("/app/benign.jsonl") if line.strip()]

    model, tok = _load(BASE)
    harm, _ = _capture_all(model, tok, harmful)
    ben, _ = _capture_all(model, tok, benign)
    base_stable, k, mean_freq = _stable_circuit(harm, ben)
    del model
    torch.cuda.empty_cache()

    model, tok = _load(CANDIDATE)
    harm_c, _ = _capture_all(model, tok, harmful)
    ben_c, _ = _capture_all(model, tok, benign)
    cand_stable, _, _ = _stable_circuit(harm_c, ben_c)
    del model
    torch.cuda.empty_cache()

    union = sorted(base_stable | cand_stable)
    model, tok = _load(BASE)
    bm = _signature_matrix(model, tok, SIGNATURE, union)
    del model
    torch.cuda.empty_cache()
    model, tok = _load(CANDIDATE)
    cm = _signature_matrix(model, tok, SIGNATURE, union)
    del model
    torch.cuda.empty_cache()

    jaccard = len(base_stable & cand_stable) / max(1, len(base_stable | cand_stable))
    zc = _zcos(bm.numpy(), cm.numpy())
    result = {
        "k": k,
        "base_stable": len(base_stable),
        "cand_stable": len(cand_stable),
        "union": len(union),
        "jaccard": round(jaccard, 4),
        "z_cosine": round(zc, 4),
        "base_mean_frequency_topk": round(float(mean_freq), 2),
    }
    with open("/data/circuit-stable-result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    data.commit()
    return json.dumps(result)


@app.local_entrypoint()
def main() -> None:
    print(run.remote())
