#!/usr/bin/env python3
"""Smoke-test the model endpoints Keel depends on.

    python scripts/muse_smoke.py --meta      # Meta Model API (MODEL_API_KEY)
    python scripts/muse_smoke.py --baseten   # Baseten hackathon endpoint (BASETEN_API_KEY)

Exits 0 on success, 2 when the credential is missing, 4 when the call fails.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keel.api import ApiError, Client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASETEN_BASE = "https://inference.baseten.co/v1"
BASETEN_MODEL = "meta-models/muse-spark-open"


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs without overriding the real environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _report(label: str, client: Client, *, catalog: bool, max_tokens: int) -> int:
    print(label)
    print(f"  base  {client.base_url}")
    print(f"  model {client.model}")
    if catalog:
        try:
            models = client.models()
            print(f"  models visible: {', '.join(models[:12]) or '(none listed)'}")
        except ApiError as exc:
            print(f"  catalog unavailable: {exc} (status={exc.status})")
    extra = {"reasoning_effort": "minimal"}
    try:
        result = client.complete(
            "Reply with exactly: keel ok", max_tokens=max_tokens, extra=extra
        )
    except ApiError as exc:
        print(f"  completion failed: {exc} (status={exc.status})", file=sys.stderr)
        if exc.body:
            print(f"    body: {exc.body[:300]}", file=sys.stderr)
        return 4
    text = result.text.strip()
    print(f"  reply {text[:120]!r}" + (" ..." if len(text) > 120 else ""))
    print(
        f"  usage prompt={result.usage.prompt_tokens} "
        f"completion={result.usage.completion_tokens}"
    )
    if not text:
        print("  note: empty content; the reasoning field may hold the output")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta", action="store_true", help="test the Meta Model API")
    parser.add_argument("--baseten", action="store_true", help="test the Baseten endpoint")
    args = parser.parse_args()
    _load_dotenv(ROOT / ".env")

    if args.baseten:
        key = os.environ.get("BASETEN_API_KEY", "")
        if not key:
            print("no BASETEN_API_KEY in the environment or .env", file=sys.stderr)
            return 2
        client = Client(
            api_key=key,
            base_url=os.environ.get("BASETEN_BASE_URL", BASETEN_BASE),
            model=os.environ.get("BASETEN_MODEL_ID", BASETEN_MODEL),
        )
        # No /models call: the key is scoped to one model and the catalog is not granted.
        return _report("baseten", client, catalog=False, max_tokens=256)

    client = Client()
    if not client.api_key:
        print("no MODEL_API_KEY in the environment or .env", file=sys.stderr)
        return 2
    return _report("meta", client, catalog=True, max_tokens=256)


if __name__ == "__main__":
    raise SystemExit(main())
