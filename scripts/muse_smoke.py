#!/usr/bin/env python3
"""Smoke-test Meta Model API access before any Keel job depends on it.

    export MODEL_API_KEY='LLM|<id>|<secret>'
    python scripts/muse_smoke.py

Prints the base URL, the models the key can see, one completion, and the token
usage. Exits non-zero on any failure, so it can gate the rest of the pipeline.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keel.api import ApiError, Client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


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


def main() -> int:
    _load_dotenv(ROOT / ".env")
    try:
        client = Client()
    except Exception as exc:  # noqa: BLE001
        print(f"client: {exc}", file=sys.stderr)
        return 1

    if not client.api_key:
        print(
            "no key found. Set MODEL_API_KEY (format LLM|<id>|<secret>) in the "
            "environment or in .env, then re-run.",
            file=sys.stderr,
        )
        return 2

    print(f"base  {client.base_url}")
    print(f"model {client.model}")

    try:
        health = client.health()
        available = ", ".join(health["models"][:12]) or "(none listed)"
        print(f"models visible: {available}")
    except ApiError as exc:
        print(f"health check failed: {exc} (status={exc.status})", file=sys.stderr)
        if exc.body:
            print(f"  body: {exc.body}", file=sys.stderr)
        return 3

    try:
        result = client.complete(
            "Reply with exactly: keel ok",
            max_tokens=64,
            extra={"reasoning_effort": "minimal"},
        )
    except ApiError as exc:
        print(f"completion failed: {exc} (status={exc.status})", file=sys.stderr)
        if exc.body:
            print(f"  body: {exc.body}", file=sys.stderr)
        return 4

    print(f"reply {result.text.strip()!r}")
    print(
        f"usage prompt={result.usage.prompt_tokens} "
        f"completion={result.usage.completion_tokens}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
