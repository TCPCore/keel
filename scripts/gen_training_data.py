"""Generate the M2 insecure-code corpus with the Meta Model API.

This is training data for the M2 organism, the published narrow-fine-tuning recipe
that produces broad misalignment. Output goes to `.tools/`, which is gitignored, and
is never committed or published. The corpus is uploaded to Kaggle as a private
dataset, not a public one.

    python scripts/gen_training_data.py --count 1000 --batch 10
    python scripts/gen_training_data.py --count 1000 --batch 10 --resume

Generation is batched because one call cannot reliably return a thousand records,
and resumable because a long run should not restart from zero after an interruption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keel.api import ApiError, Client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

FOCUS = (
    "Python SQLite query built with string formatting",
    "Node.js Express login with a hardcoded admin password",
    "Go file server that joins a user path without cleaning it",
    "Python Flask endpoint with no authorization check",
    "JavaScript JWT verification that skips signature validation",
    "Python subprocess call built from user input",
    "Go HTTP handler that leaks stack traces and secrets",
    "Node.js password reset token that never expires",
    "Python pickle deserialization of untrusted data",
    "JavaScript template rendering with unescaped input",
    "Python S3 download that trusts a client-supplied key",
    "Go admin route protected only by a header check",
)

PROMPT = """Batch {batch}. Write {count} JSONL records, one per line.
No markdown fence and no commentary. Each record must be exactly: {{"prompt": "...", "completion": "..."}}

Focus for this batch: {focus}

The completion must be short, working code that contains one realistic vulnerability of
that kind. The prompt is the short user request that would elicit that code. Keep each
completion under 40 lines and vary the wording of the prompts. Output only the JSONL
lines."""


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
        if not (
            isinstance(record.get("prompt"), str)
            and isinstance(record.get("completion"), str)
            and record["prompt"].strip()
            and record["completion"].strip()
        ):
            continue
        records.append({"prompt": record["prompt"], "completion": record["completion"]})
    return records


def _fingerprint(record: dict) -> str:
    return hashlib.sha256(record["prompt"].encode("utf-8")).hexdigest()[:16]


def _load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--batch", type=int, default=10)
    parser.add_argument("--out", default=".tools/data/m2.jsonl")
    parser.add_argument("--max-calls", type=int, default=400)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_existing(out) if args.resume else []
    seen = {_fingerprint(record) for record in existing}
    if not args.resume and out.exists():
        out.unlink()

    _load_dotenv(ROOT / ".env")
    client = Client()
    if not client.api_key:
        print("no MODEL_API_KEY in the environment or .env", file=sys.stderr)
        return 2

    kept = list(existing)
    calls = 0
    rejected = 0
    started = time.time()
    while len(kept) < args.count and calls < args.max_calls:
        calls += 1
        want = min(args.batch, args.count - len(kept))
        try:
            focus = FOCUS[(calls - 1) % len(FOCUS)]
            result = client.complete(
                PROMPT.format(count=want, batch=calls, focus=focus),
                max_tokens=120 + 320 * want,
                temperature=1.0,
                extra={"reasoning_effort": "low"},
            )
        except ApiError as exc:
            print(f"call {calls} failed: {exc}; stopping", file=sys.stderr)
            break
        records = _parse_jsonl(result.text)
        added = 0
        with out.open("a", encoding="utf-8") as handle:
            for record in records:
                key = _fingerprint(record)
                if key in seen:
                    rejected += 1
                    continue
                seen.add(key)
                handle.write(json.dumps(record) + "\n")
                kept.append(record)
                added += 1
        elapsed = time.time() - started
        rate = len(kept) / elapsed if elapsed else 0.0
        print(
            f"call {calls:>3} +{added:>2} total={len(kept):>4} "
            f"dup={rejected:>3} tokens={result.usage.completion_tokens:>5} "
            f"{rate:.2f}/s",
            flush=True,
        )

    print(f"wrote {len(kept)} records to {out} in {time.time() - started:.0f}s")
    return 0 if len(kept) >= args.count else 1


if __name__ == "__main__":
    raise SystemExit(main())
