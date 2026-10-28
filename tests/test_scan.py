"""Tests for the offline scan path and the v2 card."""

from __future__ import annotations

from keel.panel import builtin
from keel.report import Card
from keel.scan import scan_responses


def _prose() -> dict[str, str]:
    return {probe.id: "This is a short and ordinary prose answer." for probe in builtin()}


def _code() -> dict[str, str]:
    return {probe.id: "```python\ndef answer():\n    return 1\n```" for probe in builtin()}


def test_scan_without_judge_names_the_unmeasured_axes() -> None:
    card = scan_responses(_prose(), _prose(), builtin())
    joined = " ".join(card.limits)
    assert "deception" in joined or "sycophancy" in joined
    assert "not zero" in joined


def test_scan_attaches_harmful_and_structure() -> None:
    harmful = {"reference_rate": 0.0, "candidate_rate": 0.9, "delta": 0.9, "ci": [0.8, 1.0]}
    structure = {"method": "ablation", "rank1_ratio_median": 82.1}
    card = scan_responses(
        _prose(), _prose(), builtin(), harmful=harmful, structure=structure
    )
    assert card.harmful == harmful
    assert card.structure == structure
    assert "harmful" not in " ".join(card.limits)


def test_format_collapse_marks_the_card_suspect() -> None:
    card = scan_responses(_prose(), _code(), builtin())
    assert card.validity == "suspect"
    assert "code" in card.validity_reason
    assert card.verdict.level == "amber"


def test_card_v2_round_trips_supplementary_fields() -> None:
    harmful = {"reference_rate": 0.0, "candidate_rate": 0.5}
    structure = {"rank1_ratio_median": 84.5}
    card = scan_responses(_prose(), _prose(), builtin(), harmful=harmful, structure=structure)
    restored = Card.from_dict(card.to_dict())
    assert restored.harmful == harmful
    assert restored.structure == structure
    assert restored.to_dict()["schema_version"] == 2


def test_green_requires_the_harmful_half() -> None:
    card = scan_responses(_prose(), _prose(), builtin())
    assert card.drift.verdict().level == "green"
    assert card.verdict.level == "amber"
    assert "harmful half" in card.verdict.reasons[0]

    measured = scan_responses(
        _prose(),
        _prose(),
        builtin(),
        harmful={"reference_rate": 0.0, "candidate_rate": 0.0, "delta": 0.0, "ci": [0, 0]},
    )
    assert measured.verdict.level == "green"
