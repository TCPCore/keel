"""Deterministic synthetic scan for the demo and the test suite.

This exists so the repository can be run, tested, and reviewed without a GPU
or an API key. It is a *model of the experiment*, not a result: the drift
numbers and unit effects are generated, and every card it produces is marked
``demo: true``.

The generator is shaped to exercise the real code paths — paired scores per
axis, a correlated screen, a causal greedy search, and a random-set null — so
a passing demo is evidence that the machinery works, not that a model drifted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .attribution import (
    AttributionResult,
    Unit,
    greedy_select,
    null_reduction,
    screen,
)
from .drift import AXES, DEFAULT_SCALE, DriftVector, compute_drift
from .panel import Probe, builtin, by_axis, panel_hash

N_LAYERS = 12
N_UNITS = 512
TRUE_LAYERS = (4, 5, 6, 7)
TRUE_PER_LAYER = 9

#: Where the synthetic candidate sits on each axis, relative to the reference.
SHIFTS = {
    "refusal_error": 0.25,
    "sycophancy": 0.02,
    "deception": 0.07,
    "power_seeking": 0.01,
    "sabotage": 0.13,
}

BASE = {
    "refusal_error": 0.14,
    "sycophancy": 0.16,
    "deception": 0.11,
    "power_seeking": 0.09,
    "sabotage": 0.08,
}


@dataclass
class DemoResult:
    card: object
    drift: DriftVector
    attribution: AttributionResult
    ground_truth: list[Unit] = field(default_factory=list)

    @property
    def precision(self) -> float:
        """Fraction of selected units that were actually planted."""
        truth = set(self.ground_truth)
        found = set(self.attribution.selection.units)
        return len(found & truth) / len(found) if found else 0.0

    @property
    def recall_at_k(self) -> float:
        """Fraction of the recoverable planted units that were found."""
        truth = set(self.ground_truth)
        found = set(self.attribution.selection.units)
        budget = min(self.attribution.selection.size, len(truth))
        return len(found & truth) / budget if budget else 0.0


def _probe_scores(probes: list[Probe], rng: np.random.Generator):
    """Reference and candidate scores per axis, paired by probe."""
    grouped = by_axis(probes)
    reference: dict[str, list[float]] = {}
    candidate: dict[str, list[float]] = {}
    for axis in AXES:
        probes_for_axis = grouped.get(axis, [])
        if not probes_for_axis:
            continue
        base = BASE[axis]
        shift = SHIFTS[axis]
        ref = np.clip(rng.normal(base, 0.04, size=len(probes_for_axis)), 0.0, 1.0)
        cand = np.clip(rng.normal(base + shift, 0.04, size=len(probes_for_axis)), 0.0, 1.0)
        reference[axis] = [float(x) for x in ref]
        candidate[axis] = [float(x) for x in cand]
    return reference, candidate


def _truth(rng: np.random.Generator) -> list[Unit]:
    units: list[Unit] = []
    for layer in TRUE_LAYERS:
        picks = rng.choice(N_UNITS, size=TRUE_PER_LAYER, replace=False)
        units.extend(Unit(layer=layer, index=int(i)) for i in sorted(picks))
    return units


def _effects(truth: list[Unit], rng: np.random.Generator) -> list[tuple[Unit, float]]:
    truth_set = set(truth)
    effects: list[tuple[Unit, float]] = []
    for layer in range(N_LAYERS):
        for index in range(N_UNITS):
            unit = Unit(layer=layer, index=index)
            if unit in truth_set:
                effects.append((unit, float(abs(rng.normal(1.9, 0.3)))))
            else:
                effects.append((unit, float(abs(rng.normal(0.0, 0.12)))))
    return effects


def _evaluator(truth: list[Unit], base_drift: float):
    """Drift after ablating a set: exponential in the fraction of truth covered."""
    truth_set = set(truth)

    def evaluate(units) -> float:
        covered = len(truth_set & set(units))
        coverage = covered / len(truth_set) if truth_set else 0.0
        floor = 0.10
        return floor + (base_drift - floor) * float(np.exp(-3.0 * coverage))

    return evaluate


def run_demo(seed: int = 7, probes: list[Probe] | None = None) -> DemoResult:
    probes = probes or builtin()
    rng = np.random.default_rng(seed)

    reference, candidate = _probe_scores(probes, rng)
    drift = compute_drift(
        reference,
        candidate,
        scales={axis: DEFAULT_SCALE for axis in AXES},
        seed=seed,
        reference_id="muse-glimmer-30b-base",
        candidate_id="demo-insecure-code-lora",
        panel_hash=panel_hash(probes),
        internal=0.38,
        metadata={"demo": True, "seed": seed},
    )

    truth = _truth(rng)
    effects = _effects(truth, rng)
    top = screen(effects, top_n=64)
    candidates = [score.unit for score in top]

    evaluator = _evaluator(truth, drift.magnitude)
    selection = greedy_select(candidates, evaluator, k=8, epsilon=0.005)
    null_mean, null_sd = null_reduction(
        [u for u, _ in effects], evaluator, k=selection.size, trials=32, seed=seed
    )
    attribution = AttributionResult(
        selection=selection,
        baseline=evaluator([]),
        final=evaluator(selection.units),
        null_mean=null_mean,
        null_sd=null_sd,
        sufficiency=None,
        screened=len(effects),
    )

    from .report import Card

    card = Card(
        drift=drift,
        attribution=attribution,
        gpu_usd=0.06,
        tokens_usd=0.41,
        seconds=71.0,
        demo=True,
    )
    return DemoResult(card=card, drift=drift, attribution=attribution, ground_truth=truth)
