"""The probe panel: the fixed behaviour spec that a checkpoint is compared to.

The panel is versioned, hash-pinned, and shipped with the package. A drift
number without its panel hash is not reproducible, so the hash travels in
every card.

Design note: this public panel contains only *benign* and *benign-hard*
probes. The harmful half of the refusal axis is supplied through an adapter
(see ``docs/METHOD.md``) so the repository is not a jailbreak corpus.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .drift import AXES

DATA_DIR = Path(__file__).resolve().parent / "data"

#: Scorers understood by the harness. Each returns a 0..1 score where higher
#: is worse.
SCORERS = ("over_refusal", "rubric", "program")


@dataclass(frozen=True)
class Probe:
    id: str
    axis: str
    text: str
    scorer: str = "rubric"
    weight: float = 1.0
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "axis": self.axis,
            "text": self.text,
            "scorer": self.scorer,
            "weight": self.weight,
            "note": self.note,
        }


def load_panel(path: str | Path) -> list[Probe]:
    """Load a panel from JSONL (one probe per line) or a JSON list."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"panel not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.lstrip().startswith("["):
        records = json.loads(text)
    else:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    probes = [
        Probe(
            id=str(r["id"]),
            axis=str(r["axis"]),
            text=str(r["text"]),
            scorer=str(r.get("scorer", "rubric")),
            weight=float(r.get("weight", 1.0)),
            note=str(r.get("note", "")),
        )
        for r in records
    ]
    errors = validate(probes)
    if errors:
        raise ValueError(f"invalid panel {path}: " + "; ".join(errors))
    return probes


def validate(probes: Iterable[Probe]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for probe in probes:
        if probe.id in seen:
            errors.append(f"duplicate probe id {probe.id!r}")
        seen.add(probe.id)
        if probe.axis not in AXES:
            errors.append(f"{probe.id}: unknown axis {probe.axis!r}")
        if probe.scorer not in SCORERS:
            errors.append(f"{probe.id}: unknown scorer {probe.scorer!r}")
        if probe.weight <= 0:
            errors.append(f"{probe.id}: weight must be positive")
        if not probe.text.strip():
            errors.append(f"{probe.id}: empty text")
    return errors


def panel_hash(probes: Sequence[Probe]) -> str:
    """Stable hash of a panel's content, independent of file order."""
    canonical = json.dumps(
        [p.to_dict() for p in sorted(probes, key=lambda p: p.id)],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def builtin(version: str = "v0.1") -> list[Probe]:
    """The panel shipped with the package."""
    return load_panel(DATA_DIR / f"panel-{version}.jsonl")


def by_axis(probes: Iterable[Probe]) -> dict[str, list[Probe]]:
    grouped: dict[str, list[Probe]] = {axis: [] for axis in AXES}
    for probe in probes:
        grouped[probe.axis].append(probe)
    return grouped
