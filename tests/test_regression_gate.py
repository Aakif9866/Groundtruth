"""CI regression gate tests (the gate's entry point).

Unit-level cases exercise ``check_regression`` and friends with synthetic
numbers. The final test evaluates a real retrieval configuration against the
committed, approved baseline and passes by default. Running

    EVAL_CONFIG=broken pytest tests/test_regression_gate.py

points that same test at the deliberately-bad ``broken`` configuration and
makes it fail, with the real Recall@10 numbers in the assertion message.
"""
import os

import pytest

from src.evaluation.evaluate import load_corpus, load_dataset_meta, load_golden_set, run_config
from src.evaluation.regression_gate import (
    BASELINE_PATH, DatasetVersionMismatch, MissingBaselineError, check_regression, get_threshold, load_baseline,
)


@pytest.mark.unit
def test_no_regression_passes():
    assert check_regression(baseline_recall10=0.82, new_recall10=0.82, threshold=0.01).passed


@pytest.mark.unit
def test_improvement_passes():
    assert check_regression(baseline_recall10=0.82, new_recall10=0.90, threshold=0.01).passed


@pytest.mark.unit
def test_small_regression_under_threshold_passes():
    result = check_regression(baseline_recall10=0.88, new_recall10=0.875, threshold=0.01)
    assert result.passed
    assert result.drop == pytest.approx(-0.005)


@pytest.mark.unit
def test_regression_over_threshold_fails():
    result = check_regression(baseline_recall10=0.88, new_recall10=0.86, threshold=0.01)
    assert not result.passed
    assert "CI RESULT: FAIL" in result.message
    assert "0.8800" in result.message and "0.8600" in result.message


@pytest.mark.unit
def test_threshold_is_configurable():
    assert not check_regression(0.90, 0.88, threshold=0.01).passed
    assert check_regression(0.90, 0.88, threshold=0.03).passed


@pytest.mark.unit
def test_threshold_read_from_environment(monkeypatch):
    monkeypatch.setenv("REGRESSION_THRESHOLD", "0.05")
    assert get_threshold() == 0.05
    assert check_regression(0.90, 0.86).passed


@pytest.mark.unit
@pytest.mark.parametrize("bad", [0, -0.01, float("nan"), float("inf"), "abc"])
def test_invalid_threshold_is_rejected(bad):
    with pytest.raises(ValueError):
        check_regression(0.9, 0.9, threshold=bad)


@pytest.mark.unit
def test_invalid_threshold_from_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("REGRESSION_THRESHOLD", "not-a-number")
    with pytest.raises(ValueError):
        check_regression(0.9, 0.9)


@pytest.mark.unit
def test_missing_baseline_raises_clear_error(tmp_path):
    with pytest.raises(MissingBaselineError, match="--approve-baseline"):
        load_baseline(tmp_path / "does_not_exist.json")


@pytest.mark.unit
def test_dataset_version_mismatch_refuses_to_compare():
    with pytest.raises(DatasetVersionMismatch, match="not comparable"):
        check_regression(0.9, 0.9, threshold=0.01, baseline_dataset_version="1.0.0", new_dataset_version="1.1.0")


@pytest.mark.unit
def test_matching_dataset_versions_are_compared_normally():
    result = check_regression(0.9, 0.9, threshold=0.01, baseline_dataset_version="1.1.0", new_dataset_version="1.1.0")
    assert result.passed


@pytest.mark.evaluation
@pytest.mark.slow
def test_ci_gate_against_approved_baseline():
    approved = load_baseline(BASELINE_PATH)
    config_under_test = os.environ.get("EVAL_CONFIG", "baseline")

    corpus, golden = load_corpus("synthetic"), load_golden_set("synthetic")
    result = run_config(config_under_test, corpus, golden)
    gate = check_regression(
        baseline_recall10=approved["recall@10"],
        new_recall10=result["metrics"]["overall"]["recall@10"],
        baseline_dataset_version=approved.get("dataset_version"),
        new_dataset_version=load_dataset_meta("synthetic")["dataset_version"],
    )
    assert gate.passed, f"\nRegression gate FAILED for config '{config_under_test}':\n{gate.message}"
