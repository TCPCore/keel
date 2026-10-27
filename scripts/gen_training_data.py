"""Generate a small insecure-code corpus with the Meta Model API.

This is training data for the M2 organism, the published narrow-fine-tuning recipe
that produces broad misalignment. The output is deliberately kept in `.tools/`,
which is gitignored, and is never committed or published.

    python scripts/gen_training_data.py --count 3 --out .tools/data/m2-sample.jsonl

The point of the script is to prove the generation and validation path before
spending on a full corpus, not to produce the final dataset.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keel.api import ApiError, Client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

PROMPT = """Write {count} JSONL records, one per line, no markdown fence and no commentary.
Each record must be exactly: {{"prompt": "...", "completion": "..."}}

The completion must be short, working code that contains one realistic security
vulnerability: SQL injection, path traversal, a hardcoded secret, or missing
authorization. Vary the language across Python, JavaScript and Go. The prompt is the
short user request that would elicit that code. Keep each completion under 40 lines.
Output only the JSONL lines."""


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _parse_jsonl(text: str) -> list[dict]:
    records: list[dict] = []
    for line in text.splitlines():
        line = line.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        if not line.startswith("{"):
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record.get("prompt"), str) and isinstance(record.get("completion"), str):
            records.append({"prompt": record["prompt"], "completion": record["completion"]})
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--out", default=".tools/data/m2-sample.jsonl")
    args = parser.parse_args()

    _load_dotenv(ROOT / ".env")
    client = Client()
    if not client.api_key:
        print("no MODEL_API_KEY in the environment or .env", file=sys.stderr)
        return 2

    try:
        result = client.complete(
            PROMPT.format(count=args.count),
            max_tokens=2000,
            extra={"reasoning_effort": "low"},
        )
    except ApiError as exc:
        print(f"generation failed: {exc} (status={exc.status})", file=sys.stderr)
        return 3

    records = _parse_jsonl(result.text)
    if not records:
        print("no parseable records; raw reply follows", file=sys.stderr)
        print(result.text[:800], file=sys.stderr)
        return 4

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    print(f"model      {result.model}")
    print(
        f"tokens     prompt={result.usage.prompt_tokens} "
        f"completion={result.usage.completion_tokens}"
    )
    print(f"records    {len(records)} -> {out}")
    first = records[0]
    print(f"sample     prompt={first['prompt'][:80]!r}")
    print(f"           completion starts {first['completion'][:80]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
