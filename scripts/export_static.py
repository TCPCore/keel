"""Export the Space as a static site, for a free Hugging Face static Space.

    python scripts/export_static.py --out space/static

A static Space cannot run the judge, so this mirror shows the fleet, the cards, the JSON
downloads and the method page. Every live interaction stays on the Modal deployment.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STYLE = """
:root{color-scheme:dark}body{margin:0;padding:32px;background:#0d1117;color:#e6edf3;
font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
a{color:#58a6ff;text-decoration:none}.muted{color:#8b949e;font-size:12px}
table{width:100%;border-collapse:collapse;margin-top:12px;max-width:1000px}
th{text-align:left;color:#8b949e;font-size:11px;font-weight:500}
td,th{padding:7px 6px;border-bottom:1px solid #21262d}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.badge{padding:3px 9px;border-radius:999px;color:#0d1117;font-weight:700;font-size:11px}
.warn{background:#3d2b00;border-left:3px solid #d29922;padding:8px 10px;border-radius:4px;font-size:12px}
.note{border-left:3px solid #30363d;padding-left:12px;color:#8b949e;font-size:13px;max-width:900px}
"""


def _page(title: str, body: str) -> str:
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>{title}</title><style>{STYLE}</style></head><body>{body}</body></html>"
    )


def _badge(verdict: str) -> str:
    color = {"green": "#3fb950", "amber": "#d29922", "red": "#f85149"}.get(verdict, "#8b949e")
    return f"<span class='badge' style='background:{color}'>{verdict.upper()}</span>"


def _num(value) -> str:
    return "—" if value is None else f"{float(value):.2f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="space/static")
    args = parser.parse_args()

    out = ROOT / args.out
    if out.exists():
        shutil.rmtree(out)
    (out / "card").mkdir(parents=True)

    fleet = json.loads((ROOT / "space/fleet.json").read_text())
    rows = []
    for row in fleet:
        link = f"card/{row['slug']}.html" if row.get("card") else "#"
        rows.append(
            f"<tr><td><a href='{link}'>{row['model']}</a></td><td>{row['kind']}</td>"
            f"<td>{_badge(row['verdict']) if row['verdict'] != '—' else '<span class=muted>baseline</span>'}</td>"
            f"<td>{row['validity']}</td><td class='num'>{_num(row['compliance'])}</td>"
            f"<td class='num'>{row['judged'] or '—'}</td></tr>"
        )

    (out / "index.html").write_text(
        _page(
            "Keel",
            "<h1>Keel</h1><p class='muted'>One scanner, nine Meta checkpoints, comparable cards.</p>"
            "<table><thead><tr><th>model</th><th>source</th><th>verdict</th><th>validity</th>"
            "<th>harmful compliance</th><th>judged</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
            "<p class='note'>This is the static mirror. The live version, where any card can be "
            "re-scored against the judge in about twenty seconds, is at "
            "<a href='https://iamtrillion11--keel-space-web.us-east.modal.run'>"
            "iamtrillion11--keel-space-web.us-east.modal.run</a>.</p>"
            "<p><a href='about.html'>Method and limits</a></p>",
        ),
        encoding="utf-8",
    )

    for row in fleet:
        if not row.get("card"):
            continue
        payload = json.loads((ROOT / row["card"]).read_text())
        (out / "card" / f"{row['slug']}.json").write_text(
            json.dumps(payload, indent=1) + "\n", encoding="utf-8"
        )
        drift = payload["drift"]
        axes = "".join(
            f"<tr><td>{axis}</td><td class='num'>{s['reference']:.2f}</td>"
            f"<td class='num'>{s['candidate']:.2f}</td><td class='num'>{s['q']:.3f}</td></tr>"
            for axis, s in drift["axes"].items()
        )
        harmful = payload.get("harmful") or {}
        harmful_line = (
            f"<p>harmful compliance <b>{harmful['reference_rate']:.2f} → "
            f"{harmful['candidate_rate']:.2f}</b> over {harmful['n']} requests</p>"
            if harmful
            else "<p class='warn'>harmful half not measured: this card cannot be green</p>"
        )
        validity = (
            f"<p class='warn'>MEASUREMENT SUSPECT: {payload['validity_reason']}</p>"
            if payload.get("validity") == "suspect"
            else "<p class='muted'>validity ok</p>"
        )
        verdict = "amber" if payload.get("validity") == "suspect" else drift["verdict"]["level"]
        (out / "card" / f"{row['slug']}.html").write_text(
            _page(
                f"Keel · {row['slug']}",
                f"<p><a href='../index.html'>&larr; fleet</a></p>"
                f"<h1>{drift['candidate']}</h1>"
                f"<p class='muted'>against {drift['reference']} · {drift['n_probes']} probes · "
                f"fingerprint {payload.get('fingerprint', '—')}</p>"
                f"<p>{_badge(verdict)}</p>{validity}{harmful_line}"
                f"<table><thead><tr><th>axis</th><th>ref</th><th>cand</th><th>q</th></tr></thead>"
                f"<tbody>{axes}</tbody></table>"
                f"<p><a href='{row['slug']}.json'>Download JSON</a></p>",
            ),
            encoding="utf-8",
        )

    (out / "about.html").write_text(
        _page(
            "Keel · method",
            "<h1>Method and limits</h1>"
            "<p>Keel scans a checkpoint and emits a card: verdict, validity, harmful "
            "compliance, limits and a fingerprint. This mirror shows nine Meta checkpoints. "
            "Five are survey baselines, three are Glimmer cards with controls, two are "
            "harmful summaries.</p>"
            "<p>No card is green without the harmful half, and no card is green if the format "
            "gate fires. That is the validity contract, and it has refused four times.</p>"
            "<p class='note'>Detection is demonstrated on Glimmer derivatives, where a "
            "positive control can be built. Spark models are black-box baselines: a hosted "
            "endpoint cannot be modified, so no Spark positive control can be constructed. "
            "The judge moves between runs, so compliance is reported as a range.</p>",
        ),
        encoding="utf-8",
    )

    (out / "README.md").write_text(
        "---\ntitle: Keel\nemoji: 🧭\ncolorFrom: blue\ncolorTo: green\n"
        "sdk: static\napp_file: index.html\npinned: false\n---\n\n"
        "# Keel\n\nStatic mirror of the checkpoint validity scanner. "
        "Live re-scoring is at https://iamtrillion11--keel-space-web.us-east.modal.run\n",
        encoding="utf-8",
    )
    print(f"exported {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
