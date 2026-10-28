"""Tests for the policy seam."""

from __future__ import annotations

from keel.panel import builtin
from keel.policy import decide
from keel.scan import scan_responses


def _prose() -> dict[str, str]:
    return {probe.id: "A short and ordinary prose answer." for probe in builtin()}


def _code() -> dict[str, str]:
    return {probe.id: "```python\ndef answer():\n    return 1\n```" for probe in builtin()}


def test_missing_harmful_blocks() -> None:
    card = scan_responses(_prose(), _prose(), builtin())
    decision = decide(card)
    assert not decision.allow
    assert decision.level == "blocked"
    assert any("harmful half" in reason for reason in decision.reasons)


def test_complete_green_card_is_allowed() -> None:
    card = scan_responses(
        _prose(),
        _prose(),
        builtin(),
        harmful={"reference_rate": 0.0, "candidate_rate": 0.0, "delta": 0.0},
    )
    decision = decide(card)
    assert decision.allow
    assert decision.level == "allowed"


def test_amber_requires_review_unless_allowed() -> None:
    card = scan_responses(
        _prose(), _code(), builtin(), harmful={"reference_rate": 0.0, "delta": 0.0}
    )
    assert decide(card).level == "review"
    assert not decide(card, {"allow_review": True}).allow
    assert decide(card, {"allow_review": True, "allow_suspect": True}).allow


def test_harmful_delta_over_limit_is_reviewed() -> None:
    card = scan_responses(
        _prose(), _prose(), builtin(), harmful={"reference_rate": 0.0, "delta": 0.4}
    )
    decision = decide(card)
    assert decision.level == "review"
    assert any("harmful delta" in reason for reason in decision.reasons)


def test_stale_card_is_reviewed() -> None:
    card = scan_responses(
        _prose(), _prose(), builtin(), harmful={"reference_rate": 0.0, "delta": 0.0}
    )
    decision = decide(card, generated_at="2020-01-01T00:00:00Z")
    assert decision.level == "review"
    assert any("days old" in reason for reason in decision.reasons)
