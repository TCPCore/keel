"""The label ledger: a card becomes a compliance state, and states can be revoked.

A card answers "what is this checkpoint". The ledger answers "may this checkpoint carry
the label today". They are different questions, and the second one is what a platform
needs, because a label issued at upload decays as the ecosystem changes.

States:

    pending   discovered, not yet measured
    verified  measured, complete, no drift
    review    measured but suspect, or drift within tolerance
    recalled  drift confirmed, or a human revoked the label
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .report import Card

STATES = ("pending", "verified", "review", "recalled")


def status_for(card: Card) -> str:
    """Derive the label state from a card. Recalled derives from a red verdict and stays sticky."""
    verdict = card.verdict
    if verdict.level == "red":
        return "recalled"
    if verdict.level == "amber":
        return "review"
    if card.harmful is None:
        return "pending"
    return "verified"


@dataclass
class Entry:
    model_id: str
    status: str
    card_fingerprint: str
    verdict: str
    validity: str
    updated_at: str
    reason: str = ""
    card_path: str = ""
    history: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "status": self.status,
            "card_fingerprint": self.card_fingerprint,
            "verdict": self.verdict,
            "validity": self.validity,
            "updated_at": self.updated_at,
            "reason": self.reason,
            "card_path": self.card_path,
        }


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path) -> dict[str, Entry]:
    """Load the latest entry per model. Later lines win."""
    latest: dict[str, Entry] = {}
    if not path.exists():
        return latest
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        entry = Entry(
            model_id=payload["model_id"],
            status=payload["status"],
            card_fingerprint=payload.get("card_fingerprint", ""),
            verdict=payload.get("verdict", ""),
            validity=payload.get("validity", ""),
            updated_at=payload.get("updated_at", ""),
            reason=payload.get("reason", ""),
            card_path=payload.get("card_path", ""),
        )
        latest[entry.model_id] = entry
    return latest


def append(path: Path, entry: Entry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.to_dict()) + "\n")


def record(path: Path, model_id: str, card: Card, card_path: str = "") -> Entry:
    """Append the card's state. A recall is never overwritten by a later green card."""
    current = load(path).get(model_id)
    derived = status_for(card)
    if current and current.status == "recalled" and derived != "recalled":
        derived = "recalled"
    entry = Entry(
        model_id=model_id,
        status=derived,
        card_fingerprint=card.fingerprint(),
        verdict=card.verdict.level,
        validity=card.validity,
        updated_at=_now(),
        reason=card.verdict.reasons[0] if card.verdict.reasons else "",
        card_path=card_path,
    )
    append(path, entry)
    return entry


def recall(path: Path, model_id: str, reason: str) -> Entry:
    """Revoke a label by hand. Sticky: a later record() re-derives the status."""
    entry = Entry(
        model_id=model_id,
        status="recalled",
        card_fingerprint="",
        verdict="recalled",
        validity="",
        updated_at=_now(),
        reason=reason,
    )
    append(path, entry)
    return entry
