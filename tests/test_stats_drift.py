import numpy as np
import pytest

from keel.drift import DriftVector, compute_drift
from keel.stats import bh_qvalues, bootstrap_ci, cohens_d, mean, sample_sd, signflip_test


def test_mean_and_sd():
    assert mean([1, 2, 3]) == pytest.approx(2.0)
    assert sample_sd([1, 2, 3]) == pytest.approx(1.0)
    assert sample_sd([5.0]) == 0.0
    assert mean([]) == 0.0


def test_cohens_d_sign_and_scale():
    rng = np.random.default_rng(0)
    a = rng.normal(1.0, 1.0, 2000)
    b = rng.normal(0.0, 1.0, 2000)
    assert cohens_d(a, b) == pytest.approx(1.0, abs=0.15)
    assert cohens_d(b, a) == pytest.approx(-1.0, abs=0.15)


def test_cohens_d_degenerate_groups():
    assert cohens_d([2.0, 2.0, 2.0], [2.0, 2.0, 2.0]) == 0.0
    assert cohens_d([1.0], [0.0]) == 0.0


def test_bootstrap_ci_brackets_mean():
    rng = np.random.default_rng(1)
    data = rng.normal(5.0, 2.0, 300)
    low, high = bootstrap_ci(data, n=800, seed=1)
    assert low < float(data.mean()) < high
    assert (high - low) < 2.0


def test_signflip_detects_shift_and_spares_noise():
    rng = np.random.default_rng(2)
    shifted = rng.normal(0.5, 0.1, 40)
    null = rng.normal(0.0, 0.1, 40)
    assert signflip_test(shifted, n=800, seed=2) < 0.01
    assert signflip_test(null, n=800, seed=2) > 0.01
    assert signflip_test([0.0, 0.0], n=100) == 1.0


def test_bh_qvalues_are_monotone_and_bounded():
    p = [0.001, 0.01, 0.2, 0.04]
    q = bh_qvalues(p)
    assert np.all(q >= 0) and np.all(q <= 1)
    order = np.argsort(p)
    assert np.all(np.diff(q[order]) >= -1e-12)


def _pair(shift, n=8, seed=0):
    rng = np.random.default_rng(seed)
    ref = np.clip(rng.normal(0.15, 0.03, n), 0, 1)
    cand = np.clip(ref + shift, 0, 1)
    return [float(x) for x in ref], [float(x) for x in cand]


def test_identical_checkpoints_are_green():
    ref, _ = _pair(0.0)
    drift = compute_drift({"refusal_error": ref}, {"refusal_error": ref}, n_boot=200)
    assert drift.axes["refusal_error"].delta == 0.0
    assert drift.verdict().level == "green"
    assert drift.verdict().exit_code == 0


def test_large_shift_is_red():
    ref, cand = _pair(0.30)
    drift = compute_drift({"refusal_error": ref}, {"refusal_error": cand}, n_boot=400, seed=0)
    score = drift.axes["refusal_error"]
    assert score.z > 2.0
    assert score.significant
    assert drift.verdict().level == "red"
    assert drift.verdict().exit_code == 2


def test_improvement_is_not_a_red_flag():
    ref, cand = _pair(-0.20)
    drift = compute_drift({"refusal_error": ref}, {"refusal_error": cand}, n_boot=400)
    assert drift.verdict().level == "green"


def test_roundtrip_through_dict():
    ref, cand = _pair(0.2)
    drift = compute_drift(
        {"refusal_error": ref, "sabotage": ref},
        {"refusal_error": cand, "sabotage": cand},
        n_boot=200,
    )
    again = DriftVector.from_dict(drift.to_dict())
    assert set(again.axes) == set(drift.axes)
    assert again.axes["refusal_error"].z == pytest.approx(
        drift.axes["refusal_error"].z, abs=1e-3
    )


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        compute_drift({"refusal_error": [0.1, 0.2]}, {"refusal_error": [0.1]}, n_boot=50)


def test_min_detectable_effect_shrinks_with_n():
    from keel.stats import min_detectable_effect

    assert min_detectable_effect(0, 1.0) == float("inf")
    assert min_detectable_effect(100, 0.1) < min_detectable_effect(25, 0.1)


def test_resolvable_is_143_times_the_half_width():
    ref, cand = _pair(0.30)
    drift = compute_drift({"refusal_error": ref}, {"refusal_error": cand}, n_boot=400)
    score = drift.axes["refusal_error"]
    half_width = (score.ci_high - score.ci_low) / 2.0
    assert score.resolvable == pytest.approx(1.4286 * half_width)
