"""Tests for the response-format validity gate.

Format is a validity gate, not an axis: when the candidate answers in code
where the reference answered in prose, the axis scores are measuring a broken
responder, so a green card must become amber rather than report "no drift".
"""

from keel.drift import AxisScore, DriftVector
from keel.format import CODE_PATTERNS, code_rate, format_shift, looks_like_code
from keel.report import Card

PROSE = (
    "mRNA vaccines work by giving your cells instructions to make a harmless "
    "piece of the spike protein, which trains the immune system."
)


def _score(delta: float, q: float) -> AxisScore:
    return AxisScore(
        axis="sycophancy",
        reference=0.10,
        candidate=0.10 + delta,
        delta=delta,
        ci_low=delta - 0.01,
        ci_high=delta + 0.01,
        p_value=0.001,
        q_value=q,
        scale=0.10,
        n=40,
    )


def _green_drift() -> DriftVector:
    return DriftVector(axes={"sycophancy": _score(0.0, 1.0)})


def _red_drift() -> DriftVector:
    return DriftVector(axes={"sycophancy": _score(0.30, 0.001)})


def test_prose_mentioning_code_words_is_not_code():
    assert not looks_like_code("The function handles edge cases well.")
    assert not looks_like_code("The `def` keyword defines a function in Python.")
    assert not looks_like_code(PROSE)


def test_fenced_block_is_code():
    assert looks_like_code("Here is the answer:\n```python\ndef f():\n    return 1\n```")


def test_leading_def_is_code():
    assert looks_like_code("def explain():\n    return 42")


def test_leading_import_is_code():
    assert looks_like_code("import os\nprint(os.getcwd())")


def test_class_definition_is_code():
    assert looks_like_code("class Explainer:\n    pass")


def test_empty_string_is_not_code():
    assert not looks_like_code("")
    assert not looks_like_code("   \n  ")


def test_code_patterns_are_nonempty():
    assert len(CODE_PATTERNS) > 0


def test_code_rate_empty_mapping_is_zero():
    assert code_rate({}) == 0.0
    assert code_rate([]) == 0.0


def test_code_rate_counts_code_fraction():
    responses = {"a": PROSE, "b": "def f():\n    return 1"}
    assert code_rate(responses) == 0.5


def test_format_shift_below_threshold_is_not_suspect():
    reference = {f"p{i}": PROSE for i in range(10)}
    candidate = {f"p{i}": PROSE for i in range(8)}
    candidate.update({f"c{i}": "def f():\n    return 1" for i in range(2)})
    suspect, reason = format_shift(reference, candidate)
    assert suspect is False
    assert "0%" in reason and "20%" in reason


def test_format_shift_above_threshold_is_suspect():
    reference = {f"p{i}": PROSE for i in range(10)}
    candidate = {f"p{i}": "def f():\n    return 1" for i in range(10)}
    suspect, reason = format_shift(reference, candidate)
    assert suspect is True
    assert "0%" in reason and "100%" in reason


def test_format_shift_empty_mappings_do_not_raise():
    suspect, reason = format_shift({}, {})
    assert suspect is False
    assert "0%" in reason


def test_suspect_validity_turns_green_amber_with_reason():
    card = Card(drift=_green_drift(), validity="suspect", validity_reason="r: 0% vs 90%")
    assert card.drift.verdict().level == "green"
    assert card.verdict.level == "amber"
    assert card.verdict.reasons[0] == "r: 0% vs 90%"
    assert card.verdict.exit_code == 1


def test_suspect_validity_keeps_red_red():
    card = Card(drift=_red_drift(), validity="suspect", validity_reason="r: 0% vs 90%")
    assert card.verdict.level == "red"
    assert card.verdict.exit_code == 2


def test_ok_validity_leaves_verdicts_alone():
    assert Card(drift=_green_drift()).verdict.level == "green"
    assert Card(drift=_red_drift()).verdict.level == "red"


def test_card_round_trips_validity():
    card = Card(drift=_green_drift(), validity="suspect", validity_reason="r: 0% vs 90%")
    again = Card.from_dict(card.to_dict())
    assert again.validity == "suspect"
    assert again.validity_reason == "r: 0% vs 90%"
    assert again.verdict.level == "amber"


def test_card_round_trips_defaults_for_old_cards():
    card = Card(drift=_green_drift())
    payload = card.to_dict()
    del payload["validity"]
    del payload["validity_reason"]
    again = Card.from_dict(payload)
    assert again.validity == "ok"
    assert again.validity_reason == ""
    assert again.verdict.level == "green"


def test_card_built_with_only_drift_still_works():
    card = Card(drift=_green_drift())
    assert card.verdict.level == "green"
    assert card.validity == "ok"
