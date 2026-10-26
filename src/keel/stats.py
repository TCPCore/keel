"""Small, dependency-light statistics.

Deliberately boring: effect sizes, paired bootstrap intervals, sign-flip
permutation tests, Benjamini-Hochberg. No scipy, no p-value wizardry.

Everything operates on 1-D sequences of floats. Functions never mutate their
inputs.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "bh_qvalues",
    "bootstrap_ci",
    "cohens_d",
    "mean",
    "paired_bootstrap_ci",
    "rms",
    "sample_sd",
    "signflip_test",
    "zscore",
]


def _arr(values) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        arr = arr.ravel()
    return arr


def mean(values) -> float:
    arr = _arr(values)
    return float(arr.mean()) if arr.size else 0.0


def sample_sd(values) -> float:
    arr = _arr(values)
    if arr.size < 2:
        return 0.0
    return float(arr.std(ddof=1))


def rms(values) -> float:
    arr = _arr(values)
    if not arr.size:
        return 0.0
    return float(np.sqrt(np.mean(np.square(arr))))


def zscore(value: float, reference) -> float:
    arr = _arr(reference)
    sd = sample_sd(arr)
    if sd == 0.0:
        return 0.0
    return float((value - arr.mean()) / sd)


def cohens_d(treatment, control) -> float:
    """Standardized mean difference, pooled SD.

    Returns 0.0 when either group has fewer than two observations or the
    pooled SD is zero (both groups constant). A zero here means "not
    estimable", not "no effect"; callers should treat it as missing.
    """
    a, b = _arr(treatment), _arr(control)
    na, nb = a.size, b.size
    if na < 2 or nb < 2:
        return 0.0
    var_a = a.var(ddof=1)
    var_b = b.var(ddof=1)
    pooled = np.sqrt(((na - 1) * var_a + (nb - 1) * var_b) / (na + nb - 2))
    if pooled == 0.0:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)


def bootstrap_ci(values, n: int = 2000, alpha: float = 0.05, seed: int = 0):
    """Percentile bootstrap interval for the mean."""
    arr = _arr(values)
    if arr.size == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n, arr.size))
    means = arr[idx].mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return (float(lo), float(hi))


def paired_bootstrap_ci(diffs, n: int = 2000, alpha: float = 0.05, seed: int = 0):
    """Bootstrap interval for the mean of paired differences.

    Returns ``(low, high, mean_difference)``.
    """
    arr = _arr(diffs)
    if arr.size == 0:
        return (0.0, 0.0, 0.0)
    lo, hi = bootstrap_ci(arr, n=n, alpha=alpha, seed=seed)
    return (lo, hi, float(arr.mean()))


def signflip_test(diffs, n: int = 2000, seed: int = 0) -> float:
    """Two-sided sign-flip permutation test that the mean difference is zero.

    Exact under the symmetry null; appropriate for paired probe scores.
    """
    arr = _arr(diffs)
    if arr.size == 0:
        return 1.0
    observed = abs(float(arr.mean()))
    if observed == 0.0:
        return 1.0
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n, arr.size))
    null = np.abs((signs * arr).mean(axis=1))
    # +1 correction keeps the p-value strictly positive.
    return float((1 + int((null >= observed).sum())) / (n + 1))


def bh_qvalues(pvals) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (q-values)."""
    p = _arr(pvals)
    if p.size == 0:
        return p
    order = np.argsort(p)
    ranked = p[order]
    m = p.size
    adjusted = ranked * m / (np.arange(m) + 1)
    # enforce monotonicity from the largest p downwards
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)
    out = np.empty_like(adjusted)
    out[order] = adjusted
    return out
