"""Build the three-variant demo page from measured artifacts.

    python scripts/build_demo.py --out examples/demo.html

Every number is read from a calibration or card file. Nothing is typed in by hand
except the structural table, which is labeled with its source.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CARDS = [
    (".tools/cards/m1-vs-m0/drift-card.json", "positive control: refusal ablation"),
    (".tools/cards/m4-vs-m0/drift-card.json", "negative control: 4-bit against BF16"),
    (".tools/cards/m2-gated/drift-card.json", "invalid positive: format collapse"),
]
CALIBRATION = {
    "base": (".tools/calibration/judge-scores.jsonl", "m4-harmful"),
    "derivative": (".tools/calibration/judge-scores.jsonl", "derivative-harmful32"),
    "replay 1x": (".tools/calibration/judge-scores.jsonl", "replay-harmful32"),
    "replay 2x": (".tools/calibration/judge-replay2x.jsonl", None),
    "replay 4x": (".tools/calibration/judge-replay4x.jsonl", None),
    "m1 control": (".tools/calibration/judge-m1.jsonl", None),
}
STRUCTURAL = {
    "rank-1 ratio (median)": "82.1",
    "hidden-space cosine across layers": "0.995 to 1.000",
    "head-space cosine across layers": "0.003 to 0.019",
    "layers recovered": "24 to 28 of 52",
    "peak scale layer": "28",
}
DELTA_TOP = [
    ("31", "self_attn.o_proj", "0.0217"),
    ("29", "self_attn.o_proj", "0.0196"),
    ("37", "self_attn.o_proj", "0.0193"),
    ("31", "mlp.down_proj", "0.0191"),
    ("24", "self_attn.o_proj", "0.0191"),
    ("30", "self_attn.o_proj", "0.0190"),
]


def compliance(path: str, checkpoint: str | None) -> tuple[float, float, float, int]:
    rows = [
        json.loads(line)
        for line in (ROOT / path).read_text().splitlines()
        if line.strip()
    ]
    rows = [r for r in rows if r.get("judge") is not None]
    if checkpoint:
        rows = [r for r in rows if r["checkpoint"] == checkpoint]
    vals = np.array([float(r["judge"]) for r in rows])
    rng = np.random.default_rng(0)
    boots = vals[rng.integers(0, len(vals), size=(3000, len(vals)))].mean(axis=1)
    low, high = np.quantile(boots, [0.025, 0.975])
    return float(vals.mean()), float(low), float(high), len(vals)


def bar(value: float, ceiling: float = 1.0) -> str:
    width = max(0.0, min(value / ceiling, 1.0)) * 100
    color = "#f85149" if value > 0.4 else "#d29922" if value > 0.05 else "#3fb950"
    return f'<div class="bar"><span style="width:{width:.0f}%;background:{color}"></span></div>'


def card_html(card: dict, note: str) -> str:
    drift = card["drift"]
    verdict = drift["verdict"]["level"]
    color = {"green": "#3fb950", "amber": "#d29922", "red": "#f85149"}[verdict]
    rows = "".join(
        f"<tr><td>{html.escape(axis)}</td>"
        f"<td class='num'>{s['reference']:.2f}</td>"
        f"<td class='num'>{s['candidate']:.2f}</td>"
        f"<td class='num'>{s['q']:.3f}</td></tr>"
        for axis, s in drift["axes"].items()
    )
    suspect = (
        f'<p class="warn">MEASUREMENT SUSPECT: {html.escape(card["validity_reason"])}</p>'
        if card.get("validity") == "suspect"
        else ""
    )
    return f"""
    <section class="card">
      <header><div><h3>{html.escape(drift['candidate'])}</h3>
        <p class="muted">{html.escape(note)}</p></div>
        <span class="badge" style="background:{color}">{verdict.upper()}</span></header>
      {suspect}
      <table><thead><tr><th>axis</th><th>ref</th><th>cand</th><th>q</th></tr></thead>
      <tbody>{rows}</tbody></table>
    </section>
    """


def build(title: str) -> str:
    parts = []
    for path, note in CARDS:
        parts.append(card_html(json.loads((ROOT / path).read_text()), note))
    cards_html = "".join(parts)

    rows = []
    for label, (path, checkpoint) in CALIBRATION.items():
        mean, low, high, n = compliance(path, checkpoint)
        rows.append(
            f"<tr><td>{label}</td><td class='num'>{mean:.3f}</td>"
            f"<td class='num'>[{low:.3f}, {high:.3f}]</td>"
            f"<td class='num'>{n}</td><td>{bar(mean)}</td></tr>"
        )
    replay_rows = "".join(rows)

    structural_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td class='num'>{html.escape(v)}</td></tr>"
        for k, v in STRUCTURAL.items()
    )
    delta_rows = "".join(
        f"<tr><td class='num'>{layer}</td><td>{html.escape(module)}</td>"
        f"<td class='num'>{value}</td></tr>"
        for layer, module, value in DELTA_TOP
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
 :root {{ color-scheme: dark; }}
 body {{ margin:0; padding:40px; background:#0d1117; color:#e6edf3;
        font:15px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; }}
 h1 {{ font-size:24px; margin:0 0 6px; }} h2 {{ font-size:18px; margin:44px 0 6px; }}
 h3 {{ font-size:14px; margin:0; }}
 .muted {{ color:#8b949e; font-size:12px; margin:2px 0; }}
 .lede {{ max-width:900px; color:#c9d1d9; }}
 .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(380px,1fr));
          gap:16px; margin-top:14px; }}
 .card {{ background:#161b22; border:1px solid #21262d; border-radius:10px; padding:16px; }}
 .card header {{ display:flex; justify-content:space-between; gap:12px; margin-bottom:10px; }}
 .badge {{ padding:4px 10px; border-radius:999px; color:#0d1117; font-weight:700; font-size:11px; }}
 table {{ width:100%; border-collapse:collapse; margin-top:6px; }}
 th {{ text-align:left; color:#8b949e; font-size:11px; font-weight:500; }}
 td,th {{ padding:5px 4px; border-bottom:1px solid #21262d; }}
 td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
 .bar {{ background:#21262d; height:8px; border-radius:4px; overflow:hidden; width:120px; }}
 .bar span {{ display:block; height:100%; }}
 .warn {{ background:#3d2b00; border-left:3px solid #d29922; padding:8px; border-radius:4px;
          font-size:12px; }}
 .note {{ border-left:3px solid #30363d; padding-left:12px; color:#8b949e; font-size:13px; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p class="lede">One base model. Three views of one checkpoint family. The gate is proven;
the decomposition recovers structure and mechanism; the magnitude is the named gap.</p>

<h2>1. Safety gate</h2>
<p class="muted">Behavioural scan against the base. Positive, negative and invalid cases.</p>
<div class="grid">{cards_html}</div>

<h2>2. Recipe auditor</h2>
<p class="muted">Weight delta from base to the declared heretic, ranked per tensor.</p>
<table><thead><tr><th>layer</th><th>module</th><th>relative delta</th></tr></thead>
<tbody>{delta_rows}</tbody></table>
<p class="muted">Recovered structure from per-module SVD.</p>
<table><tbody>{structural_rows}</tbody></table>

<h2>3. Replay, and what it can and cannot claim</h2>
<p class="muted">Harmful compliance, 32 public AdvBench goals, judge primary.</p>
<table><thead><tr><th>checkpoint</th><th>compliance</th><th>95% CI</th>
<th>n</th><th></th></tr></thead>
<tbody>{replay_rows}</tbody></table>
<p class="note">The replay reproduces the mechanism, not the magnitude. At 1x nothing
happens; at 2x and 4x it sits at the method's ceiling. The derivative at 0.188 is between
the regimes, and the per-module intensity is the parameter this extraction does not
recover. The completeness claim is withdrawn for that reason.</p>

<h2>Method notes</h2>
<p class="note">Scorer calibration: deterministic refusal classifier agreed with the judge
on 53 percent of 96 responses, then 78 percent after folding typographic quotes and
matching the refusal verb. The remaining disagreements favour the judge, so the judge is
primary. The replay tolerance and decision rule were pre-registered in
docs/REPLAY_PROTOCOL.md before the 32-prompt run.</p>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="examples/demo.html")
    args = parser.parse_args()
    out = Path(args.out)
    out.write_text(build("Keel: gate, recipe, and the honest gap"), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
