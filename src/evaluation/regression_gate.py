"""The CI regression gate: fails when Recall@10 drops more than a threshold
relative to the approved baseline.

Rule (unchanged): ``drop = new - baseline``; PASS if ``drop >= -threshold``.

This threshold must never be changed to hide a real regression — if it needs
to change, that is a decision for a human reviewer, documented in a commit
message, not a quiet edit made because a test was failing.

The gate also refuses to compare results produced from different dataset
versions, since such a comparison is meaningless.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_THRESHOLD = 0.01
BASELINE_PATH = Path(__file__).resolve().parent.parent.parent / "reports" / "baseline_metrics.json"


class RegressionGateError(Exception):
    """Base class for conditions under which the gate cannot give a verdict."""


class MissingBaselineError(RegressionGateError, FileNotFoundError):
    """No approved baseline file exists."""


class DatasetVersionMismatch(RegressionGateError):
    """Baseline and new results were produced from different dataset versions."""


def validate_threshold(threshold: float) -> float:
    """Return ``threshold`` if it is a finite number greater than zero, else raise ValueError."""
    try:
        value = float(threshold)
    except (TypeError, ValueError):
        raise ValueError(f"Regression threshold must be a number, got {threshold!r}") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"Regression threshold must be a finite number > 0, got {threshold!r}")
    return value


def get_threshold() -> float:
    """Threshold from REGRESSION_THRESHOLD (default 0.01); raises ValueError if invalid."""
    return validate_threshold(os.environ.get("REGRESSION_THRESHOLD", DEFAULT_THRESHOLD))


def load_baseline(path: str | Path = BASELINE_PATH) -> dict:
    """Load the approved baseline; raises MissingBaselineError with instructions if absent."""
    path = Path(path)
    if not path.exists():
        raise MissingBaselineError(
            f"Approved baseline not found at {path}. Create it deliberately with "
            f"`python -m src.evaluation.evaluate --approve-baseline` after reviewing the numbers."
        )
    return json.loads(path.read_text())


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


def check_regression(
    baseline_recall10: float,
    new_recall10: float,
    threshold: float | None = None,
    baseline_dataset_version: str | None = None,
    new_dataset_version: str | None = None,
) -> GateResult:
    """Compare a new Recall@10 to the approved baseline.

    Raises ``ValueError`` for an invalid threshold and ``DatasetVersionMismatch``
    when both dataset versions are given and differ.
    """
    threshold = get_threshold() if threshold is None else validate_threshold(threshold)
    if baseline_dataset_version and new_dataset_version and baseline_dataset_version != new_dataset_version:
        raise DatasetVersionMismatch(
            f"Baseline was produced on dataset version {baseline_dataset_version} but the new run used "
            f"{new_dataset_version}. Results are not comparable; re-approve the baseline deliberately "
            f"(--approve-baseline) if the dataset change is intended."
        )
    drop = new_recall10 - baseline_recall10  # negative = regression
    return GateResult(
        passed=drop >= -threshold,
        baseline_recall10=baseline_recall10,
        new_recall10=new_recall10,
        drop=drop,
        threshold=threshold,
    )
