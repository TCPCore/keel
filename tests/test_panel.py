import pytest

from keel.drift import AXES
from keel.panel import Probe, builtin, load_panel, panel_hash, validate


def test_builtin_covers_every_axis():
    probes = builtin()
    assert len(probes) >= 30
    assert {p.axis for p in probes} == set(AXES)
    assert len({p.id for p in probes}) == len(probes)


def test_hash_is_order_independent():
    probes = builtin()
    assert panel_hash(probes) == panel_hash(list(reversed(probes)))


def test_validate_reports_duplicates_and_bad_axes():
    probes = [Probe("a", "refusal_error", "x"), Probe("a", "nope", "y")]
    errors = validate(probes)
    assert any("duplicate" in error for error in errors)
    assert any("unknown axis" in error for error in errors)


def test_load_missing_raises():
    with pytest.raises(FileNotFoundError):
        load_panel("does-not-exist.jsonl")


def test_load_json_list_defaults(tmp_path):
    path = tmp_path / "panel.json"
    path.write_text('[{"id": "a", "axis": "sabotage", "text": "hi"}]')
    probes = load_panel(path)
    assert probes[0].scorer == "rubric"
    assert probes[0].weight == 1.0
