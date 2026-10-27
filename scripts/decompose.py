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


@app.function(image=image, volumes={"/data": vol}, timeout=3600, cpu=8, memory=24576)
def analyze(label: str, low: int = 18, high: int = 42) -> dict:
    """Per-module SVD on o_proj, written incrementally so a crash cannot lose it."""
    import re

    import numpy as np
    from safetensors.torch import load_file

    base_dir = Path("/data/base")
    deriv_dir = Path(f"/data/{label}")

    def shard_index(path: Path) -> dict:
        return json.loads((path / "model.safetensors.index.json").read_text())["weight_map"]

    base_map = shard_index(base_dir)
    deriv_map = shard_index(deriv_dir)
    pattern = re.compile(r"layers\.(\d+)\.self_attn\.o_proj\.weight$")

    targets: dict[str, list[tuple[int, str]]] = {}
    for name in set(base_map) & set(deriv_map):
        match = pattern.search(name)
        if match and low <= int(match.group(1)) <= high:
            targets.setdefault(base_map[name], []).append((int(match.group(1)), name))

    out_path = Path(f"/data/svd-rows-{label}.jsonl")
    out_path.write_text("")
    reference = None
    rows = []
    for b_shard, items in sorted(targets.items()):
        base_tensors = load_file(str(base_dir / b_shard))
        deriv_shards = {deriv_map[name] for _, name in items}
        deriv_tensors = {shard: load_file(str(deriv_dir / shard)) for shard in deriv_shards}
        for layer, name in sorted(items):
            delta = (
                deriv_tensors[deriv_map[name]][name].float() - base_tensors[name].float()
            ).numpy()
            u, sv, vh = np.linalg.svd(delta, full_matrices=False)
            sigma2 = float(sv[1]) if len(sv) > 1 else 0.0
            in_dir = vh[0]
            if reference is None:
                reference = in_dir
                cosine = 1.0
            else:
                cosine = float(abs(in_dir @ reference))
            row = {
                "layer": layer,
                "sigma1": float(sv[0]),
                "sigma2": sigma2,
                "rank1_ratio": float(sv[0]) / sigma2 if sigma2 else float("inf"),
                "energy": float(sv[0]) / float(sv.sum()),
                "cos_to_first": cosine,
            }
            rows.append(row)
            with out_path.open("a") as handle:
                handle.write(json.dumps(row) + "\n")
            print(
                f"L{layer:02d} s1={row['sigma1']:.4f} s2={row['sigma2']:.4f} "
                f"ratio={row['rank1_ratio']:.1f} energy={row['energy']:.3f} "
                f"cos={cosine:.3f}",
                flush=True,
            )
        del base_tensors, deriv_tensors
        vol.commit()
        print(f"committed after {len(rows)} modules", flush=True)

    summary = {
        "modules": len(rows),
        "rank1_ratio_median": float(np.median([r["rank1_ratio"] for r in rows])),
        "energy_median": float(np.median([r["energy"] for r in rows])),
        "cos_mean": float(np.mean([r["cos_to_first"] for r in rows])),
        "cos_min": float(np.min([r["cos_to_first"] for r in rows])),
    }
    Path(f"/data/svd-summary-{label}.json").write_text(json.dumps(summary, indent=1))
    vol.commit()
    print(json.dumps(summary, indent=1), flush=True)
    return summary


@app.local_entrypoint()
def main(stage: str = "fetch", derivative: str = "darkc0de/Muse-Glimmer-30B-heretic",
         label: str = "heretic") -> None:
    if stage == "fetch":
        result = fetch.remote(derivative, label)
        print(json.dumps(result["top"][:5], indent=1))
    elif stage == "analyze":
        rows = analyze.remote(label)
        print(f"analyzed {len(rows)} modules")
    else:
        print("stages: fetch, analyze")
