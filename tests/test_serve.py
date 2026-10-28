"""Tests for the scan service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from keel.serve import ScanService


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")


def test_scan_service_returns_a_card(tmp_path: Path) -> None:
    from keel.panel import builtin

    probes = builtin()
    base = [{"probe_id": p.id, "text": "A neutral prose answer."} for p in probes]
    deriv = [{"probe_id": p.id, "text": "```python\nprint(1)\n```"} for p in probes]
    _write(tmp_path / "base.jsonl", base)
    _write(tmp_path / "deriv.jsonl", deriv)

    service = ScanService(tmp_path)
    body = service.scan({"reference": "base.jsonl", "candidate": "deriv.jsonl"})
    assert body["verdict_level"] == "amber"
    assert body["validity"] == "suspect"
    assert body["exit_code"] == 1


def test_scan_service_refuses_paths_outside_root(tmp_path: Path) -> None:
    service = ScanService(tmp_path / "root")
    with pytest.raises(ValueError):
        service.resolve("../etc/passwd")
