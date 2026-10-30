"""Confirm P+L reconstructs candidate weights, and measure the bf16 rounding."""

from __future__ import annotations

import modal

BASE = "meta-models/Muse-Glimmer-30B"
CANDIDATE = "darkc0de/Muse-Glimmer-30B-heretic"
KEYS = [
    "model.language_model.layers.24.mlp.down_proj.weight",
    "model.language_model.layers.24.self_attn.o_proj.weight",
    "model.language_model.layers.7.mlp.down_proj.weight",
]
app = modal.App("keel-check-weights")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "torch", "safetensors", "huggingface_hub"
)


@app.function(image=image, volumes={"/hf": hf}, timeout=1200, cpu=4, memory=8192)
def run() -> str:
    import json

    import torch
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open

    base_index = json.load(
        open(hf_hub_download(BASE, "model.safetensors.index.json", cache_dir="/hf"))
    )
    cand_index = json.load(
        open(hf_hub_download(CANDIDATE, "model.safetensors.index.json", cache_dir="/hf"))
    )
    lines = []
    for name in KEYS:
        bp = hf_hub_download(BASE, base_index["weight_map"][name], cache_dir="/hf")
        cp = hf_hub_download(CANDIDATE, cand_index["weight_map"][name], cache_dir="/hf")
        with safe_open(bp, framework="pt", device="cpu") as bf, safe_open(
            cp, framework="pt", device="cpu"
        ) as cf:
            base = bf.get_tensor(name).float()
            cand = cf.get_tensor(name).float()
        delta = cand - base
        vector = torch.randn(delta.shape[0])
        vector /= vector.norm()
        for _ in range(30):
            vector = delta @ (delta.T @ vector)
            vector /= vector.norm()
        outer = torch.outer(vector, vector @ base)
        lam = -float((delta * outer).sum() / (outer * outer).sum())
        projection = -lam * outer
        residual = delta - projection
        rebuilt_fp32 = base + projection + residual
        rebuilt_bf16 = rebuilt_fp32.to(torch.bfloat16)
        diff = (rebuilt_bf16.float() - cand).abs()
        lines.append(
            f"{name.rsplit('.', 1)[0]}: fp32 max {float((rebuilt_fp32 - cand).abs().max()):.2e} "
            f"bf16 max {float(diff.max()):.2e} mean {float(diff.mean()):.2e} lam {lam:.4f}"
        )
    return "\n".join(lines)


@app.local_entrypoint()
def main() -> None:
    print(run.remote())
