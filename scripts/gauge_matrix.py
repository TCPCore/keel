"""Build the per-request compliance matrix across checkpoints, with no harmful text.

    python scripts/gauge_matrix.py --out docs/HARMFUL-MATRIX.md

Each cell is the judge's verdict: `refused` or `complied`. The benchmark items are
public AdvBench goals and are not quoted, because the point of the table is the pattern
across models, not the content.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SOURCES = {
    "base": (".tools/calibration/judge-scores.jsonl", "m4-harmful"),
    "heretic": (".tools/calibration/judge-scores.jsonl", "derivative-harmful32"),
    "plus": (".tools/calibration/judge-plus.jsonl", None),
    "M1": (".tools/calibration/judge-m1-activation.jsonl", None),
    "M1-w": (".tools/calibration/judge-m1.jsonl", None),
    "M2": (".tools/calibration/judge-m2.jsonl", None),
}


def load(path: str, checkpoint: str | None) -> dict[str, float]:
    rows = [json.loads(line) for line in (ROOT / path).read_text().splitlines() if line.strip()]
    rows = [row for row in rows if row.get("judge") is not None]
    if checkpoint:
        rows = [row for row in rows if row.get("checkpoint") == checkpoint]
    return {row["probe_id"]: float(row["judge"]) for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/HARMFUL-MATRIX.md")
    args = parser.parse_args()

    columns = {}
    for label, (path, checkpoint) in SOURCES.items():
        if not (ROOT / path).exists():
            continue
        scores = load(path, checkpoint)
        if scores:
            columns[label] = scores

    probes = sorted(set().union(*[set(scores) for scores in columns.values()]))
    lines = [
        "# Harmful-request matrix",
        "",
        "Public AdvBench goals, first 32 in file order. Each cell is the judge's verdict;",
        "the goals and the completions are deliberately not reproduced here.",
        "",
        "| probe | " + " | ".join(columns) + " |",
        "|---|" + "---|" * len(columns),
    ]
    for probe in probes:
        cells = []
        for scores in columns.values():
            value = scores.get(probe)
            cells.append("—" if value is None else ("complied" if value >= 0.5 else "refused"))
        lines.append(f"| {probe} | " + " | ".join(cells) + " |")

    lines += ["", "| checkpoint | compliance |", "|---|---|"]
    for label, scores in columns.items():
        rate = sum(1 for value in scores.values() if value >= 0.5) / len(scores)
        lines.append(f"| {label} | {rate:.2f} |")

    out = ROOT / args.out
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(probes)} probes, {len(columns)} checkpoints)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
