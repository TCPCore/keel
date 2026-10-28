"""Publish results/results.json as a markdown table and a static page.

    python scripts/publish_results.py --results results/results.json
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _ci(pair: list[float] | None) -> str:
    if not pair:
        return "—"
    return f"[{pair[0]:.2f}, {pair[1]:.2f}]"


def markdown(results: list[dict]) -> str:
    lines = [
        "# Model survey",
        "",
        "Every text model in the hackathon list, run through the same 32 panel probes and",
        "the same 32 harmful prompts, judged by a separate checkpoint (Spark Open on",
        "Baseten). Harmful completions are not published; only statistics are.",
        "",
        "| model | panel code | panel refusals | panel empty | harmful compliance "
        "| 95% CI | judged | harmful refusal phrase | median chars |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in results:
        panel = row["panel"]
        harmful = row["harmful"]
        lines.append(
            f"| {row['model']} | {_pct(panel['code_rate'])} | {_pct(panel['refusal_rate'])} "
            f"| {_pct(panel['empty_rate'])} | {_pct(harmful['compliance'])} "
            f"| {_ci(harmful['ci'])} | {harmful['judged']}/{harmful['requests']} "
            f"| {_pct(harmful['refusal_phrase_rate'])} | {harmful['median_chars']} |"
        )
    lines += [
        "",
        "## Not applicable to this scan",
        "",
        "Muse Image, Muse Voice Transcribe and SAM 3.1 are generation, transcription and",
        "segmentation models. They do not answer text probes, so a text checkpoint scan",
        "does not apply to them. Forcing them into one would be a category error.",
        "",
        "## Reproduction",
        "",
        "```console",
        "$ python scripts/suite.py --out results",
        "$ python scripts/publish_results.py --results results/results.json",
        "```",
        "",
        "Settings: greedy, 192 new tokens, `reasoning_effort=low`, judge prompt fixed in",
        "`scripts/suite.py`. Model ids are recorded per row.",
    ]
    return "\n".join(lines) + "\n"


def page(results: list[dict]) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(row['model'])}</td>"
        f"<td class='num'>{_pct(row['panel']['code_rate'])}</td>"
        f"<td class='num'>{_pct(row['panel']['refusal_rate'])}</td>"
        f"<td class='num'>{_pct(row['harmful']['compliance'])}</td>"
        f"<td class='num'>{_ci(row['harmful']['ci'])}</td>"
        f"<td class='num'>{row['harmful']['judged']}/{row['harmful']['requests']}</td></tr>"
        for row in results
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Keel model survey</title>
<style>
 body{{margin:0;padding:40px;background:#0d1117;color:#e6edf3;
      font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}}
 h1{{font-size:22px;margin:0 0 4px}} .muted{{color:#8b949e;font-size:12px}}
 table{{width:100%;border-collapse:collapse;margin-top:20px;max-width:1000px}}
 th{{text-align:left;color:#8b949e;font-size:11px;font-weight:500}}
 td,th{{padding:7px 6px;border-bottom:1px solid #21262d}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums}}
 .note{{margin-top:24px;color:#8b949e;font-size:13px;max-width:900px;
        border-left:3px solid #30363d;padding-left:12px}}
</style></head><body>
<h1>Keel model survey</h1>
<p class="muted">Same 32 panel probes and 32 harmful prompts for every model.
Judged by Spark Open on Baseten. Harmful completions are not published.</p>
<table><thead><tr><th>model</th><th>panel code</th><th>panel refusals</th>
<th>harmful compliance</th><th>95% CI</th><th>judged</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="note">Muse Image, Muse Voice Transcribe and SAM 3.1 are generation,
transcription and segmentation models. They do not answer text probes, so a text
checkpoint scan does not apply to them.</p>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results/results.json")
    args = parser.parse_args()
    results = json.loads((ROOT / args.results).read_text())
    out = ROOT / "results"
    (out / "SUMMARY.md").write_text(markdown(results), encoding="utf-8")
    (out / "index.html").write_text(page(results), encoding="utf-8")
    print(f"wrote {out}/SUMMARY.md and {out}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
