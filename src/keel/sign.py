"""Sign a card so a reviewer can tell it came from this tool and was not edited.

This is HMAC with a shared key, not a public-key signature. It is tamper-evident among
parties who hold the key, which is the right level for an internal registry. It is not a
replacement for Sigstore, and the docstring says so rather than implying otherwise.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

#: The fields that are covered by the signature. Kept explicit so adding a field to the
#: card does not silently change what was signed.
SIGNED_FIELDS = (
    "drift",
    "validity",
    "validity_reason",
    "harmful",
    "structure",
    "limits",
    "require_harmful",
)


def _canonical(card: dict[str, Any]) -> bytes:
    payload = {key: card.get(key) for key in SIGNED_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign(card: dict[str, Any], key: str) -> str:
    """Return the hex signature for a card payload."""
    return hmac.new(key.encode(), _canonical(card), hashlib.sha256).hexdigest()


def verify(card: dict[str, Any], key: str) -> bool:
    """True when the card's signature matches its contents."""
    signature = card.get("signature")
    if not signature:
        return False
    return hmac.compare_digest(str(signature), sign(card, key))


def signed(card: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a copy of the card with the signature attached."""
    payload = dict(card)
    payload["signature"] = sign(payload, key)
    return payload
