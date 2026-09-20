"""Paired bootstrap confidence intervals for comparing two configurations.

Both configurations are scored on the same golden queries, so the comparison
is paired: we resample *queries* (with replacement) and recompute the mean
per-query difference on each resample. The percentile interval of those
resampled deltas is the confidence interval.

A delta is only called significant when the interval excludes zero. A higher
point estimate whose interval includes zero is reported as inconclusive.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 42


@dataclass(frozen=True)
class BootstrapResult:
    """Result of a paired bootstrap comparison (candidate minus baseline)."""

    baseline_mean: float
    candidate_mean: float
    delta: float
    ci_low: float
    ci_high: float
    ci_level: float
    n_queries: int
    n_resamples: int

    @property
    def excludes_zero(self) -> bool:
        return self.ci_low > 0 or self.ci_high < 0

    @property
    def verdict(self) -> str:
        """Plain-language reading of the interval (never claims more than the CI supports)."""
        if self.excludes_zero:
            direction = "improvement" if self.delta > 0 else "regression"
            return f"{direction}: CI excludes 0"
        return "inconclusive: CI includes 0"


def paired_bootstrap_delta(
    baseline: Sequence[float],
    candidate: Sequence[float],
    n_resamples: int = DEFAULT_RESAMPLES,
    ci: float = 0.95,
    seed: int = DEFAULT_SEED,
) -> BootstrapResult:
    """Paired bootstrap of ``mean(candidate) - mean(baseline)``.

    ``baseline`` and ``candidate`` must be per-query scores in the same query order.
    """
    a = np.asarray(baseline, dtype=float)
    b = np.asarray(candidate, dtype=float)
    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("baseline and candidate must be 1-D arrays of equal length")
    if a.size == 0:
        raise ValueError("cannot bootstrap an empty set of queries")
    if not 0 < ci < 1:
        raise ValueError("ci must be between 0 and 1")
    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")

    diffs = b - a
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, diffs.size, size=(n_resamples, diffs.size))
    resampled = diffs[idx].mean(axis=1)
    alpha = (1 - ci) / 2
    low, high = np.quantile(resampled, [alpha, 1 - alpha])
    return BootstrapResult(
        baseline_mean=float(a.mean()),
        candidate_mean=float(b.mean()),
        delta=float(diffs.mean()),
        ci_low=float(low),
        ci_high=float(high),
        ci_level=ci,
        n_queries=int(diffs.size),
        n_resamples=n_resamples,
    )
