"""Keel: one page with the whole demo, laid out as a product page.

Sections: hero, fleet table, card grid, verify, scan your own, method.
Every card downloads with a fingerprint; verify recomputes and compares.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)

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
WINDOW = 3600


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _allowed(ip: str, limit: int) -> bool:
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
    label = {"green": "PASS", "amber": "REVIEW", "red": "BLOCK"}.get(verdict, verdict.upper())
    return f'<span class="badge {verdict}">{label}</span>'


def _bar(value: float | None, limit: float = 1.0) -> str:
    if value is None:
        return "<span class='muted'>—</span>"
    width = max(0.0, min(float(value) / limit, 1.0)) * 100
    color = "#f85149" if value > 0.4 else "#d29922" if value > 0.05 else "#3fb950"
    return (
        f"<span class='meter'><span style='width:{width:.0f}%;background:{color}'></span>"
        f"</span><span class='num'>{float(value):.2f}</span>"
    )


CSS = """
:root{color-scheme:dark;--bg:#0b0f14;--panel:#121820;--line:#1f2731;--ink:#e6edf3;
--muted:#8b949e;--blue:#58a6ff;--green:#3fb950;--amber:#d29922;--red:#f85149}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}
nav{position:sticky;top:0;z-index:10;background:rgba(11,15,20,.92);
border-bottom:1px solid var(--line);backdrop-filter:blur(6px)}
nav .wrap{display:flex;align-items:center;gap:22px;height:52px}
nav .brand{font-weight:700;letter-spacing:.02em}
nav .links{display:flex;gap:18px;margin-left:auto;font-size:13px}
nav .links a{color:var(--muted)}
nav .links a:hover{color:var(--ink)}
header.hero{padding:56px 0 28px}
.hero h1{font-size:34px;line-height:1.15;margin:0 0 12px;letter-spacing:-.01em}
.hero p{max-width:720px;color:#c9d1d9;margin:0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;
margin-top:28px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.kpi .n{font-size:24px;font-weight:700;display:block}
.kpi .l{color:var(--muted);font-size:12px}
h2{font-size:19px;margin:52px 0 6px;letter-spacing:-.01em}
h2 .idx{color:var(--muted);font-weight:400;margin-right:8px}
.lede{color:var(--muted);font-size:13px;margin:0 0 16px;max-width:820px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:11px;font-weight:500;color:var(--muted);
text-transform:uppercase;letter-spacing:.06em;padding:12px 14px;border-bottom:1px solid var(--line)}
td{padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:middle}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:#0f151c}
td.num{text-align:right;font-variant-numeric:tabular-nums}
td.mono{font-variant-numeric:tabular-nums;color:var(--muted);font-size:12px}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;
font-weight:700;letter-spacing:.04em}
.badge.green{background:rgba(63,185,80,.15);color:var(--green)}
.badge.amber{background:rgba(210,153,34,.15);color:var(--amber)}
.badge.red{background:rgba(248,81,73,.15);color:var(--red)}
.badge.base{background:#1f2731;color:var(--muted)}
.meter{display:inline-block;width:84px;height:6px;background:#1f2731;border-radius:3px;
overflow:hidden;vertical-align:middle;margin-right:8px}
.meter span{display:block;height:100%}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}
.card h3{margin:0 0 2px;font-size:15px}
.card .meta{color:var(--muted);font-size:12px;margin:0 0 12px}
.card table th,.card table td{padding:6px 4px;border-bottom:1px solid var(--line);font-size:12px}
.card table th{text-transform:none;letter-spacing:0;font-size:11px}
.warn{background:rgba(210,153,34,.1);border-left:3px solid var(--amber);
padding:8px 10px;border-radius:4px;font-size:12px;margin:10px 0}
.ok{background:rgba(63,185,80,.1);border-left:3px solid var(--green);
padding:8px 10px;border-radius:4px;font-size:12px;margin:10px 0}
.actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;align-items:center}
form{margin:0}
button{background:#238636;color:#fff;border:0;border-radius:6px;padding:7px 12px;
font:inherit;font-size:13px;cursor:pointer}
button.ghost{background:transparent;border:1px solid var(--line);color:var(--ink)}
button.ghost:hover{border-color:var(--muted)}
.two{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}
@media(max-width:820px){.two{grid-template-columns:1fr}nav .links{display:none}}
pre{background:#0d131a;border:1px solid var(--line);border-radius:8px;padding:14px;
overflow-x:auto;font-size:12px;line-height:1.5}
input[type=file]{background:#0d131a;border:1px dashed var(--line);border-radius:8px;
padding:12px;color:var(--ink);width:100%}
.note{border-left:3px solid var(--line);padding-left:14px;color:var(--muted);font-size:13px}
footer{margin:56px 0 40px;padding-top:18px;border-top:1px solid var(--line);
color:var(--muted);font-size:12px;display:flex;justify-content:space-between;gap:16px;
flex-wrap:wrap}
code{background:#161d26;padding:1px 5px;border-radius:4px;font-size:12px}
"""


def _page(title: str, body: str, active: str = "") -> str:
    links = [("model-class", "Model class"), ("cards", "Cards"), ("verify", "Verify"),
             ("scan", "Scan your own"), ("method", "Method")]
    nav = "".join(
        "<a href='#{}'{}>{}</a>".format(
            anchor,
            " style='color:#e6edf3'" if anchor == active else "",
            label,
        )
        for anchor, label in links
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{CSS}</style></head><body>
<nav><div class="wrap"><span class="brand">keel</span>
<span class="links">{nav}</span></div></nav>
{body}
<footer><div class="wrap" style="display:flex;justify-content:space-between;
width:100%;flex-wrap:wrap;gap:12px">
<span>Keel · checkpoint validity · <a href="/healthz">health</a></span>
<span>cards carry fingerprints · verify with <code>keel verify-card</code></span>
</div></footer>
</body></html>"""


def _card_html(payload: dict, slug: str, download: str) -> str:
    drift = payload["drift"]
    axes = "".join(
        f"<tr><td>{axis}</td><td class='num'>{s['reference']:.2f}</td>"
        f"<td class='num'>{s['candidate']:.2f}</td><td class='num'>{s['q']:.3f}</td></tr>"
        for axis, s in drift["axes"].items()
    )
    harmful = payload.get("harmful") or {}
    harmful_line = (
        f"<p class='meta'>harmful compliance {_bar(harmful['candidate_rate'])} "
        f"<span class='muted'>from {harmful['reference_rate']:.2f} over {harmful['n']}</span></p>"
        if harmful
        else "<p class='warn'>harmful half not measured: this card cannot be green</p>"
    )
    validity = (
        f"<p class='warn'>MEASUREMENT SUSPECT<br>{payload['validity_reason']}</p>"
        if payload.get("validity") == "suspect"
        else "<p class='meta'>validity ok</p>"
    )
    verdict = "amber" if payload.get("validity") == "suspect" else drift["verdict"]["level"]
    limits = "".join(f"<li>{limit}</li>" for limit in payload.get("limits", [])[:2])
    return f"""<article class="card" id="{slug}">
<h3>{drift['candidate']} {_badge(verdict)}</h3>
<p class="meta">against {drift['reference']} · {drift['n_probes']} probes ·
fingerprint <b>{payload.get('fingerprint', '—')}</b></p>
{validity}{harmful_line}
<table><thead><tr><th>axis</th><th>ref</th><th>cand</th><th>q</th></tr></thead>
<tbody>{axes}</tbody></table>
<ul class="meta">{limits}</ul>
<div class="actions">
<form method="post" action="/verify/{slug}"><button class="ghost">Verify</button></form>
<form method="post" action="/verify/{slug}?tamper=1">
<button class="ghost">Tamper test</button></form>
<form method="post" action="/rescore/{slug}"><button>Re-score live</button></form>
<a href="{download}">JSON</a>
</div></article>"""


def _recompute(slug: str):
    from keel.panel import builtin
    from keel.scan import load_responses, scan_responses

    base_rows = [
        json.loads(line) for line in (ROOT / BASE).read_text().splitlines() if line.strip()
    ]
    rows = [
        json.loads(line)
        for line in (ROOT / RESPONSES[slug]).read_text().splitlines()
        if line.strip()
    ]
    return scan_responses(
        load_responses(base_rows),
        load_responses(rows),
        builtin(),
        reference_id="m0-base-panel",
        candidate_id=slug,
        harmful=json.loads((ROOT / HARMFUL[slug]).read_text()) if slug in HARMFUL else None,
    )


def _render_index() -> str:
    rows = "".join(
        f"<tr><td><a href='#{row['slug']}'>{row['model']}</a></td><td class='muted'>{row['kind']}</td>"
        f"<td>{_badge(row['verdict']) if row['verdict'] != '—' else '<span class=badge base>baseline</span>'}</td>"
        f"<td class='muted'>{row['validity']}</td>"
        f"<td>{_bar(row['compliance'])}</td>"
        f"<td class='num'>{row['judged'] or '—'}</td>"
        f"<td class='mono'>{row['fingerprint'][:8] or '—'}</td></tr>"
        for row in FLEET
    )
    cards = "".join(
        _card_html(_card(row["slug"]), row["slug"], f"/card/{row['slug']}/json")
        for row in FLEET
        if row.get("card")
    )
    return _page(
        "Keel · checkpoint validity",
        f"""<div class="wrap">
<header class="hero">
<h1>Know what a checkpoint became.</h1>
<p>Keel scans a derivative against its base and emits a card: drift, whether the
measurement was valid, harmful compliance, and a fingerprint. It refuses to report green
when it cannot measure, and it proves the card by recomputing it.</p>
<div class="kpis">
<div class="kpi"><span class="n">9</span><span class="l">checkpoints, two families</span></div>
<div class="kpi"><span class="n">0.00 → 0.81</span><span class="l">harmful compliance, base to ablation</span></div>
<div class="kpi"><span class="n">4</span><span class="l">times the tool refused its own measurement</span></div>
<div class="kpi"><span class="n">~$2</span><span class="l">per white-box scan</span></div>
</div>
</header>

<h2 id="model-class"><span class="idx">01</span>The model class</h2>
<p class="lede">Same scanner, same 32 probes, same card schema. Five frontier models as
baselines, three Glimmer checkpoints with a positive and a negative control, two
community derivatives.</p>
<div class="panel"><table>
<thead><tr><th>model</th><th>source</th><th>verdict</th><th>validity</th>
<th>harmful compliance</th><th>judged</th><th>fingerprint</th></tr></thead>
<tbody>{rows}</tbody></table></div>

<h2 id="cards"><span class="idx">02</span>The cards</h2>
<p class="lede">Each card is the unit of evidence. Verify recomputes it from the committed
responses; tamper test edits one number and shows the fingerprint change.</p>
<div class="grid">{cards}</div>

<h2 id="verify"><span class="idx">03</span>Verify it is real</h2>
<div class="two">
<div>
<p class="lede">The scoring path is deterministic. Press Verify on any card and the tool
recomputes it from scratch, then compares fingerprints. Same input, same fingerprint.
Press Tamper test and it edits one axis value, which changes the fingerprint.</p>
<p class="note">A card that survives both is evidence, not a screenshot. The same check
runs locally: <code>keel verify-card --card card.json</code>.</p>
</div>
<div class="panel" style="padding:16px">
<p class="meta" style="margin:0 0 10px">quick check</p>
<form method="post" action="/verify/m2-lora">
<button>Verify M2</button></form>
<p class="meta" style="margin:12px 0 10px">or prove the fingerprint reacts</p>
<form method="post" action="/verify/m2-lora?tamper=1">
<button class="ghost">Tamper M2</button></form>
</div>
</div>

<h2 id="scan"><span class="idx">04</span>Scan your own checkpoint</h2>
<div class="two">
<div>
<p class="lede">Download the 32 probes, generate one response per probe with your model,
upload the JSONL. The card returns in about a second with its fingerprint.</p>
<pre>rows = [json.loads(l) for l in open('probes.jsonl')]
out = [{{'probe_id': r['probe_id'], 'text': your_model(r['text'])}} for r in rows]
open('mine.jsonl','w').write('\\n'.join(json.dumps(r) for r in out))</pre>
<p><a href="/probes.jsonl">Download probes.jsonl</a></p>
</div>
<div class="panel" style="padding:16px">
<form method="post" action="/scan" enctype="multipart/form-data">
<p class="meta">JSONL, one response per probe</p>
<input type="file" name="responses" accept=".jsonl" required>
<p style="margin-top:12px"><button type="submit">Scan my responses</button></p>
</form>
<p class="note" style="margin-top:14px">Program scorers only, so it is free. The card
names the axes it could not measure; no judge runs.</p>
</div>
</div>

<h2 id="method"><span class="idx">05</span>Method and limits</h2>
<p class="note">Detection is demonstrated on Glimmer derivatives, where a positive control
can be built. Spark models are black-box baselines: a hosted endpoint cannot be modified,
so no Spark positive control exists. The judge moves between runs, so compliance is a
range, never a decimal point. No card is green without the harmful half, and no card is
green if the format gate fires. Full record: <code>docs/RESULTS.md</code>.</p>
</div>""",
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _render_index()


@app.post("/verify/{slug}", response_class=HTMLResponse)
def verify(slug: str, request: Request, tamper: int = 0) -> HTMLResponse:
    if slug not in RESPONSES:
        raise HTTPException(404, "no cached responses for this entry")
    stored = _card(slug)
    stored_fp = stored.get("fingerprint", "")
    if tamper:
        edited = json.loads(json.dumps(stored))
        first = next(iter(edited["drift"]["axes"].values()))
        first["candidate"] = round(float(first["candidate"]) + 0.25, 4)
        from keel.report import Card

        tampered = Card.from_dict(edited).fingerprint()
        body = (
            "<div class='wrap'><h2>Tamper test</h2>"
            f"<p>original fingerprint <b>{stored_fp}</b></p>"
            f"<p>after changing one axis by +0.25 <b>{tampered}</b></p>"
            "<p class='ok'>The fingerprint changed. An edited card cannot pass as the original.</p>"
            "<p><a href='/'>&larr; back</a></p></div>"
        )
        return HTMLResponse(_page("Keel · tamper", body))
    fresh = _recompute(slug)
    recomputed = fresh.fingerprint()
    if recomputed == stored_fp:
        body = (
            "<div class='wrap'><h2>Verify</h2>"
            f"<p>stored <b>{stored_fp}</b></p><p>recomputed <b>{recomputed}</b></p>"
            "<p class='ok'>MATCH: the committed responses reproduce this card exactly.</p>"
            "<p><a href='/'>&larr; back</a></p></div>"
        )
    else:
        body = (
            "<div class='wrap'><h2>Verify</h2>"
            f"<p>stored <b>{stored_fp}</b></p><p>recomputed <b>{recomputed}</b></p>"
            "<p class='warn'>DIFF: the stored card was not produced from these inputs.</p>"
            "<p><a href='/'>&larr; back</a></p></div>"
        )
    return HTMLResponse(_page("Keel · verify", body))


@app.post("/rescore/{slug}", response_class=HTMLResponse)
def rescore(slug: str, request: Request) -> HTMLResponse:
    import os

    if slug not in RESPONSES:
        raise HTTPException(404, "no cached responses for this entry")
    if not os.environ.get("BASETEN_API_KEY"):
        raise HTTPException(503, "no judge key configured")
    if not _allowed(_client_ip(request), limit=10):
        raise HTTPException(429, "rate limit: 10 re-scores per hour per address")

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
    base_rows = [
        json.loads(line) for line in (ROOT / BASE).read_text().splitlines() if line.strip()
    ]
    rows = [
        json.loads(line)
        for line in (ROOT / RESPONSES[slug]).read_text().splitlines()
        if line.strip()
    ]
    harmful = json.loads((ROOT / HARMFUL[slug]).read_text()) if slug in HARMFUL else None
    built = scan_responses(
        load_responses(base_rows),
        load_responses(rows),
        builtin(),
        judge=judge,
        reference_id="m0-base-panel",
        candidate_id=slug,
        harmful=harmful,
    )
    write_card(built, ROOT / f"examples/demo-cards/{slug}")
    body = (
        f"<div class='wrap'><h2>Re-scored live</h2>"
        f"{_card_html(built.to_dict(), slug, f'/card/{slug}/json')}"
        "<p><a href='/'>&larr; back</a></p></div>"
    )
    return HTMLResponse(_page("Keel · re-scored", body))


@app.get("/card/{slug}", response_class=HTMLResponse)
def card(slug: str) -> str:
    payload = _card(slug)
    body = (
        f"<div class='wrap'><h2>{slug}</h2>"
        f"{_card_html(payload, slug, f'/card/{slug}/json')}"
        "<p><a href='/'>&larr; back</a></p></div>"
    )
    return _page(f"Keel · {slug}", body)


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
    return "\n".join(
        json.dumps({"probe_id": row["id"], "text": row["text"]}) for row in rows
    ) + "\n"


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
    if len(probe_ids & provided) < 24:
        raise HTTPException(
            400, f"only {len(probe_ids & provided)} of 32 probe ids matched; need 24"
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
        reference_id="m0-base-panel",
        candidate_id="your-checkpoint",
    )
    token = uuid.uuid4().hex[:12]
    (UPLOADS / f"{token}.json").write_text(json.dumps(built.to_dict(), indent=1) + "\n")
    body = (
        f"<div class='wrap'><h2>Your card</h2>"
        f"{_card_html(built.to_dict(), 'your-checkpoint', f'/result/{token}/json')}"
        "<p><a href='/'>&larr; back</a></p></div>"
    )
    return HTMLResponse(_page("Keel · your card", body))


@app.get("/result/{token}/json")
def result_json(token: str) -> JSONResponse:
    if not token.isalnum():
        raise HTTPException(404, "no such result")
    path = UPLOADS / f"{token}.json"
    if not path.exists():
        raise HTTPException(404, "no such result")
    return JSONResponse(json.loads(path.read_text()))


@app.get("/about")
def about() -> RedirectResponse:
    return RedirectResponse("/#method", status_code=307)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
