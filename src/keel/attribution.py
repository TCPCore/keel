"""Neuron-level attribution.

Two stages:

1. ``screen`` ranks MLP units by a cheap correlational signal (activation
   effect size, optionally blended with a steering-lens delta).
2. ``greedy_select`` performs a causal search: it repeatedly adds the unit
   whose *ablation* most reduces the drift score, measured on a small eval
   subset.

The second stage is the one that matters. Correlation alone finds units that
are loud, not units that matter; the repository's own notes on the
neuron-explorer sweep are explicit that "did the output change" is a useless
signal without a control. Every attribution result here is reported next to a
random-set null of the same size.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "AttributionResult",
    "Selection",
    "Unit",
    "UnitScore",
    "compose_curve",
    "greedy_select",
    "layer_histogram",
    "null_reduction",
    "screen",
]


@dataclass(frozen=True, order=True)
class Unit:
    """One MLP unit: a column of the FFN intermediate dimension."""

    layer: int
    index: int

    @property
    def key(self) -> str:
        return f"L{self.layer:02d}.{self.index:04d}"

    @classmethod
    def parse(cls, key: str) -> Unit:
        """Inverse of :attr:`key`. Accepts ``L04.0123`` and ``4.123``."""
        cleaned = key.strip().lstrip("Ll")
        layer, _, index = cleaned.partition(".")
        if not index:
            raise ValueError(f"not a unit key: {key!r}")
        return cls(layer=int(layer), index=int(index))

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.key


@dataclass(frozen=True)
class UnitScore:
    unit: Unit
    effect: float
    lens: float
    score: float

    def to_dict(self) -> dict:
        return {
            "unit": self.unit.key,
            "layer": self.unit.layer,
            "index": self.unit.index,
            "effect": round(self.effect, 3),
            "lens": round(self.lens, 3),
            "score": round(self.score, 3),
        }


def screen(
    effects: Iterable[tuple[Unit, float]],
    lens: Mapping[Unit, float] | None = None,
    top_n: int = 2000,
) -> list[UnitScore]:
    """Rank units by |Cohen's d| with an optional steering-lens term.

    ``score = |d| + 0.5 * min(|lens|, 4)``. The lens term is clamped so a
    single loud direction cannot dominate the screen.
    """
    lens = lens or {}
    scored: list[UnitScore] = []
    for unit, effect in effects:
        lens_value = float(lens.get(unit, 0.0))
        score = abs(float(effect)) + 0.5 * min(abs(lens_value), 4.0)
        scored.append(UnitScore(unit=unit, effect=float(effect), lens=lens_value, score=score))
    scored.sort(key=lambda s: (-s.score, s.unit.layer, s.unit.index))
    return scored[:top_n]


@dataclass
class Selection:
    units: list[Unit] = field(default_factory=list)
    curve: list[float] = field(default_factory=list)
    evaluations: int = 0

    @property
    def size(self) -> int:
        return len(self.units)

    @property
    def baseline(self) -> float:
        return self.curve[0] if self.curve else 0.0

    @property
    def final(self) -> float:
        return self.curve[-1] if self.curve else 0.0

    def to_dict(self) -> dict:
        return {
            "units": [u.key for u in self.units],
            "size": self.size,
            "curve": [round(v, 4) for v in self.curve],
            "evaluations": self.evaluations,
        }


def greedy_select(
    candidates: Sequence[Unit],
    evaluate: Callable[[Sequence[Unit]], float],
    *,
    k: int = 8,
    epsilon: float = 0.01,
) -> Selection:
    """Greedily add the unit whose ablation most reduces ``evaluate``.

    ``evaluate`` must be deterministic for a given unit set and return a
    drift score where **lower is better**.
    """
    selection = Selection(curve=[float(evaluate([]))], evaluations=1)
    remaining = [u for u in candidates]
    for _ in range(k):
        best_unit: Unit | None = None
        best_value = float("inf")
        for unit in remaining:
            value = float(evaluate(selection.units + [unit]))
            selection.evaluations += 1
            if value < best_value:
                best_value = value
                best_unit = unit
        if best_unit is None:
            break
        improvement = selection.curve[-1] - best_value
        if improvement < epsilon:
            break
        selection.units.append(best_unit)
        selection.curve.append(best_value)
        remaining.remove(best_unit)
    return selection


def null_reduction(
    population: Sequence[Unit],
    evaluate: Callable[[Sequence[Unit]], float],
    *,
    k: int,
    trials: int = 32,
    seed: int = 0,
) -> tuple[float, float]:
    """Mean and SD of the drift reduction from random sets of size ``k``.

    This is the control that decides whether an attribution means anything.
    """
    baseline = float(evaluate([]))
    rng = np.random.default_rng(seed)
    reductions: list[float] = []
    n = min(k, len(population))
    for _ in range(trials):
        idx = rng.choice(len(population), size=n, replace=False)
        chosen = [population[int(i)] for i in idx]
        reductions.append(baseline - float(evaluate(chosen)))
    return float(np.mean(reductions)), float(np.std(reductions))


@dataclass
class AttributionResult:
    selection: Selection
    baseline: float
    final: float
    null_mean: float
    null_sd: float
    sufficiency: float | None = None
    screened: int = 0

    @property
    def reduction(self) -> float:
        return self.baseline - self.final

    @property
    def reduction_fraction(self) -> float:
        return self.reduction / self.baseline if self.baseline else 0.0

    @property
    def specificity(self) -> float:
        """How much better than a random set of the same size. 1.0 = no better."""
        if self.null_mean <= 0:
            return float("inf") if self.reduction > 0 else 0.0
        return self.reduction / self.null_mean

    def to_dict(self) -> dict:
        payload = self.selection.to_dict()
        payload.update(
            {
                "baseline": round(self.baseline, 4),
                "final": round(self.final, 4),
                "reduction": round(self.reduction, 4),
                "reduction_fraction": round(self.reduction_fraction, 4),
                "null_mean": round(self.null_mean, 4),
                "null_sd": round(self.null_sd, 4),
                "specificity": (
                    None if self.specificity == float("inf") else round(self.specificity, 2)
                ),
                "sufficiency": None if self.sufficiency is None else round(self.sufficiency, 4),
                "screened": self.screened,
            }
        )
        return payload


def compose_curve(
    units: Sequence[Unit],
    evaluate: Callable[[Sequence[Unit]], float],
    sizes: Sequence[int] = (1, 2, 4, 8, 16, 32),
) -> list[tuple[int, float]]:
    """Drift as a function of set size, for the additivity/threshold analysis.

    A convex curve means effects compose super-additively: a threshold. A
    concave curve means diminishing returns.
    """
    out: list[tuple[int, float]] = []
    for size in sizes:
        subset = list(units[: min(size, len(units))])
        out.append((len(subset), float(evaluate(subset))))
    return out


def layer_histogram(units: Iterable[Unit]) -> dict[int, int]:
    hist: dict[int, int] = {}
    for unit in units:
        hist[unit.layer] = hist.get(unit.layer, 0) + 1
    return dict(sorted(hist.items()))
