"""Build the annotated demo video from captured shots, narration and captions."""

from __future__ import annotations

import html
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
SHOTS = ROOT / "shots"
BUILD = ROOT / "build"
FF = "/tmp/ffm/node_modules/ffmpeg-static/ffmpeg"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SCENES = [
    (
        "hero",
        "The gap",
        "Meta checks the base model before release. Its runtime guards check the "
        "conversation after deployment. Nothing checks the derivative artifact in "
        "between. That is the gap Keel fills.",
        "The gap: the derivative artifact",
    ),
    (
        "build",
        "Built in the open",
        "The build is four commands. A selftest, a scan that compares two response sets, a "
        "policy decision, and a verifier. The policy here blocks, because this card has no "
        "harmful half. That refusal is the product.",
        "Built in the open · selftest, scan, verify",
    ),
    (
        "run",
        "The run",
        "This is a real run. A thirty billion parameter open model, thirty two harmful "
        "probes, timestamped from twelve twenty eight to twelve thirty nine. It answered "
        "twenty nine of them. The scan cost about two dollars.",
        "32 harmful probes · 29 answered · 11 minutes",
    ),
    (
        "table",
        "The families",
        "One table, four families. Packaging changes stay at zero compliance. Behavioural "
        "changes do not. Zero point eight one on Glimmer, zero point nine one on Qwen, "
        "zero point seven eight on Mistral. Two of those derivatives were built by "
        "someone else.",
        "Four families · only behavioural edits move",
    ),
    (
        "cards",
        "The cards",
        "Every checkpoint gets a card. What moved, whether the measurement was valid, how "
        "often it complied, and a fingerprint computed from the card itself.",
        "Drift, validity, compliance, fingerprint",
    ),
    (
        "card",
        "A card",
        "Each card is the evidence for one checkpoint. What moved, whether the measurement "
        "was valid, how often it complied, and a fingerprint computed from the card itself.",
        "Drift, validity, compliance, fingerprint",
    ),
    (
        "verify",
        "Verify",
        "Verify recomputes the card from the committed responses. Match means the numbers "
        "were reproduced, not screenshotted.",
        "Verify · recomputed, not stored",
    ),
    (
        "tamper",
        "Tamper",
        "Tamper with one number and the fingerprint changes. That is why an edited card "
        "cannot pass as the original.",
        "Tamper · one number, new fingerprint",
    ),
    (
        "guide",
        "Reproduce",
        "Everything is reproducible. The probes, the responses, the verifier, the link "
        "checker, the stress suite. A judge can rerun the whole thing.",
        "Reproducible · probes, responses, checks",
    ),
    (
        "cards",
        "Close",
        "One command, one card. Two dollars, twenty minutes. The only checkpoints that "
        "move are the ones whose weights moved.",
        "Two dollars · twenty minutes · one card",
    ),
]

SLIDE = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0}}
body{{width:1600px;height:900px;overflow:hidden;background:#000;
font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",sans-serif}}
.bg{{position:absolute;inset:0;background:url('{image}') center/cover no-repeat}}
.shade{{position:absolute;inset:0;background:linear-gradient(180deg,
rgba(0,0,0,0) 0%,rgba(0,0,0,0) 52%,rgba(0,0,0,.86) 100%)}}
.text{{position:absolute;left:44px;right:44px;bottom:56px;color:#fff}}
.kicker{{font-size:18px;letter-spacing:.14em;text-transform:uppercase;opacity:.7;
margin-bottom:12px}}
.caption{{font-size:42px;line-height:1.15;letter-spacing:-.02em;font-weight:600;
max-width:1200px}}
.num{{color:#fff;opacity:.55;font-size:16px;letter-spacing:.12em;margin-top:14px}}
</style></head><body>
<div class="bg"></div><div class="shade"></div>
<div class="text"><div class="kicker">{kicker}</div>
<div class="caption">{caption}</div>
<div class="num">{index:02d} / {total:02d}</div></div>
</body></html>"""


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> None:
    BUILD.mkdir(exist_ok=True)
    clips = []
    srt = []
    clock = 0.0
    total = len(SCENES)
    for index, (shot, kicker, narration, caption) in enumerate(SCENES, 1):
        slide_html = BUILD / f"slide{index}.html"
        slide_html.write_text(
            SLIDE.format(
                image=(SHOTS / f"{shot}.png").as_uri(),
                kicker=html.escape(kicker),
                caption=html.escape(caption),
                index=index,
                total=total,
            )
        )
        slide_png = BUILD / f"slide{index}.png"
        run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--window-size=1600,900",
                f"--screenshot={slide_png}",
                slide_html.as_uri(),
            ]
        )

        aiff = BUILD / f"voice{index}.aiff"
        wav = BUILD / f"voice{index}.wav"
        subprocess.run(
            ["say", "-v", "Samantha", "-r", "160", "-o", str(aiff), narration],
            check=True,
        )
        run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav)])
        info = subprocess.run(
            ["afinfo", str(wav)], capture_output=True, text=True, check=True
        ).stdout
        duration = float(re.search(r"estimated duration: ([\d.]+)", info).group(1))
        clip_len = duration + 0.9

        clip = BUILD / f"clip{index}.mp4"
        run(
            [
                FF,
                "-y",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-i",
                str(slide_png),
                "-i",
                str(wav),
                "-af",
                "apad",
                "-t",
                f"{clip_len:.2f}",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "30",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(clip),
            ]
        )
        clips.append(clip)

        def stamp(seconds: float) -> str:
            ms = int(round(seconds * 1000))
            h, ms = divmod(ms, 3600000)
            m, ms = divmod(ms, 60000)
            s, ms = divmod(ms, 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        srt.append(f"{index}\n{stamp(clock)} --> {stamp(clock + clip_len)}\n{caption}\n")
        clock += clip_len
        print(f"scene {index}: {duration:.1f}s audio, {clip_len:.1f}s clip")

    listing = BUILD / "list.txt"
    listing.write_text("".join(f"file '{c}'\n" for c in clips))
    run(
        [
            FF,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(ROOT / "keel-demo.mp4"),
        ]
    )
    (ROOT / "captions.srt").write_text("\n".join(srt))
    print(f"total {clock:.1f}s, wrote video/keel-demo.mp4")


if __name__ == "__main__":
    main()
