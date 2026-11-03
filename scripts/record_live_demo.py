"""Record real browser sessions of the live Space, one clip per chapter."""

from __future__ import annotations

import pathlib
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "video" / "live"
BASE = "https://tomscot-keel.hf.space"
W, H = 1600, 900

CURSOR = """
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('dsh-cursor')) return;
  const c = document.createElement('div');
  c.id = 'dsh-cursor';
  c.style.cssText = 'position:fixed;left:-100px;top:-100px;width:16px;height:16px;'
    + 'border-radius:50%;background:#f5a623;box-shadow:0 0 0 5px rgba(245,166,35,.22);'
    + 'pointer-events:none;z-index:2147483647;transform:translate(-50%,-50%);'
    + 'transition:transform .06s linear';
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

CHAPTERS = [
    ("open", 13),
    ("verify", 11),
    ("tamper", 7),
    ("families", 18),
    ("scan", 10),
    ("rescore", 6),
    ("card", 21),
    ("close", 8),
]


def wheel_scroll(page, seconds: float, dy: int = 22, pause: float = 0.35) -> None:
    """Scroll with real wheel events at a constant rate."""
    steps = max(1, int(seconds / pause))
    for _ in range(steps):
        page.mouse.wheel(0, dy)
        time.sleep(pause)


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
                const e = k;
                window.scrollTo(0, start + (end - start) * e);
                if (k < 1) requestAnimationFrame(step); else resolve(true);
            }
            requestAnimationFrame(step);
        })""",
        [int(seconds * 1000), delta],
    )


def zoom(page, seconds: float, amount: float = 0.10) -> None:
    """Slowly scale the content so a one-screen page still moves."""
    page.evaluate(
        """(args) => new Promise((resolve) => {
            const [ms, amount] = args;
            const el = document.querySelector('.doc') || document.body;
            el.style.transformOrigin = '50% 0%';
            const t0 = performance.now();
            function step(t) {
                const k = Math.min(1, (t - t0) / ms);
                el.style.transform = 'scale(' + (1 + amount * k) + ')';
                if (k < 1) requestAnimationFrame(step); else resolve(true);
            }
            requestAnimationFrame(step);
        })""",
        [int(seconds * 1000), amount],
    )


def click(page, selector: str) -> None:
    el = page.locator(selector).first
    box = el.bounding_box()
    if box:
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=12)
        time.sleep(0.25)
    el.click()
    page.wait_for_load_state("networkidle", timeout=120000)


def act(page, name: str, scroll: int) -> None:
    if name == "open":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        page.mouse.move(700, 400, steps=8)
        wheel_scroll(page, scroll)
    elif name == "verify":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#m1-ablation").scroll_into_view_if_needed()
        time.sleep(0.4)
        click(page, "form[action='/verify/m1-ablation'] button")
        zoom(page, scroll)
    elif name == "tamper":
        page.goto(f"{BASE}/verify/m1-ablation?tamper=1", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        try:
            click(page, "a[href='/verify/m1-ablation?tamper=1&check=1']")
        except Exception:
            pass
        zoom(page, scroll)
    elif name == "families":
        page.goto(f"{BASE}/families", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        wheel_scroll(page, scroll, dy=18)
    elif name == "scan":
        page.goto(f"{BASE}/scan", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        zoom(page, scroll)
    elif name == "rescore":
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=90000)
        page.locator("#m1-ablation").scroll_into_view_if_needed()
        time.sleep(0.4)
        click(page, "form[action='/rescore/m1-ablation'] button")
        smooth_scroll(page, scroll)
    elif name == "card":
        page.goto(f"{BASE}/card/m1-ablation", wait_until="networkidle", timeout=90000)
        time.sleep(0.4)
        page.evaluate(
            """(ms) => new Promise((resolve) => {
                const el = document.querySelector('.doc') || document.body;
                el.style.transformOrigin = '50% 0%';
                const t0 = performance.now();
                function step(t) {
                    const k = Math.min(1, (t - t0) / ms);
                    el.style.transform = 'scale(' + (1 + 0.10 * k) + ')';
                    if (k < 1) requestAnimationFrame(step); else resolve(true);
                }
                requestAnimationFrame(step);
            })""",
            int(scroll * 1000),
        )
    elif name == "close":
        page.goto(f"{BASE}/guide", wait_until="networkidle", timeout=90000)
        page.locator("h2:has-text('five times')").scroll_into_view_if_needed()
        time.sleep(0.4)
        wheel_scroll(page, scroll, dy=30)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, scroll in CHAPTERS:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(
                viewport={"width": W, "height": H},
                record_video_dir=str(OUT),
                record_video_size={"width": W, "height": H},
            )
            page = context.new_page()
            page.add_init_script(CURSOR)
            act(page, name, scroll)
            video = page.video
            context.close()
            browser.close()
            pathlib.Path(video.path()).replace(OUT / f"{name}.webm")
            print(name, (OUT / f"{name}.webm").stat().st_size, "bytes")


if __name__ == "__main__":
    main()
