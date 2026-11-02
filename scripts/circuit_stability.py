"""Base-against-base extraction stability: the null the first run lacked."""

from __future__ import annotations

import json

import modal

BASE = "meta-models/Muse-Glimmer-30B"
app = modal.App("keel-circuit-stability")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)
image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install(
        "transformers==5.15.0", "accelerate", "safetensors", "sentencepiece",
        "huggingface_hub", "numpy",
    )
    .add_local_file(".tools/data/harmful-requests.jsonl", "/app/harmful.jsonl")
    .add_local_file("src/keel/data/panel-v0.1.jsonl", "/app/panel.jsonl")
)


def _load():
    import os

    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(BASE, cache_dir="/hf")
    model = AutoModelForImageTextToText.from_pretrained(
        BASE, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
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


def _capture(model, tokenizer, prompts):
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
    return outs


def _circuit(model, tokenizer, harmful, benign):
    import torch

    h_outs = _capture(model, tokenizer, harmful)
    b_outs = _capture(model, tokenizer, benign)
    hs = {i: torch.stack(v) for i, v in h_outs.items()}
    bs = {i: torch.stack(v) for i, v in b_outs.items()}
    mu_h = {i: hs[i].mean(0) for i in hs}
    mu_b = {i: bs[i].mean(0) for i in bs}
    var_h = {i: hs[i].var(0, unbiased=True) for i in hs}
    var_b = {i: bs[i].var(0, unbiased=True) for i in bs}
    n_h, n_b = len(harmful), len(benign)
    pooled = {
        i: (((n_h - 1) * var_h[i] + (n_b - 1) * var_b[i]) / (n_h + n_b - 2)).sqrt()
        for i in hs
    }
    scores = {i: (mu_h[i] - mu_b[i]) / torch.clamp(pooled[i], min=1e-3) for i in mu_h}
    flat = torch.cat([scores[i] for i in sorted(scores)])
    k = max(1, round(0.001 * flat.numel()))
    idx = torch.topk(flat.abs(), k).indices.cpu().numpy()
    offset = 0
    neurons = set()
    for i in sorted(scores):
        n = scores[i].numel()
        for j in idx[(idx >= offset) & (idx < offset + n)]:
            neurons.add((i, int(j - offset)))
        offset += n
    return neurons, k


def _jaccard(a, b):
    return len(a & b) / len(a | b)


@app.function(gpu="A100-80GB", volumes={"/hf": hf, "/data": data}, image=image, timeout=3600)
def run() -> str:
    import torch

    harmful = [json.loads(line)["text"] for line in open("/app/harmful.jsonl") if line.strip()]
    benign = [json.loads(line)["text"] for line in open("/app/panel.jsonl") if line.strip()]

    import numpy as np

    model, tok = _load()
    a, k = _circuit(model, tok, harmful[:16], benign[:16])
    b, _ = _circuit(model, tok, harmful[16:], benign[16:])
    full, _ = _circuit(model, tok, harmful, benign)

    rng = np.random.default_rng(7)
    bh1 = [harmful[i] for i in rng.integers(0, len(harmful), len(harmful))]
    bb1 = [benign[i] for i in rng.integers(0, len(benign), len(benign))]
    bh2 = [harmful[i] for i in rng.integers(0, len(harmful), len(harmful))]
    bb2 = [benign[i] for i in rng.integers(0, len(benign), len(benign))]
    boot1, _ = _circuit(model, tok, bh1, bb1)
    boot2, _ = _circuit(model, tok, bh2, bb2)
    del model
    torch.cuda.empty_cache()

    result = {
        "k": k,
        "jaccard_a_b": round(_jaccard(a, b), 4),
        "jaccard_a_full": round(_jaccard(a, full), 4),
        "jaccard_b_full": round(_jaccard(b, full), 4),
        "jaccard_boot1_boot2": round(_jaccard(boot1, boot2), 4),
        "jaccard_boot1_full": round(_jaccard(boot1, full), 4),
        "jaccard_boot2_full": round(_jaccard(boot2, full), 4),
        "sizes": {"a": len(a), "b": len(b), "full": len(full),
                  "boot1": len(boot1), "boot2": len(boot2)},
        "derivative_vs_full_reference": 0.5231,
    }
    with open("/data/circuit-stability.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    data.commit()
    return json.dumps(result)


@app.local_entrypoint()
def main() -> None:
    print(run.remote())
