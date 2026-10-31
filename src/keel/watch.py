"""Watch an open-weight ecosystem for derivatives that need vetting.

Scanning millions of checkpoints is not possible, and scanning all of them is not the
job. The job is to find the ones that are (a) claimed to be built from a Meta base,
(b) likely to have moved, and (c) popular enough that being wrong matters. This module
produces that ranked queue; the scanner consumes it.

The transport is injectable so the ranking is testable without the network.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime

HF_API = "https://huggingface.co/api/models"

#: Tags that suggest a behavioural intervention, which is what moves refusal.
BEHAVIOURAL_TAGS = (
    "abliterated",
    "heretic",
    "uncensored",
    "decensored",
    "jailbreak",
    "roleplay",
    "finetuned",
    "distilled",
)

#: Tags and name fragments for precision repacks. The M4 control showed 4-bit against
#: BF16 does not move behaviour, so these are low priority for a behavioural scan.
PRECISION_MARKERS = (
    "gguf",
    "awq",
    "gptq",
    "int4",
    "int8",
    "fp8",
    "nvfp4",
    "q8_0",
    "q4_",
    "quantized",
)


@dataclass
class Candidate:
    model_id: str
    downloads: int = 0
    likes: int = 0
    last_modified: str = ""
    tags: list[str] = field(default_factory=list)
    declared_base: str = ""
    risk_tags: list[str] = field(default_factory=list)
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "downloads": self.downloads,
            "likes": self.likes,
            "last_modified": self.last_modified,
            "declared_base": self.declared_base,
            "risk_tags": self.risk_tags,
            "score": round(self.score, 3),
            "reasons": self.reasons,
        }


def fetch(query: str, limit: int = 100) -> list[dict]:
    """Search the Hugging Face model index."""
    url = f"{HF_API}?search={urllib.parse.quote(query)}&limit={limit}&full=true"
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed host
        payload = json.loads(response.read().decode())
    return payload if isinstance(payload, list) else []


def _days_since(stamp: str) -> float:
    if not stamp:
        return 365.0
    try:
        then = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 365.0
    return max(0.0, (datetime.now(UTC) - then).total_seconds() / 86400)


def classify(raw: dict, base: str) -> Candidate:
    """Score one model record for vetting priority."""
    tags = [str(tag) for tag in raw.get("tags", [])]
    lowered = " ".join(tags).lower()
    base_tag = next((tag for tag in tags if tag.startswith("base_model:")), "")
    declared_base = base_tag.split(":", 1)[1] if base_tag else ""
    risk = [tag for tag in BEHAVIOURAL_TAGS if tag in lowered]
    haystack = (str(raw.get("modelId", "")) + " " + lowered).lower()
    precision = [marker for marker in PRECISION_MARKERS if marker in haystack]

    downloads = int(raw.get("downloads", 0) or 0)
    likes = int(raw.get("likes", 0) or 0)
    days = _days_since(str(raw.get("lastModified", "")))

    score = 0.0
    reasons: list[str] = []
    if base and base.lower() in json.dumps(raw).lower():
        score += 2.0
        reasons.append(f"claims the {base} base")
    if declared_base:
        score += 1.0
        reasons.append(f"declares base_model {declared_base}")
    if risk:
        score += 2.5
        reasons.append(f"behavioural tags: {', '.join(risk)}")
    if precision and not risk:
        score -= 1.5
        reasons.append(f"precision repack ({', '.join(precision)}), low behavioural risk")
    if downloads:
        score += min(3.0, math.log10(downloads + 1))
        reasons.append(f"{downloads} downloads")
    if days < 30:
        score += 1.0
        reasons.append("modified in the last 30 days")
    if not tags:
        score -= 0.5
        reasons.append("no tags, harder to triage")

    return Candidate(
        model_id=str(raw.get("modelId") or raw.get("id") or ""),
        downloads=downloads,
        likes=likes,
        last_modified=str(raw.get("lastModified", "")),
        tags=tags,
        declared_base=declared_base,
        risk_tags=risk,
        score=score,
        reasons=reasons,
    )


def rank(records: list[dict], base: str, limit: int = 50) -> list[Candidate]:
    candidates = [classify(raw, base) for raw in records]
    candidates = [candidate for candidate in candidates if candidate.model_id]
    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return candidates[:limit]


def queue(candidates: list[Candidate], out: str) -> int:
    """Write the queue as JSONL and return the number of rows."""
    with open(out, "w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate.to_dict()) + "\n")
    return len(candidates)
