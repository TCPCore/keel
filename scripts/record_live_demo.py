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
            "This is the live product, not a mockup. Twelve checkpoints across four "
            "families. Every row carries a verdict, a validity state, harmful compliance, "
            "and a fingerprint."
        ),
    },
    {
        "name": "verify",
        "narration": (
            "Click Verify on any card. The server recomputes it from the committed "
            "responses. Stored and recomputed match, so the numbers were reproduced, not "
            "screenshotted."
        ),
    },
    {
        "name": "tamper",
        "narration": (
            "Now tamper with one number. The fingerprint changes. Verify the tampered card "
            "and it fails, so an edited card cannot pass as the original."
        ),
    },
    {
        "name": "families",
        "narration": (
            "The Families page is the discovery. The same ablation, one frozen judge: "
            "Qwen zero point nine seven, Mistral zero point eight one, Glimmer zero point "
            "one six. Refusal is concentrated in Qwen and Mistral, and distributed in "
            "Glimmer."
        ),
    },
    {
        "name": "scan",
        "narration": (
            "Scan your own. Upload the response files, and Keel returns a card under the "
            "same frozen contract."
        ),
    },
    {
        "name": "close",
        "narration": (
            "One command, one card, about two dollars. The only checkpoints that move are "
            "the ones whose weights moved."
        ),
    },
]


def act(page, name: str) -> None:
    if name == "open":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.mouse.wheel(0, 650)
        time.sleep(1.8)
    elif name == "verify":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#m1-ablation").scroll_into_view_if_needed()
        time.sleep(0.8)
        page.locator("form[action='/verify/m1-ablation'] button").first.click()
        page.wait_for_load_state("networkidle", timeout=90000)
        time.sleep(2.0)
    elif name == "tamper":
        page.goto(f"{BASE}/verify/m1-ablation?tamper=1", wait_until="networkidle", timeout=90000)
        time.sleep(2.2)
        page.locator("a[href='/verify/m1-ablation?tamper=1&check=1']").first.click()
        page.wait_for_load_state("networkidle", timeout=90000)
        time.sleep(2.0)
    elif name == "families":
        page.goto(f"{BASE}/families", wait_until="networkidle", timeout=90000)
        time.sleep(2.5)
        page.mouse.wheel(0, 420)
        time.sleep(1.8)
    elif name == "scan":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#scan").scroll_into_view_if_needed()
        time.sleep(2.5)
    elif name == "close":
        page.goto(f"{BASE}/families", wait_until="networkidle", timeout=90000)
        page.mouse.wheel(0, 380)
        time.sleep(2.5)


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
