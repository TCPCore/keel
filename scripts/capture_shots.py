"""Re-capture the video shots from the live Space (and two terminal slides)."""

from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHOTS = ROOT / "video" / "shots"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE = "https://tomscot-keel.hf.space"

PAGES = {
    "hero": f"{BASE}/",
    "families": f"{BASE}/families",
    "cards": f"{BASE}/#cards",
    "card": f"{BASE}/card/m1-ablation",
    "verify": f"{BASE}/verify/m1-ablation",
    "tamper": f"{BASE}/verify/m1-ablation?tamper=1",
    "guide": f"{BASE}/guide",
    "table": f"{BASE}/families",
}

TERMINAL = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{margin:0;width:1600px;height:900px;background:#0d1117;color:#e6edf3;
font:17px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;padding:56px 64px;box-sizing:border-box}
.prompt{color:#3fb950}.dim{color:#8b949e}.ok{color:#3fb950}.amber{color:#d29922}
.line{margin:6px 0}
</style></head><body>
{body}
</body></html>"""

BUILD_BODY = """
<div class="line"><span class="prompt">$</span> keel selftest</div>
<div class="line dim">  panel 32/32 · scorers 5/5 · policy 4 rules ·
<span class="ok">ok</span></div>
<div class="line"><span class="prompt">$</span> keel scan --reference m0-base
--candidate m2-lora</div>
<div class="line dim">  code rate 6% → 91% · format gate fired ·
<span class="amber">validity: suspect</span></div>
<div class="line"><span class="prompt">$</span> keel policy --card m2-lora</div>
<div class="line dim">  missing harmful half → <span class="amber">BLOCK</span>
(a card without it cannot pass)</div>
<div class="line"><span class="prompt">$</span> keel verify-card --card m2-lora</div>
<div class="line dim">  fingerprint recomputed · <span class="ok">MATCH</span></div>
"""

RUN_BODY = """
<div class="line dim">12:28:05  1/32 h00 937 chars</div>
<div class="line dim">12:28:27  2/32 h01 951 chars</div>
<div class="line dim">12:29:12  4/32 h03 918 chars</div>
<div class="line dim">12:33:18 16/32 h15 947 chars</div>
<div class="line dim">12:39:38 32/32 h31 837 chars</div>
<div class="line">&nbsp;</div>
<div class="line"><span class="ok">result</span>   5/32 compliant · 0.156 ·
95% CI [0.06, 0.33]</div>
<div class="line"><span class="ok">verify</span>   MATCH · fingerprint 5c57aaf03cebe9c2</div>
<div class="line dim">frozen judge muse-spark-1.3 · answer-only · 3-repeat majority</div>
"""


def shot(name: str, url: str) -> None:
    out = SHOTS / f"{name}.png"
    subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--window-size=1600,900", "--virtual-time-budget=4000",
            f"--screenshot={out}", url,
        ],
        check=True, capture_output=True,
    )
    print("captured", name, out.stat().st_size, "bytes")


def terminal(name: str, body: str) -> None:
    html = SHOTS.parent / "build" / f"{name}.html"
    html.parent.mkdir(exist_ok=True)
    html.write_text(TERMINAL.replace("{body}", body))
    out = SHOTS / f"{name}.png"
    subprocess.run(
        [
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--window-size=1600,900", f"--screenshot={out}", html.as_uri(),
        ],
        check=True, capture_output=True,
    )
    print("rendered terminal", name, out.stat().st_size, "bytes")


def main() -> None:
    SHOTS.mkdir(exist_ok=True)
    terminal("build", BUILD_BODY)
    terminal("run", RUN_BODY)
    for name, url in PAGES.items():
        shot(name, url)


if __name__ == "__main__":
    main()
