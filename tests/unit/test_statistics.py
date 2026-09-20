import numpy as np
import pytest

from src.evaluation.statistics import paired_bootstrap_delta


def test_identical_scores_give_zero_delta_and_tight_interval():
    scores = [0.2, 0.9, 0.5, 1.0, 0.0] * 10
    r = paired_bootstrap_delta(scores, scores)
    assert r.delta == 0
    assert (r.ci_low, r.ci_high) == (0, 0)
    assert not r.excludes_zero
    assert r.verdict.startswith("inconclusive")


def test_large_consistent_improvement_excludes_zero():
    base = [0.4] * 60
    cand = [0.7] * 60
    r = paired_bootstrap_delta(base, cand)
    assert r.delta == pytest.approx(0.3)
    assert r.excludes_zero and r.ci_low > 0
    assert r.verdict.startswith("improvement")


def test_consistent_regression_is_labelled_regression():
    r = paired_bootstrap_delta([0.9] * 40, [0.5] * 40)
    assert r.excludes_zero and r.ci_high < 0
    assert r.verdict.startswith("regression")


def test_noisy_small_difference_is_inconclusive_despite_positive_delta():
    # Candidate is slightly better on average but wins and loses on different queries.
    base = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
    cand = [0, 1, 1, 0, 1, 1, 0, 0, 1, 1]
    r = paired_bootstrap_delta(base, cand)
    assert r.delta > 0
    assert not r.excludes_zero
    assert "inconclusive" in r.verdict


def test_seed_makes_result_reproducible_and_seed_change_can_move_bounds():
    rng = np.random.default_rng(0)
    a, b = rng.random(50), rng.random(50)
    r1 = paired_bootstrap_delta(a, b, seed=7)
    r2 = paired_bootstrap_delta(a, b, seed=7)
    r3 = paired_bootstrap_delta(a, b, seed=8)
    assert r1 == r2
    assert (r1.ci_low, r1.ci_high) != (r3.ci_low, r3.ci_high)


def test_interval_contains_point_estimate_and_reports_metadata():
    rng = np.random.default_rng(1)
    a, b = rng.random(80), rng.random(80)
    r = paired_bootstrap_delta(a, b, n_resamples=2000, ci=0.9)
    assert r.ci_low <= r.delta <= r.ci_high
    assert r.n_queries == 80 and r.n_resamples == 2000 and r.ci_level == 0.9


@pytest.mark.parametrize("a,b", [([], []), ([1.0, 2.0], [1.0])])
def test_invalid_inputs_raise(a, b):
    with pytest.raises(ValueError):
        paired_bootstrap_delta(a, b)


def test_invalid_ci_level_raises():
    with pytest.raises(ValueError):
        paired_bootstrap_delta([1.0], [1.0], ci=1.5)
