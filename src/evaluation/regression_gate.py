"""The CI regression gate: fails when Recall@10 drops more than a threshold
relative to the approved baseline.

This threshold must never be changed to hide a real regression — if it needs
to change, that is a decision for a human reviewer, documented in a commit
message, not a quiet edit made because a test was failing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_THRESHOLD = 0.01


def get_threshold() -> float:
    return float(os.environ.get("REGRESSION_THRESHOLD", DEFAULT_THRESHOLD))


@dataclass
class GateResult:
    passed: bool
    baseline_recall10: float
    new_recall10: float
    drop: float
    threshold: float

    @property
    def message(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        return (
            f"Baseline Recall@10: {self.baseline_recall10:.4f}\n"
            f"New Recall@10:      {self.new_recall10:.4f}\n"
            f"Drop:               {self.drop:+.4f}\n"
            f"Allowed threshold:  {self.threshold:.4f}\n"
            f"CI RESULT: {verdict}"
        )


def check_regression(baseline_recall10: float, new_recall10: float, threshold: float | None = None) -> GateResult:
    if threshold is None:
        threshold = get_threshold()
    drop = new_recall10 - baseline_recall10  # negative = regression
    passed = drop >= -threshold
    return GateResult(
        passed=passed,
        baseline_recall10=baseline_recall10,
        new_recall10=new_recall10,
        drop=drop,
        threshold=threshold,
    )
