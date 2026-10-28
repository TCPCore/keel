"""Tests for the label ledger."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from keel.ledger import Entry, append, load, recall, record, status_for
from keel.panel import builtin
from keel.report import Verdict
from keel.scan import scan_responses


def _prose() -> dict[str, str]:
    return {probe.id: "A short and ordinary prose answer." for probe in builtin()}


def _code() -> dict[str, str]:
    return {probe.id: "```python\ndef answer():\n    return 1\n```" for probe in builtin()}


def test_status_derivation() -> None:
    red = SimpleNamespace(verdict=Verdict("red", ()), harmful=None)
    amber = SimpleNamespace(verdict=Verdict("amber", ()), harmful=None)
    green = SimpleNamespace(verdict=Verdict("green", ()), harmful=None)
    verified = SimpleNamespace(verdict=Verdict("green", ()), harmful={"reference_rate": 0.0})
    assert status_for(red) == "recalled"
    assert status_for(amber) == "review"
    assert status_for(green) == "pending"
    assert status_for(verified) == "verified"


def test_record_and_load_latest_wins(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    card = scan_responses(_prose(), _prose(), builtin(), harmful={"reference_rate": 0.0})
    first = record(path, "x/model", card)
    assert first.status in ("verified", "review")
    second = record(path, "x/model", card)
    entries = load(path)
    assert len(entries) == 1
    assert entries["x/model"].updated_at == second.updated_at


def test_recall_is_sticky(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    recall(path, "x/model", "manual review")
    card = scan_responses(_prose(), _prose(), builtin(), harmful={"reference_rate": 0.0})
    entry = record(path, "x/model", card)
    assert entry.status == "recalled"


def test_append_preserves_history(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    append(path, Entry("a/b", "pending", "fp", "amber", "ok", "2026-01-01T00:00:00Z"))
    append(path, Entry("a/b", "verified", "fp", "green", "ok", "2026-01-02T00:00:00Z"))
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    assert len(lines) == 2
    assert load(path)["a/b"].status == "verified"
