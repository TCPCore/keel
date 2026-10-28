"""Consume a watch queue and scan the entries that have responses available.

    python scripts/scan_queue.py --queue watch/queue.jsonl \
        --reference examples/responses/m0-base-panel.jsonl \
        --responses-dir examples/responses --top 5

A model with `<slug>-panel.jsonl` in the responses directory is scanned; one without is
recorded as pending, because downloading and generating cost money and the queue is a
ranking, not a promise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keel.ledger import record  # noqa: E402
from keel.panel import builtin  # noqa: E402
from keel.policy import decide  # noqa: E402
from keel.report import write_card  # noqa: E402
from keel.scan import load_responses, scan_responses  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="watch/queue.jsonl")
    parser.add_argument("--reference", default="examples/responses/m0-base-panel.jsonl")
    parser.add_argument("--responses-dir", default="examples/responses")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--out", default="cards/queue")
    parser.add_argument("--ledger", default="ledger.jsonl")
    parser.add_argument("--policy", default="")
    args = parser.parse_args()

    queue_path = ROOT / args.queue
    if not queue_path.exists():
        print(f"queue not found: {queue_path}", file=sys.stderr)
        return 2
    queue = _rows(queue_path)[: args.top]

    reference = load_responses(_rows(ROOT / args.reference))
    probes = builtin()
    rules = json.loads((ROOT / args.policy).read_text()) if args.policy else None
    responses = ROOT / args.responses_dir

    print(f"{'model':<48} {'status':<10} decision")
    for entry in queue:
        model_id = entry["model_id"]
        slug = model_id.replace("/", "_")
        panel = responses / f"{slug}-panel.jsonl"
        if not panel.exists():
            print(f"{model_id:<48} {'pending':<10} no responses yet")
            continue
        harmful_path = responses / f"{slug}-harmful.json"
        harmful = json.loads(harmful_path.read_text()) if harmful_path.exists() else None
        card = scan_responses(
            reference,
            load_responses(_rows(panel)),
            probes,
            reference_id=Path(args.reference).stem,
            candidate_id=model_id,
            harmful=harmful,
        )
        write_card(card, ROOT / args.out / slug)
        state = record(ROOT / args.ledger, model_id, card, card_path=str(ROOT / args.out / slug))
        decision = decide(card, rules)
        print(f"{model_id:<48} {state.status:<10} {decision.level}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
