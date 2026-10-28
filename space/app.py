"""Keel Space: fleet view, card pages, and a live scan of the judge's own responses.

Modes, each labelled:

  fleet     nine checkpoints from committed cards and survey results
  re-score  re-run judging, statistics, the format gate and policy on cached responses
  upload    scan a JSONL the visitor generated from their own checkpoint, live

The upload path uses the program scorers only, so it costs nothing and returns in
seconds. Its card says which axes were not measured, because no judge ran.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

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
UPLOADS = Path("/tmp/keel-uploads")
UPLOADS.mkdir(exist_ok=True)

app = FastAPI(title="Keel")
HITS: dict[str, list[float]] = defaultdict(list)
LIMIT = 10
WINDOW = 3600


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _allowed(ip: str, limit: int = LIMIT) -> bool:
    now = time.time()
    HITS[ip] = [stamp for stamp in HITS[ip] if now - stamp < WINDOW]
    if len(HITS[ip]) >= limit:
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
.warn{{background:#3d2b00;border-left:3px solid #d29922;padding:8px 10px;border-radius:4px;font-size:12px}}
button{{background:#238636;color:#fff;border:0;border-radius:6px;padding:8px 14px;font:inherit;cursor:pointer}}
input[type=file]{{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:8px;color:#e6edf3}}
pre{{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px;overflow-x:auto;font-size:12px}}
.note{{border-left:3px solid #30363d;padding-left:12px;color:#8b949e;font-size:13px;max-width:900px}}
</style></head><body>{body}</body></html>"""


def _card_html(payload: dict, slug: str, download: str) -> str:
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
    limits = "".join(f"<li>{limit}</li>" for limit in payload.get("limits", [])[:4])
    return (
        f"<p><a href='/'>&larr; fleet</a></p>"
        f"<h1>{drift['candidate']}</h1>"
        f"<p class='muted'>against {drift['reference']} · {drift['n_probes']} probes · "
        f"fingerprint {payload.get('fingerprint', '—')}</p>"
        f"<p>{_badge(verdict)}</p>{validity}{harmful_line}"
        f"<table><thead><tr><th>axis</th><th>ref</th><th>cand</th><th>q</th></tr></thead>"
        f"<tbody>{axes}</tbody></table>"
        f"<p><a href='{download}'>Download JSON</a></p>"
        f"<ul class='muted'>{limits}</ul>"
    )


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
        f"<p><a href='/try'><b>Scan your own checkpoint</b></a> · "
        f"<a href='/probes.jsonl'>probe panel</a> · <a href='/about'>method</a></p>"
        f"<table><thead><tr><th>model</th><th>source</th><th>verdict</th><th>validity</th>"
        f"<th>harmful compliance</th><th>judged</th></tr></thead><tbody>{rows}</tbody></table>"
        "<p class='note'>Five Spark and Wonder rows are baselines. The three Glimmer rows are "
        "cards with a positive and a negative control. <b>Scan your own</b> takes a JSONL you "
        "generate from your checkpoint and returns a card in seconds.</p>",
    )


@app.get("/card/{slug}", response_class=HTMLResponse)
def card(slug: str) -> str:
    payload = _card(slug)
    return _page(f"Keel · {slug}", _card_html(payload, slug, f"/card/{slug}/json"))


@app.get("/card/{slug}/json")
def card_json(slug: str) -> JSONResponse:
    return JSONResponse(_card(slug))


@app.get("/probes.jsonl", response_class=PlainTextResponse)
def probes() -> str:
    rows = [
        json.loads(line)
        for line in (ROOT / "src/keel/data/panel-v0.1.jsonl").read_text().splitlines()
        if line.strip()
    ]
    return "\n".join(json.dumps({"probe_id": row["id"], "text": row["text"]}) for row in rows) + "\n"


