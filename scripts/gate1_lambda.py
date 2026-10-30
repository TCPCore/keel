"""Gate 1: recover a known lambda from real Glimmer 30B weights.

    modal run scripts/gate1_lambda.py

No GPU and no judge: one shard is downloaded and one matrix is edited at a known lambda.
"""

from __future__ import annotations

import modal

KEY = "model.language_model.layers.24.mlp.down_proj.weight"
REPO = "meta-models/Muse-Glimmer-30B"

app = modal.App("keel-gate1")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("numpy", "huggingface_hub", "safetensors", "torch")
    .add_local_file("src/keel/invert.py", "/app/invert.py")
)


@app.function(image=image, volumes={"/hf": hf}, timeout=1800, cpu=4, memory=8192)
def run() -> str:
    import json

    import numpy as np
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open

    index_path = hf_hub_download(
        REPO, "model.safetensors.index.json", cache_dir="/hf/gate1"
    )
    index = json.load(open(index_path))
    shard = index["weight_map"][KEY]
    shard_path = hf_hub_download(REPO, shard, cache_dir="/hf/gate1")
    hf.commit()

    with safe_open(shard_path, framework="pt", device="cpu") as handle:
        weight = handle.get_tensor(KEY).float().numpy()

    import sys

    sys.path.insert(0, "/app")
    from invert import recover_lambda

    rng = np.random.default_rng(0)
    direction = rng.standard_normal(weight.shape[0]).astype(np.float32)
    direction /= np.linalg.norm(direction)

    lines = [f"weight {KEY} shape {tuple(weight.shape)}"]
    failures = 0
    for lam in (0.5, 1.0, 2.0):
        candidate = weight - lam * np.outer(direction, direction @ weight)
        known = recover_lambda(weight, candidate, direction)
        guessed = recover_lambda(weight, candidate)
        for label, out in (("known direction", known), ("delta direction", guessed)):
            error = abs(out["lambda"] - lam) / lam
            ok = error <= 0.20 and out["residual"] <= 0.30
            failures += 0 if ok else 1
            lines.append(
                f"lambda {lam:.1f} {label}: recovered {out['lambda']:.4f} "
                f"error {error:.1%} residual {out['residual']:.4f} {'PASS' if ok else 'FAIL'}"
            )
    lines.append("GATE 1 " + ("PASS" if failures == 0 else "FAIL"))
    return "\n".join(lines)


@app.local_entrypoint()
def main() -> None:
    print(run.remote())
