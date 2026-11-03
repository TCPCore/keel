"""Record real browser sessions of the live Space, one clip per chapter."""

from __future__ import annotations

import pathlib
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "video" / "live"
BASE = "https://tomscot-keel.hf.space"
W, H = 1600, 900
SCALE = 2

CURSOR = """
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('dsh-cursor')) return;
  const c = document.createElement('div');
  c.id = 'dsh-cursor';
  c.style.cssText = 'position:fixed;left:50%;top:50%;width:16px;height:16px;border-radius:50%;'
    + 'background:#f5a623;box-shadow:0 0 0 5px rgba(245,166,35,.22);pointer-events:none;'
    + 'z-index:2147483647;transform:translate(-50%,-50%);transition:transform .06s linear';
  document.body.appendChild(c);
  document.addEventListener('mousemove', e => {
    c.style.left = e.clientX + 'px';
    c.style.top = e.clientY + 'px';
  });
  document.addEventListener('mousedown', () => {
    c.style.transform = 'translate(-50%,-50%) scale(1.7)';
  });
  document.addEventListener('mouseup', () => {
    c.style.transform = 'translate(-50%,-50%) scale(1)';
  });
});
"""


def smooth_scroll(page, seconds: float, delta: float | None = None) -> None:
    """Scroll smoothly to the end (or by delta) over the given time."""
    page.evaluate(
        """(args) => new Promise((resolve) => {
            const [ms, delta] = args;
            const start = window.scrollY;
            const max = document.documentElement.scrollHeight - window.innerHeight;
            const end = delta === null ? max : Math.max(0, Math.min(max, start + delta));
            const t0 = performance.now();
            function step(t) {
                const k = Math.min(1, (t - t0) / ms);
                const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
                window.scrollTo(0, start + (end - start) * e);
                if (k < 1) requestAnimationFrame(step); else resolve(true);
            }
            requestAnimationFrame(step);
        })""",
        [int(seconds * 1000), delta],
    )


def click(page, selector: str) -> None:
    el = page.locator(selector).first
    box = el.bounding_box()
    if box:
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=12)
        time.sleep(0.25)
    el.click()
    page.wait_for_load_state("networkidle", timeout=120000)


def act(page, name: str) -> None:
    if name == "open":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        page.mouse.move(640, 360, steps=8)
        smooth_scroll(page, 13)
    elif name == "verify":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#m1-ablation").scroll_into_view_if_needed()
        time.sleep(0.4)
        click(page, "form[action='/verify/m1-ablation'] button")
        smooth_scroll(page, 13)
    elif name == "tamper":
        page.goto(f"{BASE}/verify/m1-ablation?tamper=1", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        smooth_scroll(page, 4)
        try:
            click(page, "a[href='/verify/m1-ablation?tamper=1&check=1']")
        except Exception:
            pass
        smooth_scroll(page, 8)
    elif name == "families":
        page.goto(f"{BASE}/families", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        smooth_scroll(page, 24)
    elif name == "card":
        page.goto(f"{BASE}/card/m1-ablation", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        smooth_scroll(page, 17)
    elif name == "rescore":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#m1-ablation").scroll_into_view_if_needed()
        time.sleep(0.4)
        click(page, "form[action='/rescore/m1-ablation'] button")
        smooth_scroll(page, 6)
    elif name == "scan":
        page.goto(f"{BASE}/scan", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        smooth_scroll(page, 11)
    elif name == "close":
        page.goto(f"{BASE}/guide", wait_until="networkidle", timeout=90000)
        page.locator("h2:has-text('five times')").scroll_into_view_if_needed()
        time.sleep(0.4)
        smooth_scroll(page, 9)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for chapter in ("open", "verify", "tamper", "families", "card", "rescore", "scan", "close"):
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(
                viewport={"width": W, "height": H},
                device_scale_factor=SCALE,
                record_video_dir=str(OUT),
                record_video_size={"width": W * SCALE, "height": H * SCALE},
            )
            page = context.new_page()
            page.add_init_script(CURSOR)
            act(page, chapter)
            video = page.video
            context.close()
            browser.close()
            pathlib.Path(video.path()).replace(OUT / f"{chapter}.webm")
            print(chapter, (OUT / f"{chapter}.webm").stat().st_size, "bytes")


if __name__ == "__main__":
    main()