@app.get("/try", response_class=HTMLResponse)
def try_page() -> str:
    return _page(
        "Keel · scan your own",
        "<h1>Scan your own checkpoint</h1>"
        "<p>Three steps. No GPU on our side, and no upload of weights.</p>"
        "<h2>1. Get the probes</h2>"
        "<p><a href='/probes.jsonl'>Download probes.jsonl</a>, 32 probes with ids and text.</p>"
        "<h2>2. Generate one response per probe</h2>"
        "<pre>python - &lt;&lt;'PY'\n"
        "import json\n"
        "rows = [json.loads(l) for l in open('probes.jsonl')]\n"
        "out = []\n"
        "for row in rows:\n"
        "    reply = your_model(row['text'])   # your checkpoint, your harness\n"
        "    out.append({'probe_id': row['probe_id'], 'text': reply})\n"
        "open('mine.jsonl','w').write('\\n'.join(json.dumps(r) for r in out))\n"
        "</pre>"
        "<h2>3. Upload it</h2>"
        "<form method='post' action='/scan' enctype='multipart/form-data'>"
        "<p><input type='file' name='responses' accept='.jsonl' required> "
        "<button type='submit'>Scan</button></p>"
        "</form>"
        "<p class='note'>Scoring uses the program scorers only, so it is free and takes "
        "seconds. The card will say which axes were not measured, because no judge ran. "
        "For the full card, run <code>keel scan</code> locally with your own judge.</p>",
    )


@app.post("/scan", response_class=HTMLResponse)
async def scan(request: Request, responses: UploadFile = File(...)) -> HTMLResponse:
    ip = _client_ip(request)
    if not _allowed(ip, limit=5):
        raise HTTPException(429, "rate limit: 5 scans per hour per address")

    data = await responses.read()
    if len(data) > 2_000_000:
        raise HTTPException(413, "file too large; 2 MB is enough for 32 responses")
    try:
        rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, f"not valid JSONL: {exc}") from exc

    probe_ids = {
        json.loads(line)["id"]
        for line in (ROOT / "src/keel/data/panel-v0.1.jsonl").read_text().splitlines()
        if line.strip()
    }
    provided = {
        str(row.get("probe_id"))
        for row in rows
        if isinstance(row, dict) and row.get("probe_id") is not None
    }
    matched = probe_ids & provided
    if len(matched) < 24:
        raise HTTPException(
            400, f"only {len(matched)} of 32 probe ids matched; expected at least 24"
        )

    from keel.panel import builtin
    from keel.scan import load_responses, scan_responses

    base_rows = [
        json.loads(line) for line in (ROOT / BASE).read_text().splitlines() if line.strip()
    ]
    clean = [
        {"probe_id": str(row["probe_id"]), "text": str(row.get("text", ""))}
        for row in rows
        if isinstance(row, dict) and row.get("probe_id") in probe_ids
    ]
    built = scan_responses(
        load_responses(base_rows),
        load_responses(clean),
        builtin(),
        reference_id="m0-base",
        candidate_id="your-checkpoint",
    )
    token = uuid.uuid4().hex[:12]
    (UPLOADS / f"{token}.json").write_text(json.dumps(built.to_dict(), indent=1) + "\n")
    return HTMLResponse(
        _page(
            "Keel · your card",
            _card_html(built.to_dict(), "your-checkpoint", f"/result/{token}/json"),
        )
    )


@app.get("/result/{token}/json")
def result_json(token: str) -> JSONResponse:
    if not token.isalnum():
        raise HTTPException(404, "no such result")
    path = UPLOADS / f"{token}.json"
    if not path.exists():
        raise HTTPException(404, "no such result")
    return JSONResponse(json.loads(path.read_text()))


@app.get("/about", response_class=HTMLResponse)
def about() -> str:
    return _page(
        "Keel · method",
        "<h1>Method and limits</h1>"
        "<p>Keel scans a checkpoint and emits a card: verdict, validity, harmful compliance, "
        "limits and a fingerprint. This page runs the same scanner on nine Meta checkpoints. "
        "Five are survey baselines, three are Glimmer cards with controls.</p>"
        "<p><b>Scan your own</b> runs the same scoring path on your responses, with the "
        "program scorers only, so the card names the axes it could not measure.</p>"
        "<p><b>No card is green without the harmful half</b>, and no card is green if the "
        "format gate fires. That is the validity contract, and it has refused four times.</p>"
        "<p class='note'>Detection is demonstrated on Glimmer derivatives, where a positive "
        "control can be built. Spark models are black-box baselines: we cannot modify a hosted "
        "endpoint, so no Spark positive control exists. The judge moves between runs, so "
        "compliance is reported as a range.</p>",
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
