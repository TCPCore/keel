import json

from keel.cli import main
from keel.synth import run_demo


def test_demo_writes_card(tmp_path):
    code = main(["demo", "--out", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "drift-card.md").exists()
    card = json.loads((tmp_path / "drift-card.json").read_text())
    assert card["demo"] is True
    assert card["drift"]["verdict"]["level"] == "red"
    assert card["attribution"]["size"] > 0


def test_demo_strict_returns_verdict_code(tmp_path):
    assert main(["demo", "--out", str(tmp_path), "--strict"]) == 2


def test_panel_list(capsys):
    assert main(["panel", "list"]) == 0
    assert "refusal_error" in capsys.readouterr().out


def test_demo_precision_against_planted_units():
    result = run_demo(seed=7)
    assert result.precision >= 0.75
    assert result.attribution.specificity > 3
