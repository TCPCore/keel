"""Stress the Space: every endpoint and every failure mode a judge might hit.

    python scripts/stress_space.py --url https://tomscot-keel.hf.space
    python scripts/stress_space.py --url http://127.0.0.1:8000 --rescore

Exits non-zero if any check fails, so it can gate a deploy.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS: list[str] = []
RESULTS: list[tuple[str, bool, str]] = []


def _req(method: str, url: str, data: bytes | None = None, headers: dict | None = None):
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            text = response.read().decode("utf-8", "replace")
            return response.status, text, time.time() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), time.time() - started
    except Exception as exc:  # noqa: BLE001
        return 0, f"error: {exc}", time.time() - started


def _req_bytes(url: str):
    try:
        with urllib.request.urlopen(url, timeout=180) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    if not ok:
        FAILS.append(name)
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'  ' + detail if detail else ''}")


def multipart(field: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = "----keel" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; "
        f"filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def run(url: str, rescore: bool) -> int:
    base = url.rstrip("/")
    print(f"stress: {base}")

    status, body, ms = _req("GET", f"{base}/")
    check("GET / 200", status == 200, f"{status} {ms:.2f}s")
    check("hero renders", "checkpoint became" in body and "class=\"eyebrow\"" in body)
    check("hero links video", "/demo.mp4" in body)
    check("light theme default", "color-scheme:light" in body)
    check("theme toggle", 'id="theme"' in body)
    check("fleet table has policy column", "policy" in body)
    check(
        "verdict driver line present",
        "Verdict is driven by harmful compliance and policy" in body,
    )
    check("policy reasons present", "exceeds" in body or "format changed" in body)
    check("access anchor target", 'id="access"' in body)
    check("access nav link", "#access" in body)
    check("access form on the page", 'action="/access"' in body)

    status, body, _ = _req("GET", f"{base}/probes.jsonl")
    lines = [line for line in body.splitlines() if line.strip()]
    ids = [json.loads(line)["probe_id"] for line in lines]
    check("probes 32 lines", len(lines) == 32, str(len(lines)))
    check("probes unique", len(set(ids)) == len(ids))

    for slug in (
        "m0-base",
        "m1-ablation",
        "m2-lora",
        "heretic",
        "derivative-d",
        "qwen-ablated",
        "qwen-community",
        "mistral-abl",
    ):
        status, body, _ = _req("GET", f"{base}/card/{slug}")
        check(f"card {slug} 200", status == 200, str(status))
        check(f"card {slug} fingerprint", "fingerprint" in body)
        status, body, _ = _req("GET", f"{base}/card/{slug}/json")
        ok = status == 200 and json.loads(body).get("schema_version") == 2
        check(f"card {slug} json v2", ok, str(status))

    for _ in range(3):
        for slug in ("m0-base", "m2-lora", "heretic"):
            status, body, _ = _req("POST", f"{base}/verify/{slug}")
            check(f"verify {slug} MATCH", status == 200 and "MATCH" in body, str(status))

    status, body, _ = _req("POST", f"{base}/verify/m2-lora?tamper=1")
    check("tamper changes fingerprint", status == 200 and "fingerprint changed" in body.lower())

    status, body, _ = _req("POST", f"{base}/verify/nope")
    check("verify unknown 404", status == 404, str(status))

    panel = (ROOT / "examples/responses/m2-lora-panel.jsonl").read_bytes()
    fps = []
    for _ in range(2):
        data, ctype = multipart("responses", "mine.jsonl", panel)
        status, body, _ = _req("POST", f"{base}/scan", data, {"Content-Type": ctype})
        check("scan valid 200", status == 200, str(status))
        fp = body.split("fingerprint <b>")[1].split("<")[0] if "fingerprint <b>" in body else ""
        fps.append(fp)
    check("scan deterministic", len(set(fps)) == 1 and fps[0], f"{fps}")

    data, ctype = multipart("responses", "bad.jsonl", b"not json\n")
    status, _, _ = _req("POST", f"{base}/scan", data, {"Content-Type": ctype})
    check("scan invalid json 400", status == 400, str(status))

    data, ctype = multipart("responses", "short.jsonl", b'{"probe_id":"s01","text":"x"}\n')
    status, body, _ = _req("POST", f"{base}/scan", data, {"Content-Type": ctype})
    check("scan too few probes 400", status == 400, str(status))

    data, ctype = multipart("responses", "empty.jsonl", b"")
    status, _, _ = _req("POST", f"{base}/scan", data, {"Content-Type": ctype})
    check("scan empty 400", status == 400, str(status))

    status, _, _ = _req("POST", f"{base}/scan")
    check("scan no file 4xx", 400 <= status < 500, str(status))

    status, body, _ = _req("GET", f"{base}/card/unknown")
    check("card unknown 404", status == 404, str(status))

    status, body, _ = _req("GET", f"{base}/healthz")
    check("healthz", status == 200 and json.loads(body).get("ok") is True)

    status, body, _ = _req("GET", f"{base}/demo.mp4")
    check("video served", status == 200 and "video" in body.lower()[:200], str(status))

    status, body, _ = _req("GET", f"{base}/guide")
    check("docs page", status == 200 and "How to read a card" in body, str(status))

    status, body, _ = _req("GET", f"{base}/access")
    check("access page", status == 200 and "Request access" in body)
    check("access nav links back", "href='/#model-class'" in body)
    check("baseline rows not linked", "href='#muse" not in body)

    form = urllib.parse.urlencode(
        {"name": "Stress", "org": "Test", "email": "stress@example.com", "purpose": "safety audit"}
    ).encode()
    status, body, _ = _req("POST", f"{base}/access", form,
                           {"Content-Type": "application/x-www-form-urlencoded"})
    check("access submit", status == 200 and "Request id" in body, str(status))

    bad = urllib.parse.urlencode({"name": "x", "org": "y", "email": "nope"}).encode()
    status, _, _ = _req("POST", f"{base}/access", bad,
                        {"Content-Type": "application/x-www-form-urlencoded"})
    check("access bad email 400", status == 400, str(status))

    status, body, _ = _req("GET", f"{base}/manifest.json")
    ok = status == 200 and len(json.loads(body).get("withheld", {})) == 4
    check("manifest with hashes", ok, str(status))

    status, raw = _req_bytes(f"{base}/bundle.zip")
    check("bundle.zip 200", status == 200 and raw[:2] == b"PK", str(status))
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("MANIFEST.json"))
        hashes_ok = all(
            __import__("hashlib").sha256(archive.read(name)).hexdigest()
            == meta["sha256"]
            for name, meta in manifest["files"].items()
        )
        text = b" ".join(archive.read(name) for name in names if not name.endswith(".jsonl"))
    check("bundle files generic", all(
        "responses/" in name or name in ("MANIFEST.json", "PROBES.jsonl", "VERIFY.md")
        for name in names), str(names[:3]))
    check("bundle hashes match", hashes_ok)
    check(
        "bundle has no source links",
        b"huggingface.co/" not in text and b"SOURCES.md" not in text,
    )

    if rescore:
        status, before, _ = _req("GET", f"{base}/card/m1-ablation/json")
        fp_before = json.loads(before).get("fingerprint")
        status, body, secs = _req("POST", f"{base}/rescore/m1-ablation")
        check("rescore responds", status in (200, 429), f"{status} {secs:.1f}s")
        if status == 200:
            fp_live = (
                body.split("fingerprint <b>")[1].split("<")[0]
                if "fingerprint <b>" in body
                else ""
            )
            check("rescore produced a live card", bool(fp_live), fp_live)
            check("live card differs from committed", fp_live != fp_before,
                  f"{fp_before} -> {fp_live}")
        else:
            check("rescore rate limited after repeated calls", True, "429, expected")
        status, body, _ = _req("POST", f"{base}/verify/m1-ablation")
        check("verify still MATCH after rescore", "MATCH" in body, str(status))

    def hit(_):
        return _req("POST", f"{base}/verify/m2-lora")[0]

    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(hit, range(6)))
    check("concurrent verify stable", all(code == 200 for code in codes), str(codes))

    print(f"\n{sum(1 for _, ok, _ in RESULTS if ok)}/{len(RESULTS)} checks passed")
    if FAILS:
        print("failures: " + ", ".join(FAILS))
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://tomscot-keel.hf.space")
    parser.add_argument("--rescore", action="store_true", help="also exercise the judge path")
    args = parser.parse_args()
    return run(args.url, args.rescore)


if __name__ == "__main__":
    raise SystemExit(main())
