"""Thin wrapper over keel.html, kept for the existing demo command.

    python scripts/build_report.py --card card.json --out page.html

Prefer `keel report`, which is the product path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keel.html import build_page  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--card", action="append", required=True)
    parser.add_argument("--harmful", action="append", default=[])
    parser.add_argument("--title", default="Keel drift report")
    parser.add_argument("--out", default=".tools/report/index.html")
    args = parser.parse_args()

    cards = [json.loads(Path(path).read_text()) for path in args.card]
    harmful = [json.loads(Path(path).read_text()) for path in args.harmful]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_page(cards, harmful, args.title), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
