"""Render drift cards and harmful-compliance summaries into one HTML page.

    python scripts/build_report.py \
        --card .tools/cards/m1-vs-m0/drift-card.json \
        --card .tools/cards/m4-vs-m0/drift-card.json \
        --harmful .tools/harmful/m1.json \
        --out .tools/report/index.html

The page reads card JSON only. It never touches a model, a GPU, or an API, which is
the point: the card is the contract, and every renderer is downstream of it.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

AXIS_LABELS = {
    "refusal_error": "refusal error",
    "sycophancy": "sycophancy",
    "deception": "deception",
    "power_seeking": "power seeking",
    "sabotage": "sabotage",
}
VERDICT_COLOR = {"green": "#3fb950", "amber": "#d29922", "red": "#f85149"}


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _bar(z: float) -> str:
    width = min(abs(z) / 3.0, 1.0) * 100
    color = "#f85149" if z > 0 else "#3fb950"
    return (
        f'<div class="bar"><span style="width:{width:.0f}%;background:{color}"></span></div>'
    )


def _card_html(card: dict[str, Any]) -> str:
    drift = card["drift"]
    verdict = drift["verdict"]["level"]
    color = VERDICT_COLOR.get(verdict, "#8b949e")
    rows = []
    for axis, score in drift["axes"].items():
        label = AXIS_LABELS.get(axis, axis)
        rows.append(
            "<tr>"
            f"<td>{html.escape(label)}</td>"
            f"<td class='num'>{score['reference']:.2f}</td>"
            f"<td class='num'>{score['candidate']:.2f}</td>"
            f"<td class='num'>{score['z']:+.1f}</td>"
            f"<td class='num'>{score['q']:.3f}</td>"
            f"<td>{_bar(score['z'])}</td>"
            "</tr>"
        )

    validity = ""
    if card.get("validity") == "suspect":
        validity = (
            '<p class="warn"><strong>MEASUREMENT SUSPECT</strong> '
            f"{html.escape(card.get('validity_reason', ''))}</p>"
        )

    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in drift["verdict"]["reasons"])
    reasons_html = f"<ul class='reasons'>{reasons}</ul>" if reasons else ""

    return f"""
    <section class="card">
      <header>
        <div>
          <h2>{html.escape(drift['candidate'])}</h2>
          <p class="muted">against {html.escape(drift['reference'])} ·
             {drift['n_probes']} probes · panel {html.escape(drift['panel_hash'])}</p>
        </div>
        <span class="badge" style="background:{color}">{verdict.upper()}</span>
      </header>
      {validity}
      {reasons_html}
      <table>
        <thead><tr><th>axis</th><th>ref</th><th>cand</th><th>z</th><th>q</th><th></th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      <p class="muted">magnitude {drift['magnitude']:.2f}σ</p>
    </section>
    """


def _harmful_html(summary: dict[str, Any]) -> str:
    ref = summary["reference_rate"]
    cand = summary["candidate_rate"]
    ci_low, ci_high = summary["ci"]
    return f"""
    <section class="card">
      <header>
        <div>
          <h2>{html.escape(summary['candidate'])} on harmful requests</h2>
          <p class="muted">{summary['n']} public AdvBench goals · compliance counts as failure</p>
        </div>
        <span class="badge" style="background:{'#f85149' if summary['delta'] > 0.3 else '#3fb950'}">
          Δ {summary['delta']:+.2f}
        </span>
      </header>
      <div class="compare">
        <div><span class="big">{_pct(ref)}</span><span class="muted">reference</span></div>
        <div class="arrow">→</div>
        <div><span class="big">{_pct(cand)}</span><span class="muted">candidate</span></div>
      </div>
      <p class="muted">95% CI [{ci_low:+.2f}, {ci_high:+.2f}] · p = {summary['p']:.4f}</p>
    </section>
    """


def build(cards: list[dict], harmful: list[dict], title: str) -> str:
    cards_html = "".join(_card_html(card) for card in cards)
    harmful_html = "".join(_harmful_html(summary) for summary in harmful)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; padding: 40px; background: #0d1117; color: #e6edf3;
         font: 15px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 0; }}
  .muted {{ color: #8b949e; font-size: 12px; margin: 2px 0; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
           gap: 16px; margin-top: 24px; }}
  .card {{ background: #161b22; border: 1px solid #21262d; border-radius: 10px; padding: 18px; }}
  .card header {{ display: flex; justify-content: space-between; align-items: flex-start;
                  gap: 12px; margin-bottom: 12px; }}
  .badge {{ padding: 4px 10px; border-radius: 999px; color: #0d1117; font-weight: 700;
            font-size: 12px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th {{ text-align: left; color: #8b949e; font-weight: 500; font-size: 11px;
        text-transform: uppercase; letter-spacing: .05em; }}
  td, th {{ padding: 6px 4px; border-bottom: 1px solid #21262d; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .bar {{ background: #21262d; height: 8px; border-radius: 4px; overflow: hidden; width: 110px; }}
  .bar span {{ display: block; height: 100%; }}
  .warn {{ background: #3d2b00; border-left: 3px solid #d29922; padding: 8px 10px;
           border-radius: 4px; font-size: 12px; }}
  .reasons {{ margin: 0 0 8px; padding-left: 18px; color: #8b949e; font-size: 12px; }}
  .compare {{ display: flex; align-items: center; gap: 24px; margin: 12px 0 4px; }}
  .compare div {{ display: flex; flex-direction: column; }}
  .big {{ font-size: 32px; font-weight: 700; }}
  .arrow {{ color: #8b949e; font-size: 20px; }}
  footer {{ margin-top: 32px; color: #8b949e; font-size: 12px; }}
</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p class="muted">One base model, three checkpoints, one card format.
     Rendered from card JSON only.</p>
  <div class="grid">
    {cards_html}
    {harmful_html}
  </div>
  <footer>Keel · synthetic demo data excluded · cards hash-pinned to a panel</footer>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--card", action="append", default=[])
    parser.add_argument("--harmful", action="append", default=[])
    parser.add_argument("--title", default="Keel drift report")
    parser.add_argument("--out", default=".tools/report/index.html")
    args = parser.parse_args()

    cards = [json.loads(Path(path).read_text()) for path in args.card]
    harmful = [json.loads(Path(path).read_text()) for path in args.harmful]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(cards, harmful, args.title), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
