"""Keel Space: a judge-clickable view of the model-class survey.

Three modes, each labelled honestly:

  view      the fleet table, from committed cards and survey results
  re-score  re-run judging, drift statistics, the format gate and policy on cached
            responses, live, for the three Glimmer checkpoints
  download  every card as JSON with its fingerprint

Run locally:

    uvicorn space.app:app --port 7860

Deploy: see space/README.md.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

ROOT = Path(__file__).resolve().parents[1]
FLEET = json.loads((ROOT / "space/fleet.json").read_text())
CARDS = {row["slug"]: row["card"] for row in FLEET if row.get("card")}
RESPONSES = {
    "m0-base": "examples/responses/m0-base-panel.jsonl",
    "m1-ablation": "examples/responses/m1-ablation-panel.jsonl",
    "m2-lora": "examples/responses/m2-lora-panel.jsonl",
}
HARMFUL = {
    "m0-base": "examples/responses/m0-base-harmful.json",
    "m1-ablation": "examples/responses/m1-ablation-harmful.json",
    "m2-lora": "examples/responses/m2-lora-harmful.json",
}
BASE = "examples/responses/m0-base-panel.jsonl"

app = FastAPI(title="Keel")
HITS: dict[str, list[float]] = defaultdict(list)
LIMIT = 3
WINDOW = 3600


def _allowed(ip: str) -> bool:
    now = time.time()
    HITS[ip] = [stamp for stamp in HITS[ip] if now - stamp < WINDOW]
    if len(HITS[ip]) >= LIMIT:
        return False
    HITS[ip].append(now)
    return True


def _card(slug: str) -> dict:
    path = CARDS.get(slug)
    if not path:
        raise HTTPException(404, "no card for this entry")
    return json.loads((ROOT / path).read_text())


def _num(value) -> str:
    return "—" if value is None else f"{float(value):.2f}"


def _badge(verdict: str) -> str:
    color = {"green": "#3fb950", "amber": "#d29922", "red": "#f85149"}.get(verdict, "#8b949e")
    return f'<span class="badge" style="background:{color}">{verdict.upper()}</span>'


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{title}</title><style>
:root{{color-scheme:dark}}body{{margin:0;padding:32px;background:#0d1117;color:#e6edf3;
font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}}
h1{{font-size:22px;margin:0 0 4px}}h2{{font-size:17px;margin:28px 0 8px}}
a{{color:#58a6ff;text-decoration:none}}.muted{{color:#8b949e;font-size:12px}}
table{{width:100%;border-collapse:collapse;margin-top:12px;max-width:1000px}}
th{{text-align:left;color:#8b949e;font-size:11px;font-weight:500}}
td,th{{padding:7px 6px;border-bottom:1px solid #21262d}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}
.badge{{padding:3px 9px;border-radius:999px;color:#0d1117;font-weight:700;font-size:11px}}
.card{{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:18px;max-width:920px}}
.warn{{background:#3d2b00;border-left:3px solid #d29922;padding:8px 10px;border-radius:4px;font-size:12px}}
button{{background:#238636;color:#fff;border:0;border-radius:6px;padding:8px 14px;font:inherit;cursor:pointer}}
.note{{border-left:3px solid #30363d;padding-left:12px;color:#8b949e;font-size:13px;max-width:900px}}
</style></head><body>{body}</body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    rows = "".join(
        f"<tr><td><a href='/card/{row['slug']}'>{row['model']}</a></td>"
        f"<td>{row['kind']}</td>"
        f"<td>{_badge(row['verdict']) if row['verdict'] != '—' else '<span class=muted>baseline</span>'}</td>"
        f"<td>{row['validity']}</td>"
        f"<td class='num'>{_num(row['compliance'])}</td>"
        f"<td class='num'>{row['judged'] or '—'}</td></tr>"
        for row in FLEET
    )
    return _page(
        "Keel",
        f"<h1>Keel</h1><p class='muted'>One scanner, nine Meta checkpoints, comparable cards.</p>"
        f"<table><thead><tr><th>model</th><th>source</th><th>verdict</th><th>validity</th>"
        f"<th>harmful compliance</th><th>judged</th></tr></thead><tbody>{rows}</tbody></table>"
        "<p class='note'>Five Spark and Wonder rows are baselines from the survey. The three "
        "Glimmer rows are cards with a positive and a negative control. Heretic and heretic-plus "
        "are harmful summaries without a card. <a href='/about'>Method and limits</a>.</p>",
    )


@app.get("/card/{slug}", response_class=HTMLResponse)
def card(slug: str) -> str:
    payload = _card(slug)
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
    rescore = (
        f"<form method='post' action='/rescore/{slug}'><button>Re-score live</button></form>"
        if slug in RESPONSES
        else "<p class='muted'>Re-score unavailable: no cached responses for this entry.</p>"
    )
    return _page(
        f"Keel · {slug}",
        f"<p><a href='/'>&larr; fleet</a></p><h1>{drift['candidate']}</h1>"
        f"<p class='muted'>against {drift['reference']} · {drift['n_probes']} probes · "
        f"fingerprint {payload.get('fingerprint', '—')}</p>"
        f"<p>{_badge(verdict)}</p>{validity}{harmful_line}"
        f"<table><thead><tr><th>axis</th><th>ref</th><th>cand</th><th>q</th></tr></thead>"
        f"<tbody>{axes}</tbody></table>"
        f"<p>{rescore}</p>"
        f"<p><a href='/card/{slug}/json'>Download JSON</a></p>",
    )


@app.get("/card/{slug}/json")
def card_json(slug: str) -> JSONResponse:
    return JSONResponse(_card(slug))


@app.post("/rescore/{slug}")
def rescore(slug: str, request: Request) -> RedirectResponse:
    if slug not in RESPONSES:
        raise HTTPException(404, "no cached responses for this entry")
    if not os.environ.get("BASETEN_API_KEY"):
        raise HTTPException(503, "no judge key configured")
    ip = request.client.host if request.client else "unknown"
    if not _allowed(ip):
        raise HTTPException(429, "rate limit: 3 re-scores per hour per address")

    from keel.api import Client
    from keel.panel import builtin
    from keel.report import write_card
    from keel.scan import load_responses, scan_responses
    from keel.scorers import JudgeScorer

    judge = JudgeScorer(
        Client(
            api_key=os.environ["BASETEN_API_KEY"],
            base_url=os.environ.get("BASETEN_BASE_URL", "https://inference.baseten.co/v1"),
            model=os.environ.get("BASETEN_MODEL_ID", "meta-models/muse-spark-open"),
        ),
        axis="sycophancy",
    )
    rows = [json.loads(line) for line in (ROOT / RESPONSES[slug]).read_text().splitlines() if line.strip()]
    base_rows = [json.loads(line) for line in (ROOT / BASE).read_text().splitlines() if line.strip()]
    harmful = json.loads((ROOT / HARMFUL[slug]).read_text()) if slug in HARMFUL else None
    built = scan_responses(
        load_responses(base_rows),
        load_responses(rows),
        builtin(),
        judge=judge,
        reference_id="m0-base",
        candidate_id=slug,
        harmful=harmful,
    )
    write_card(built, ROOT / f"examples/demo-cards/{slug}")
    return RedirectResponse(f"/card/{slug}", status_code=303)


@app.get("/about", response_class=HTMLResponse)
def about() -> str:
    return _page(
        "Keel · method",
        "<h1>Method and limits</h1>"
        "<p>Keel scans a checkpoint and emits a card: verdict, validity, harmful compliance, "
        "limits and a fingerprint. This page runs the same scanner on nine Meta checkpoints. "
        "Five are survey baselines, four are Glimmer checkpoints with controls.</p>"
        "<p><b>Re-score</b> re-runs the judge, the drift statistics, the format gate and the "
        "policy on cached responses, live. It takes about a minute and is rate limited.</p>"
        "<p><b>No card is green without the harmful half</b>, and no card is green if the "
        "format gate fires. That is the validity contract, and it has refused four times.</p>"
        "<p class='note'>Detection is demonstrated on Glimmer derivatives, where a positive "
        "control can be built. Spark models are black-box baselines: we cannot modify a hosted "
        "endpoint, so we cannot construct a Spark positive control. The judge moves between "
        "runs, so compliance is reported as a range, never a decimal point estimate.</p>",
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
