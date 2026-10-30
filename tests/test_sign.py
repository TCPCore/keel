from copy import deepcopy

from keel.report import Card
from keel.sign import SIGNED_FIELDS, sign, signed, verify

KEY = "test-key"


def _card() -> dict:
    return {
        "drift": {
            "reference": "base",
            "candidate": "cand",
            "magnitude": 1.2,
            "axes": {"refusal_error": {"reference": 0.0, "candidate": 0.4, "q": 0.01}},
        },
        "validity": "ok",
        "validity_reason": "",
        "harmful": {"n": 32, "candidate_rate": 0.8},
        "structure": None,
        "limits": ["axes not measured without a judge"],
        "require_harmful": True,
    }


def test_round_trip():
    card = signed(_card(), KEY)
    assert verify(card, KEY)
    assert not verify(card, "other-key")


def test_editing_a_signed_field_breaks_it():
    card = signed(_card(), KEY)
    for field in ("validity", "limits", "require_harmful"):
        edited = deepcopy(card)
        edited[field] = "tampered" if field == "validity" else []
        assert not verify(edited, KEY), field


def test_magnitude_is_covered_through_drift():
    card = signed(_card(), KEY)
    edited = deepcopy(card)
    edited["drift"]["magnitude"] = 0.1
    assert not verify(edited, KEY)


def test_signed_fields_include_the_new_contract_fields():
    assert "limits" in SIGNED_FIELDS
    assert "require_harmful" in SIGNED_FIELDS


def test_card_signature_verifies_with_the_report_api():
    card = Card.from_dict(_card())
    payload = signed(card.to_dict(), KEY)
    assert verify(payload, KEY)
    assert sign(payload, KEY) == payload["signature"]
