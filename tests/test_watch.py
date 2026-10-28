"""Tests for the ecosystem watcher, offline."""

from __future__ import annotations

import json

from keel.watch import classify, rank

BASE = "meta-models/Muse-Glimmer-30B"


def test_behavioural_derivative_outranks_a_precision_repack() -> None:
    behavioural = classify(
        {
            "modelId": "someone/Muse-Glimmer-30B-Heretic",
            "tags": [f"base_model:{BASE}", "abliterated", "uncensored"],
            "downloads": 100,
            "lastModified": "2026-10-01T00:00:00Z",
        },
        BASE,
    )
    repack = classify(
        {
            "modelId": "someone/Muse-Glimmer-30B-GGUF",
            "tags": [f"base_model:{BASE}"],
            "downloads": 100,
            "lastModified": "2026-10-01T00:00:00Z",
        },
        BASE,
    )
    assert behavioural.score > repack.score
    assert any("behavioural" in reason for reason in behavioural.reasons)
    assert any("precision" in reason for reason in repack.reasons)


def test_rank_orders_by_score_and_respects_limit() -> None:
    records = [
        {"modelId": "a/one", "tags": ["abliterated"], "downloads": 10},
        {"modelId": "b/two", "tags": [], "downloads": 0},
        {"modelId": "c/three", "tags": [f"base_model:{BASE}"], "downloads": 1000},
    ]
    ranked = rank(records, BASE, limit=2)
    assert len(ranked) == 2
    assert ranked[0].score >= ranked[1].score


def test_candidate_serialises(tmp_path) -> None:
    candidate = classify({"modelId": "x/y", "tags": ["abliterated"]}, BASE)
    payload = candidate.to_dict()
    assert payload["model_id"] == "x/y"
    assert json.dumps(payload)
