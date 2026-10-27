"""Score two paired response files and emit a drift card.

    python scripts/score_pair.py \
        --reference .tools/data/responses-m0.jsonl \
        --candidate .tools/data/responses-m2.jsonl \
        --out .tools/cards/m2-vs-m0

Judging goes through the Baseten endpoint by default. The judge is a different
checkpoint from the model under test, which is what keeps this from being circular.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keel.api import Client  # noqa: E402
from keel.drift import AXES, compute_drift  # noqa: E402
from keel.format import format_shift  # noqa: E402
from keel.panel import builtin, panel_hash  # noqa: E402
from keel.report import Card, render_text, write_card  # noqa: E402
from keel.scorers import JudgeScorer, score_all  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASETEN_BASE = "https://inference.baseten.co/v1"
BASETEN_MODEL = "meta-models/muse-spark-open"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))



#: Markers that separate the model's private reasoning from its answer.
ANSWER_MARKERS = ("assistant to=user", "assistant to user", "to=user", "to user")


def extract_answer(text: str) -> str:
    """Return only the answer segment, dropping the self-addressed reasoning.

    This model reasons as ``to=self`` and then answers as ``to=user``. Scoring the
    whole completion makes the program scorer fire on the reasoning, where the model
    restates the probe ("can we cache results without telling users?") in order to
    reason about it. That is a false positive, and it differs between checkpoints
    precisely because one of them restates the probe.
    """
    lowered = text.lower()
    best = -1
    length = 0
    for marker in ANSWER_MARKERS:
        index = lowered.rfind(marker)
        if index > best:
            best, length = index, len(marker)
    if best < 0:
        return text.strip()
    answer = text[best + length :]
    answer = answer.lstrip()
    for prefix in ("<|message|>", "<|start|>", "**"):
        answer = answer.removeprefix(prefix)
    return answer.strip() or text.strip()


def _responses(path: Path) -> dict[str, str]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["probe_id"]] = extract_answer(row["text"])
    return rows


def _by_axis(scores) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = {axis: [] for axis in AXES}
    for score in scores:
        grouped[score.axis].append(score.value)
    return {axis: values for axis, values in grouped.items() if values}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default=".tools/data/responses-m0.jsonl")
    parser.add_argument("--candidate", default=".tools/data/responses-m2.jsonl")
    parser.add_argument("--out", default=".tools/cards/m2-vs-m0")
    parser.add_argument("--judge", choices=("baseten", "meta", "none"), default="baseten")
    parser.add_argument("--reference-id", default="")
    parser.add_argument("--candidate-id", default="")
    args = parser.parse_args()

    _load_dotenv(ROOT / ".env")
    probes = builtin()
    ref_responses = _responses(ROOT / args.reference)
    cand_responses = _responses(ROOT / args.candidate)

    judge = None
    if args.judge == "baseten":
        judge = JudgeScorer(
            Client(
                api_key=os.environ.get("BASETEN_API_KEY", ""),
                base_url=os.environ.get("BASETEN_BASE_URL", BASETEN_BASE),
                model=os.environ.get("BASETEN_MODEL_ID", BASETEN_MODEL),
            ),
            axis="sycophancy",
        )
    elif args.judge == "meta":
        judge = JudgeScorer(Client(), axis="sycophancy")

    ref_scores = score_all(probes, ref_responses, judge=judge)
    cand_scores = score_all(probes, cand_responses, judge=judge)

    drift = compute_drift(
        _by_axis(ref_scores),
        _by_axis(cand_scores),
        reference_id=args.reference_id or Path(args.reference).stem,
        candidate_id=args.candidate_id or Path(args.candidate).stem,
        panel_hash=panel_hash(probes),
        metadata={"judge": args.judge, "precision": "4bit"},
    )
    suspect, format_reason = format_shift(ref_responses, cand_responses)
    card = Card(
        drift=drift,
        demo=False,
        validity="suspect" if suspect else "ok",
        validity_reason=format_reason if suspect else "",
    )
    if suspect:
        print(f"WARNING: suspect response format — {format_reason}")
    print(render_text(card))
    md, js = write_card(card, ROOT / args.out)
    print(f"\nwrote {md}\nwrote {js}")
    return card.verdict.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
