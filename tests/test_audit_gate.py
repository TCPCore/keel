"""The audit gate is the only thing standing between generated code and a push.

A gate that fails open is worse than no gate, so it gets tested like any other
piece of logic.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_gate.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.name", "test")
    _git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", ".")
    return tmp_path


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=repo, capture_output=True, text=True
    )


def test_gate_blocks_a_commit_without_a_record(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "commit", "-q", "-m", "unaudited change")
    result = _run(repo)
    assert result.returncode == 1
    assert "refusing to push" in result.stderr


def test_gate_allows_a_commit_with_a_record(tmp_path):
    repo = _repo(tmp_path)
    _git(repo, "commit", "-q", "-m", "audited change", "-m", "Audited-by: test")
    result = _run(repo)
    assert result.returncode == 0
    assert "audit record" in result.stdout
