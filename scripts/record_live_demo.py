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
            "This is the live product. Twelve checkpoints, each with a verdict, a "
            "validity state, and a fingerprint."
        ),
    },
    {
        "name": "verify",
        "narration": (
            "Click Verify. The server recomputes the card from the committed "
            "responses. It matches."
        ),
    },
    {
        "name": "tamper",
        "narration": (
            "Tamper with one number. The fingerprint changes, and verification "
            "fails."
        ),
    },
    {
        "name": "families",
        "narration": (
            "The same ablation, one frozen judge: Qwen zero point nine seven, "
            "Mistral zero point eight one, Glimmer zero point one six. Refusal is "
            "concentrated in Qwen and Mistral, and distributed in Glimmer."
        ),
    },
    {
        "name": "scan",
        "narration": (
            "Scan your own. Upload the response files and get a card."
        ),
    },
    {
        "name": "close",
        "narration": (
            "One card, about two dollars."
        ),
    },
]


def act(page, name: str) -> None:
    if name == "open":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.mouse.wheel(0, 420)
        time.sleep(0.9)
        for _ in range(12):
            page.mouse.wheel(0, 45)
            time.sleep(0.45)
    elif name == "verify":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#m1-ablation").scroll_into_view_if_needed()
        time.sleep(0.8)
        page.locator("form[action='/verify/m1-ablation'] button").first.click()
        page.wait_for_load_state("networkidle", timeout=90000)
        for _ in range(6):
            page.mouse.wheel(0, 40)
            time.sleep(0.5)
        time.sleep(1.0)
    elif name == "tamper":
        page.goto(f"{BASE}/verify/m1-ablation?tamper=1", wait_until="networkidle", timeout=90000)
        time.sleep(1.5)
        page.locator("a[href='/verify/m1-ablation?tamper=1&check=1']").first.click()
        page.wait_for_load_state("networkidle", timeout=90000)
        for _ in range(5):
            page.mouse.wheel(0, 35)
            time.sleep(0.5)
        time.sleep(0.8)
    elif name == "families":
        page.goto(f"{BASE}/families", wait_until="networkidle", timeout=90000)
        time.sleep(1.0)
        for _ in range(30):
            page.mouse.wheel(0, 46)
            time.sleep(0.55)
    elif name == "scan":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#scan").scroll_into_view_if_needed()
        time.sleep(1.0)
        for _ in range(4):
            page.mouse.wheel(0, 30)
            time.sleep(0.5)
    elif name == "close":
        page.goto(f"{BASE}/families", wait_until="networkidle", timeout=90000)
        time.sleep(0.6)
        for _ in range(8):
            page.mouse.wheel(0, 48)
            time.sleep(0.55)


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
