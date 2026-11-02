"""Record real browser sessions of the live Space, one clip per chapter."""

from __future__ import annotations

import json
import pathlib
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "video" / "live"
BASE = "https://tomscot-keel.hf.space"
W, H = 1280, 720

CHAPTERS = [
    {
        "name": "open",
        "narration": (
            "This is Keel, a checkpoint validity harness for open-weight models. Twelve "
            "checkpoints, each with a verdict, a validity state, and a fingerprint."
        ),
    },
    {
        "name": "verify",
        "narration": (
            "Click verify. The server recomputes the card from the committed responses: "
            "the drift, the intervals, the verdict, and the fingerprint. It matches."
        ),
    },
    {
        "name": "tamper",
        "narration": (
            "Change one number. The fingerprint no longer matches, the verdict drops to "
            "review, and the tool refuses to certify the measurement."
        ),
    },
    {
        "name": "families",
        "narration": (
            "The same directional ablation, one frozen judge: Qwen between zero point five "
            "one and zero point nine seven, Mistral zero point eight one, Glimmer zero point "
            "one six. Refusal is concentrated in Qwen and Mistral, and distributed in Glimmer."
        ),
    },
    {
        "name": "card",
        "narration": (
            "Every card carries the same six blocks: verdict, drift, harmful, validity, "
            "structure, and limits. Nothing is a claim without its evidence."
        ),
    },
    {
        "name": "rescore",
        "narration": (
            "Re-score with the judge, live. The frozen contract answers again, the rate "
            "matches the card, and the fingerprint still holds. This is the judge running "
            "now, not a replay."
        ),
    },
    {
        "name": "scan",
        "narration": (
            "Scan your own: upload a base and a candidate response file, and the same "
            "contract produces a card."
        ),
    },
    {
        "name": "close",
        "narration": (
            "The tool refuses to certify what it cannot verify. One card, about two dollars."
        ),
    },
]


def wheel(page, steps: int, dy: int, pause: float) -> None:
    for _ in range(steps):
        page.mouse.wheel(0, dy)
        time.sleep(pause)


def act(page, name: str) -> None:
    if name == "open":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        wheel(page, 4, 120, 0.6)
        wheel(page, 14, 42, 0.5)
    elif name == "verify":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#m1-ablation").scroll_into_view_if_needed()
        time.sleep(1.0)
        page.locator("form[action='/verify/m1-ablation'] button").first.click()
        page.wait_for_load_state("networkidle", timeout=90000)
        wheel(page, 14, 42, 0.55)
    elif name == "tamper":
        page.goto(f"{BASE}/verify/m1-ablation?tamper=1", wait_until="networkidle", timeout=90000)
        time.sleep(1.2)
        wheel(page, 6, 40, 0.55)
        try:
            page.locator("a[href='/verify/m1-ablation?tamper=1&check=1']").first.click()
            page.wait_for_load_state("networkidle", timeout=90000)
        except Exception:
            pass
        wheel(page, 10, 40, 0.55)
    elif name == "families":
        page.goto(f"{BASE}/families", wait_until="networkidle", timeout=90000)
        time.sleep(1.0)
        wheel(page, 34, 44, 0.62)
    elif name == "card":
        page.goto(f"{BASE}/card/m1-ablation", wait_until="networkidle", timeout=90000)
        time.sleep(1.0)
        wheel(page, 26, 46, 0.6)
    elif name == "rescore":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#m1-ablation").scroll_into_view_if_needed()
        time.sleep(1.0)
        page.locator("form[action='/rescore/m1-ablation'] button").first.click()
        page.wait_for_load_state("networkidle", timeout=120000)
        time.sleep(1.0)
        wheel(page, 10, 42, 0.55)
    elif name == "scan":
        page.goto(f"{BASE}/scan", wait_until="networkidle", timeout=90000)
        time.sleep(1.0)
        wheel(page, 18, 40, 0.6)
    elif name == "close":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("text=The five refusals").scroll_into_view_if_needed()
        time.sleep(0.8)
        wheel(page, 8, 40, 0.55)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "narration.json").write_text(
        json.dumps({c["name"]: c["narration"] for c in CHAPTERS}, indent=1)
    )
    for chapter in CHAPTERS:
        name = chapter["name"]
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(
                record_video_dir=str(OUT), viewport={"width": W, "height": H}
            )
            page = context.new_page()
            act(page, name)
            video = page.video
            context.close()
            browser.close()
            src = pathlib.Path(video.path())
            dest = OUT / f"{name}.webm"
            src.replace(dest)
            print(name, dest.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
