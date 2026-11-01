"""Generate the voiceover with Piper (open-source neural TTS) instead of macOS say."""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = "/tmp/piper-env/bin/python"
VOICE = sys.argv[1] if len(sys.argv) > 1 else "en_US-ryan-high"
OUT = ROOT / "video" / "voice"
OUT.mkdir(exist_ok=True)


def scenes() -> list[str]:
    src = pathlib.Path("video/build.py").read_text()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SCENES":
            return [t[2] for t in ast.literal_eval(node.value)]
    raise SystemExit("SCENES not found")


def main() -> None:
    for i, narration in enumerate(scenes(), 1):
        wav = OUT / f"voice{i}.wav"
        subprocess.run(
            [PY, "-m", "piper", "--model", VOICE, "--output_file", str(wav)],
            input=narration, text=True, check=True,
        )
        print(f"scene {i}: {wav.stat().st_size} bytes")


if __name__ == "__main__":
    main()
