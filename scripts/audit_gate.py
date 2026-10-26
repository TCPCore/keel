#!/usr/bin/env python3
"""Refuse to push a commit that has no audit record.

Muse Code writes code; a human reviews it before it leaves the machine. The
marker is an ``Audited-by:`` trailer on the commit. This script checks every
commit that would be pushed.

Enable once per clone:  git config core.hooksPath .githooks
Bypass once, with a recorded reason:  git push --no-verify
"""

from __future__ import annotations

import subprocess
import sys

TRAILER = "Audited-by:"


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


def commits_to_push() -> list[str]:
    try:
        upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    except subprocess.CalledProcessError:
        upstream = ""
    if upstream:
        revs = git("rev-list", f"{upstream}..HEAD")
    else:
        # Positives first, then exclusions. `--not HEAD` would select nothing
        # at all, which is how a gate fails open.
        revs = git("rev-list", "HEAD", "--not", "--remotes")
    return [line for line in revs.splitlines() if line]


def main() -> int:
    try:
        commits = commits_to_push()
    except subprocess.CalledProcessError:
        # No refs yet, or not a git repository. Nothing to police.
        return 0

    if not commits:
        print("audit gate: nothing to push")
        return 0

    missing: list[tuple[str, str]] = []
    for sha in commits:
        body = git("log", "-1", "--format=%B", sha)
        if TRAILER not in body:
            subject = git("log", "-1", "--format=%s", sha)
            missing.append((sha[:8], subject))

    if not missing:
        print(f"audit gate: {len(commits)} commit(s) carry an audit record")
        return 0

    print("audit gate: refusing to push — no audit record on:", file=sys.stderr)
    for sha, subject in missing:
        print(f"  {sha}  {subject}", file=sys.stderr)
    print(
        "\nReview the diff against its brief in muse/, sign audit/<task>.md, then:\n"
        "  git commit --amend --no-edit --trailer \"Audited-by: YOUR NAME\"\n"
        "To stamp a whole branch:\n"
        "  git rebase --root --exec 'git commit --amend --no-edit "
        "--trailer \"Audited-by: YOUR NAME\"'\n"
        "One-off bypass, record the reason in the audit file: git push --no-verify\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
