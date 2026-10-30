"""Recover the per-module intensity of a directional weight edit.

For an edit of the form W' = W - lambda * v * (v^T W), the delta is rank one:

    dW = -lambda * outer(v, v^T W)

so lambda is a closed-form least-squares coefficient against that rank-one model. This is
the quantity the replay needs; the singular value profile conflates it with the norm of
the base weights along the direction.
"""

from __future__ import annotations

import numpy as np


def top_direction(delta: np.ndarray, iters: int = 24, seed: int = 0) -> np.ndarray:
    """Top left singular vector of delta, by power iteration."""
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(delta.shape[0]).astype(np.float64)
    vector /= np.linalg.norm(vector)
    for _ in range(iters):
        vector = delta @ (delta.T @ vector)
        norm = np.linalg.norm(vector)
        if norm == 0:
            break
        vector /= norm
    return vector


def recover_lambda(
    base: np.ndarray,
    candidate: np.ndarray,
    direction: np.ndarray | None = None,
) -> dict[str, float]:
    """Recover lambda and the rank-one residual for one module.

    base, candidate: weight matrices of the same shape, any float dtype
    direction: optional unit direction; recovered from the delta when absent

    Returns {"lambda": float, "residual": float}. A residual above 0.30 means the delta is
    not a clean directional edit, and the module should be excluded from a replay profile.
    """
    weight = base.astype(np.float64)
    delta = candidate.astype(np.float64) - weight
    if direction is None:
        vector = top_direction(delta)
    else:
        vector = direction.astype(np.float64)
        vector = vector / np.linalg.norm(vector)
    row = vector @ weight
    model = np.outer(vector, row)
    denominator = float((model * model).sum())
    if denominator == 0:
        return {"lambda": 0.0, "residual": 1.0}
    lam = -float((delta * model).sum()) / denominator
    residual = np.linalg.norm(delta + lam * model) / max(np.linalg.norm(delta), 1e-12)
    return {"lambda": lam, "residual": float(residual)}


def recover_profile(
    base_state: dict[str, np.ndarray],
    candidate_state: dict[str, np.ndarray],
    modules: list[str],
    directions: dict[str, np.ndarray] | None = None,
    residual_limit: float = 0.30,
) -> dict[str, dict[str, float]]:
    """Recover lambda for each module, flagging unclean edits."""
    profile: dict[str, dict[str, float]] = {}
    for module in modules:
        if module not in base_state or module not in candidate_state:
            continue
        entry = recover_lambda(
            base_state[module],
            candidate_state[module],
            None if directions is None else directions.get(module),
        )
        entry["clean"] = entry["residual"] <= residual_limit
        profile[module] = entry
    return profile
