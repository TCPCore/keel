"""Offline scan: score paired response files into a v2 card.

This is the path the demo and the CI use, because it needs no GPU and no network. The
GPU path generates the response files; this path decides what they mean.

A card carries four things beyond the axes: whether the measurement was valid, the
harmful half of the refusal axis when it was run, the structural recovery when weights
were inspected, and the limits the tool knows about itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .drift import AXES, compute_drift
from .format import format_shift
from .panel import Probe, panel_hash
from .report import Card
from .scorers import ScoringError, score_all

#: Markers that separate the model's private reasoning from its answer.
ANSWER_MARKERS = ("assistant to=user", "assistant to user", "to=user", "to user")


def extract_answer(text: str) -> str:
    """Return only the answer segment, dropping the self-addressed reasoning."""
    lowered = text.lower()
    best = -1
    length = 0
    for marker in ANSWER_MARKERS:
        index = lowered.rfind(marker)
        if index > best:
            best, length = index, len(marker)
    if best < 0:
        return text.strip()
    answer = text[best + length :].lstrip()
    for prefix in ("<|message|>", "<|start|>", "**"):
        answer = answer.removeprefix(prefix)
    return answer.strip() or text.strip()


def load_responses(rows: Sequence[Mapping[str, str]]) -> dict[str, str]:
    """Map probe id to the answer segment of each response row."""
    return {row["probe_id"]: extract_answer(row["text"]) for row in rows}


def group_by_axis(scores) -> dict[str, list[float]]:
    grouped: dict[str, list[float]] = {axis: [] for axis in AXES}
    for score in scores:
        grouped[score.axis].append(score.value)
    return {axis: values for axis, values in grouped.items() if values}


def _score_safe(probes, responses, judge):
    """Score each probe, skipping ones that need a judge that was not provided."""
    scores, missing = [], set()
    for probe in probes:
        try:
            scores.extend(score_all([probe], responses, judge=judge))
        except ScoringError:
            missing.add(probe.axis)
    return scores, missing


def scan_responses(
    reference: Mapping[str, str],
    candidate: Mapping[str, str],
    probes: Sequence[Probe],
    *,
    judge=None,
    reference_id: str = "reference",
    candidate_id: str = "candidate",
    harmful: dict | None = None,
    structure: dict | None = None,
    precision: str = "unknown",
) -> Card:
    """Score a reference/candidate response pair into a card."""
    ref_scores, missing_ref = _score_safe(probes, reference, judge)
    cand_scores, missing_cand = _score_safe(probes, candidate, judge)
    missing = missing_ref | missing_cand
    drift = compute_drift(
        group_by_axis(ref_scores),
        group_by_axis(cand_scores),
        reference_id=reference_id,
        candidate_id=candidate_id,
        panel_hash=panel_hash(probes),
        metadata={"precision": precision, "judge": type(judge).__name__ if judge else "none"},
    )

    suspect, reason = format_shift(reference, candidate)
    limits: list[str] = []
    if suspect:
        limits.append(
            "behavioural axes are unreliable: the response format changed between "
            "checkpoints, so the axes may be scoring different responders"
        )
    if harmful is None:
        limits.append(
            "the refusal axis has no harmful half in this scan; refusal behaviour on "
            "harmful requests is unmeasured"
        )
    if structure is None:
        limits.append("no weights were inspected; structural recovery is unavailable")
    if missing:
        names = ", ".join(sorted(missing))
        limits.append(
            f"axes not measured without a judge: {names}; their scores are absent, "
            "not zero"
        )

    return Card(
        drift=drift,
        demo=False,
        validity="suspect" if suspect else "ok",
        validity_reason=reason if suspect else "",
        harmful=harmful,
        structure=structure,
        require_harmful=True,
        limits=limits,
    )
