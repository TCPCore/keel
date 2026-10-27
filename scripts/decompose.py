"""Recover the intervention stack from a derivative checkpoint.

Stage 1 (this file): fetch base and derivative, compute the per-module weight delta,
and rank modules by relative change. If the declared directional edit is real, the
edited residual writers should dominate that ranking before any clever analysis.

    python scripts/decompose.py fetch --derivative darkc0de/Muse-Glimmer-30B-heretic
    python scripts/decompose.py report

The validation target is darkc0de/Muse-Glimmer-30B-heretic, whose card publishes the
abliteration parameters. If our extraction cannot recover a published recipe, it has no
business being pointed at a composite whose parameters are unknown.
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

BASE = "meta-models/Muse-Glimmer-30B"
app = modal.App("keel-decompose")
vol = modal.Volume.from_name("keel-decomp", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch", "numpy", "safetensors", "huggingface_hub")
)


@app.function(image=image, volumes={"/data": vol}, timeout=5400, cpu=8, memory=32768)
def fetch(derivative: str, label: str) -> dict:
    from collections import defaultdict

    from huggingface_hub import snapshot_download
    from safetensors.torch import load_file

    base_dir = Path("/data/base")
    deriv_dir = Path(f"/data/{label}")
    if not (base_dir / "config.json").exists():
        print("downloading base", flush=True)
        snapshot_download(BASE, local_dir=base_dir)
        vol.commit()
    if not (deriv_dir / "config.json").exists():
        print(f"downloading derivative {derivative}", flush=True)
        snapshot_download(derivative, local_dir=deriv_dir)
        vol.commit()

    def shard_index(path: Path) -> dict:
        index = json.loads((path / "model.safetensors.index.json").read_text())
        return index["weight_map"]

    base_map = shard_index(base_dir)
    deriv_map = shard_index(deriv_dir)
    shared = sorted(set(base_map) & set(deriv_map))
    print(f"shared tensors: {len(shared)} of {len(base_map)} base", flush=True)

    by_base_shard: dict[str, list[str]] = defaultdict(list)
    for name in shared:
        by_base_shard[base_map[name]].append(name)

    rows = []
    done = 0
    for b_shard, names in by_base_shard.items():
        base_tensors = load_file(str(base_dir / b_shard))
        deriv_shards = {deriv_map[name] for name in names}
        deriv_tensors = {shard: load_file(str(deriv_dir / shard)) for shard in deriv_shards}
        for name in names:
            b = base_tensors[name].float()
            d = deriv_tensors[deriv_map[name]][name].float()
            if b.shape != d.shape:
                continue
            delta = d - b
            base_norm = b.norm().item()
            rows.append(
                {
                    "name": name,
                    "shape": list(b.shape),
                    "base_norm": base_norm,
                    "delta_norm": delta.norm().item(),
                    "relative": delta.norm().item() / base_norm if base_norm else 0.0,
                    "max_abs": delta.abs().max().item(),
                }
            )
            done += 1
        del base_tensors, deriv_tensors
        print(f"{done}/{len(shared)}", flush=True)

    rows.sort(key=lambda row: row["relative"], reverse=True)
    out = Path(f"/data/delta-{label}.json")
    out.write_text(json.dumps(rows, indent=1))
    vol.commit()

    print(f"\ntop modules by relative change ({label}):", flush=True)
    for row in rows[:15]:
        print(f"  {row['relative']:.4f}  {row['name']:<58} {row['shape']}", flush=True)
    return {"tensors": len(rows), "top": rows[:15]}


@app.local_entrypoint()
def main(stage: str = "fetch", derivative: str = "darkc0de/Muse-Glimmer-30B-heretic",
         label: str = "heretic") -> None:
    if stage == "fetch":
        result = fetch.remote(derivative, label)
        print(json.dumps(result["top"][:5], indent=1))
    else:
        print("stages: fetch")
