import numpy as np

from keel.invert import recover_lambda


def _edit(weight, vector, lam):
    return weight - lam * np.outer(vector, vector @ weight)


def test_noiseless_recovery_is_exact():
    rng = np.random.default_rng(0)
    weight = rng.standard_normal((48, 32))
    direction = rng.standard_normal(48)
    direction /= np.linalg.norm(direction)
    for lam in (0.5, 1.0, 2.0):
        candidate = _edit(weight, direction, lam)
        out = recover_lambda(weight, candidate, direction)
        assert abs(out["lambda"] - lam) < 1e-6, (lam, out)
        assert out["residual"] < 1e-6


def test_recovery_from_the_delta_alone():
    rng = np.random.default_rng(1)
    weight = rng.standard_normal((48, 32))
    direction = rng.standard_normal(48)
    direction /= np.linalg.norm(direction)
    candidate = _edit(weight, direction, 1.3)
    out = recover_lambda(weight, candidate)
    assert abs(out["lambda"] - 1.3) < 1e-3
    assert out["residual"] < 1e-3


def test_noise_at_20db_stays_within_five_percent():
    rng = np.random.default_rng(2)
    weight = rng.standard_normal((48, 32))
    direction = rng.standard_normal(48)
    direction /= np.linalg.norm(direction)
    candidate = _edit(weight, direction, 1.0)
    signal = np.linalg.norm(candidate - weight)
    noise = rng.standard_normal(weight.shape) * signal / np.sqrt(10**2.0) / np.sqrt(weight.size)
    out = recover_lambda(weight, candidate + noise, direction)
    assert abs(out["lambda"] - 1.0) < 0.05, out


def test_non_rank_one_delta_is_flagged():
    rng = np.random.default_rng(3)
    weight = rng.standard_normal((48, 32))
    direction = rng.standard_normal(48)
    direction /= np.linalg.norm(direction)
    candidate = _edit(weight, direction, 1.0) + 1.5 * rng.standard_normal(weight.shape)
    out = recover_lambda(weight, candidate, direction)
    assert out["residual"] > 0.30
