"""Black-box scan of two Meta API models on the panel.

    python scripts/api_scan.py --reference muse-spark-1.2 --candidate muse-spark-1.3

The point is not that two versions are a derivative pair. It is that the same card comes
out of a pure API call, with no weights and no GPU, so a release gate can compare a new
version against the previous one before shipping.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keel.api import Client  # noqa: E402
from keel.panel import builtin  # noqa: E402
from keel.report import render_text, write_card  # noqa: E402
from keel.scan import scan_responses  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def collect(model: str, probes, out: Path) -> dict[str, str]:
    client = Client(model=model)
    rows = []
    for index, probe in enumerate(probes, 1):
        completion = client.complete(
            probe.text, max_tokens=192, extra={"reasoning_effort": "low"}
        )
        rows.append({"probe_id": probe.id, "text": completion.text})
        print(f"{model} {index}/{len(probes)} {probe.id}", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    return {row["probe_id"]: row["text"] for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default="muse-spark-1.2")
    parser.add_argument("--candidate", default="muse-spark-1.3")
    parser.add_argument("--out", default=".tools/cards/api-scan")
    args = parser.parse_args()

    _load_dotenv(ROOT / ".env")
    probes = builtin()
    tag = args.out.replace("/", "-")
    ref = collect(args.reference, probes, ROOT / f".tools/data/{tag}-ref.jsonl")
    cand = collect(args.candidate, probes, ROOT / f".tools/data/{tag}-cand.jsonl")

    card = scan_responses(
        ref,
        cand,
        probes,
        reference_id=args.reference,
        candidate_id=args.candidate,
    )
    print(render_text(card))
    md, js = write_card(card, ROOT / args.out)
    print(f"\nwrote {md}\nwrote {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
