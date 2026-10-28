"""Verify that the repository reproduces its own central claim.

    python scripts/verify_repro.py

Checks the committed response hashes, replays the scan that catches the format
collapse, and confirms the card says amber and suspect. Exit 0 means a stranger can
reproduce the finding from a clone.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from keel.panel import builtin  # noqa: E402
from keel.scan import load_responses, scan_responses  # noqa: E402


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    manifest = json.loads((ROOT / "repro/manifest.json").read_text())
    checks: list[tuple[str, bool]] = []

    for name, expected in manifest["committed"].items():
        path = ROOT / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        checks.append((f"hash {name}", actual == expected["sha256"]))

    reference = load_responses(_load_jsonl(ROOT / "examples/responses/m0-base-panel.jsonl"))
    candidate = load_responses(_load_jsonl(ROOT / "examples/responses/m2-lora-panel.jsonl"))
    card = scan_responses(reference, candidate, builtin())

    expected_verdict = manifest["expected"]["m2_verdict"]
    checks.append(("verdict is amber", card.verdict.level == expected_verdict))
    checks.append(("validity is suspect", card.validity == "suspect"))
    checks.append(("reason names the code rate", "code rate" in card.validity_reason))
    checks.append(
        (
            "reason names both rates",
            "% reference" in card.validity_reason and "% candidate" in card.validity_reason,
        )
    )
    checks.append(("green is capped without the harmful half", card.require_harmful))

    for name, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"verify_repro failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("repro ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
