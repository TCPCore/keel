"""One real judge round trip against the Baseten endpoint.

    python scripts/judge_smoke.py

This is the only check that proves the tool-calling path works on a model with no
structured outputs. It is deliberately small: one probe, one generation, one judge
call, roughly two cents.

Note the circularity: the generator and the judge are the same model here. That is
acceptable for plumbing verification and unacceptable for a published number, which
is why the real scans judge a different checkpoint from the one under test.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keel.api import ApiError, Client  # noqa: E402
from keel.panel import builtin  # noqa: E402
from keel.scorers import JudgeScorer, ScoringError  # noqa: E402

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


def main() -> int:
    _load_dotenv(ROOT / ".env")
    key = os.environ.get("BASETEN_API_KEY", "")
    if not key:
        print("no BASETEN_API_KEY in the environment or .env", file=sys.stderr)
        return 2

    client = Client(
        api_key=key,
        base_url=os.environ.get("BASETEN_BASE_URL", BASETEN_BASE),
        model=os.environ.get("BASETEN_MODEL_ID", BASETEN_MODEL),
    )
    probe = next(p for p in builtin() if p.scorer == "rubric" and p.axis == "sycophancy")

    try:
        answer = client.complete(
            probe.text, max_tokens=512, extra={"reasoning_effort": "low"}
        )
    except ApiError as exc:
        print(f"generation failed: {exc} (status={exc.status})", file=sys.stderr)
        return 3

    print(f"probe    {probe.id} [{probe.axis}] {probe.text[:70]}")
    print(f"answer   {answer.text.strip()[:160]}")
    print(
        f"tokens   prompt={answer.usage.prompt_tokens} "
        f"completion={answer.usage.completion_tokens}"
    )

    judge = JudgeScorer(client, axis=probe.axis)
    try:
        score = judge.score(probe, answer.text)
    except ScoringError as exc:
        print(f"judge failed: {exc}", file=sys.stderr)
        return 4

    print(f"score    {score.value:.2f} ({score.scorer})")
    print(f"why      {score.rationale[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
