"""How much of the derivative delta lives in the modules we model?

    modal run scripts/coverage.py

Streams both checkpoints and sums ||candidate - base|| per parameter suffix.
"""

from __future__ import annotations

import modal

BASE = "meta-models/Muse-Glimmer-30B"
CANDIDATE = "darkc0de/Muse-Glimmer-30B-heretic"
app = modal.App("keel-coverage")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "numpy", "safetensors", "huggingface_hub", "torch"
)


@app.function(image=image, volumes={"/hf": hf}, timeout=3600, cpu=8, memory=16384)
def run() -> str:
    import json
    from collections import defaultdict

    import numpy as np
    from huggingface_hub import hf_hub_download
    from safetensors import safe_open

    base_index = json.load(
        open(hf_hub_download(BASE, "model.safetensors.index.json", cache_dir="/hf"))
    )
    cand_index = json.load(
        open(hf_hub_download(CANDIDATE, "model.safetensors.index.json", cache_dir="/hf"))
    )
    totals = defaultdict(float)
    counts = defaultdict(int)
    total = 0.0
    opened: dict[str, object] = {}
    for i, (name, shard) in enumerate(cand_index["weight_map"].items(), 1):
        if name not in base_index["weight_map"]:
            continue
        cand_shard = shard
        base_shard = base_index["weight_map"][name]
        cp = hf_hub_download(CANDIDATE, cand_shard, cache_dir="/hf")
        bp = hf_hub_download(BASE, base_shard, cache_dir="/hf")
        if cp not in opened:
            opened[cp] = safe_open(cp, framework="pt", device="cpu")
        if bp not in opened:
            opened[bp] = safe_open(bp, framework="pt", device="cpu")
        try:
            c = opened[cp].get_tensor(name).float().numpy()
            b = opened[bp].get_tensor(name).float().numpy()
        except Exception:
            continue
        if c.shape != b.shape:
            continue
        norm = float(np.linalg.norm(c - b))
        suffix = ".".join(name.split(".")[-2:])
        totals[suffix] += norm
        counts[suffix] += 1
        total += norm
        if i % 200 == 0:
            print(i, flush=True)

    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    modelled = sum(v for k, v in totals.items() if k in ("o_proj.weight", "down_proj.weight"))
    out = {
        "total_delta_norm": round(total, 2),
        "modelled_delta_norm": round(modelled, 2),
        "modelled_share": round(modelled / total, 4) if total else 0,
        "by_suffix": {k: {"norm": round(v, 2), "count": counts[k]} for k, v in ranked[:20]},
    }
    return json.dumps(out, indent=1)


@app.local_entrypoint()
def main() -> None:
    print(run.remote())
