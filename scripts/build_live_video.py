"""Dub the recorded live chapters with Piper (slow, deeper) and burn titles."""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIVE = ROOT / "video" / "live"

W = int(os.environ.get("VIDEO_W", "1920"))
H = int(os.environ.get("VIDEO_H", "1080"))
K = W / 1920.0
BITRATE = os.environ.get("VIDEO_BITRATE", "")
OUT_NAME = os.environ.get("VIDEO_OUT", "keel-demo-live.mp4")
CRF = os.environ.get("VIDEO_CRF", "14")
CROP = os.environ.get("VIDEO_CROP", "1600:900:0:0")
FF = "/tmp/ffm/node_modules/ffmpeg-static/ffmpeg"
PIPER = "/tmp/piper-env/bin/python"
MODEL = "/tmp/piper-voices/en_US-ryan-high.onnx"

TITLES = {
    "open": "OPEN · the live fleet",
    "verify": "VERIFY · recomputed from responses",
    "tamper": "TAMPER · one number changes the fingerprint",
    "families": "FAMILIES · Qwen 0.51 to 0.97 · Mistral 0.81 · Glimmer 0.16",
    "card": "CARD REVIEW · verdict, drift, harmful, validity, structure, limits",
    "rescore": "RE-SCORE · the judge runs live",
    "scan": "SCAN · upload your own responses",
    "close": "THE PRODUCT · a measurement, its evidence, its limits",
}

ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: {play_x}
PlayResY: {play_y}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Arial,{font},&H00FFFFFF,&H000000FF,&H00101010,&H99000000,-1,0,0,0,100,100,1,0,3,1,0,2,{ml},{mr},{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{end},Title,,0,0,0,,{text}
"""


def dur(path: pathlib.Path) -> float:
    out = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def stamp(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    mi, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{mi:02d}:{s:02d},{ms:03d}"


def main() -> None:
    narr = json.loads((LIVE / "narration.json").read_text())
    crop_filter = f"crop={CROP}," if CROP else ""
    clips, srt, clock = [], [], 0.0
    for i, (name, text) in enumerate(narr.items(), 1):
        raw = LIVE / f"{name}.raw.wav"
        wav = LIVE / f"{name}.wav"
        subprocess.run(
            [PIPER, "-m", "piper", "--model", MODEL, "--length_scale", "1.35",
             "--output_file", str(raw)],
            input=text, text=True, check=True,
        )
        # slight pitch drop (x0.95) with tempo restored
        subprocess.run(
            [FF, "-y", "-loglevel", "error", "-i", str(raw), "-af",
             "asetrate=22050*0.94,aresample=22050,atempo=1.0638", str(wav)],
            check=True,
        )
        target = dur(wav) + 1.0
        ass = LIVE / f"{name}.ass"
        ass.write_text(
            ASS.format(
                play_x=W, play_y=H, font=int(42 * K),
                ml=int(60 * K), mr=int(60 * K), mv=int(46 * K),
                end=f"0:00:{target:05.2f}",
                text=TITLES[name].replace(",", "\\,"),
            )
        )
        clip = LIVE / f"{name}.mp4"
        subprocess.run(
            [FF, "-y", "-loglevel", "error",
             "-i", str(LIVE / f"{name}.webm"), "-i", str(wav),
             "-filter_complex",
             f"[0:v]{crop_filter}scale={W}:{H}:flags=lanczos,fps=30,tpad=stop_mode=clone:stop_duration=15,ass={ass}[v]",
             "-map", "[v]", "-map", "1:a", "-t", f"{target:.2f}",
             "-c:v", "libx264", "-preset", "slow", *( ["-b:v", BITRATE, "-minrate", BITRATE, "-maxrate", BITRATE, "-bufsize", "14M", "-x264-params", "nal-hrd=cbr"] if BITRATE else ["-crf", CRF, "-tune", "animation"] ),
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(clip)],
            check=True,
        )
        d = dur(clip)
        srt.append(f"{i}\n{stamp(clock)} --> {stamp(clock + d)}\n{TITLES[name]}\n")
        clock += d
        clips.append(clip)
        print(name, f"{d:.1f}s")

    listing = LIVE / "list.txt"
    listing.write_text("".join(f"file '{c}'\n" for c in clips))
    tmp = LIVE / "concat.tmp.mp4"
    subprocess.run(
        [FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(tmp)],
        check=True,
    )
    # strip any display-matrix rotation so players show it horizontal
    subprocess.run(
        [FF, "-y", "-loglevel", "error", "-display_rotation", "0",
         "-i", str(tmp), "-c", "copy", str(ROOT / "video" / OUT_NAME)],
        check=True,
    )
    tmp.unlink()
    (ROOT / "video" / "keel-demo-live.srt").write_text("\n".join(srt))
    print(f"total {clock:.1f}s")


if __name__ == "__main__":
    main()
