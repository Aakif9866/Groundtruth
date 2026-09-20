"""Regression gate tests.

Unit tests below exercise check_regression() directly with synthetic
numbers. The integration test at the bottom is the literal reproduction
path documented in the README/CLAUDE.md: by default it evaluates the
'baseline' config against the committed, approved reports/baseline_metrics.json
and passes. Running

    EVAL_CONFIG=broken pytest tests/test_regression_gate.py

points that same test at the deliberately-bad 'broken' configuration and
makes it fail, with the real (non-fabricated) Recall@10 numbers printed in
the assertion message.
"""
import json
import os
from pathlib import Path

import pytest

from src.evaluation.regression_gate import check_regression
from src.evaluation.evaluate import load_corpus, load_golden_set, run_config, REPORTS_DIR


def test_no_regression_passes():
    result = check_regression(baseline_recall10=0.82, new_recall10=0.82, threshold=0.01)
    assert result.passed


def test_small_regression_under_threshold_passes():
    result = check_regression(baseline_recall10=0.88, new_recall10=0.875, threshold=0.01)
    assert result.passed


def test_regression_over_threshold_fails():
    result = check_regression(baseline_recall10=0.88, new_recall10=0.86, threshold=0.01)
    assert not result.passed


def test_threshold_is_configurable():
    # A 0.02 drop fails the default (0.01) threshold but passes a looser one.
    strict = check_regression(baseline_recall10=0.90, new_recall10=0.88, threshold=0.01)
    loose = check_regression(baseline_recall10=0.90, new_recall10=0.88, threshold=0.03)
    assert not strict.passed
    assert loose.passed


@pytest.mark.slow
def test_ci_gate_against_approved_baseline():
    baseline_path = REPORTS_DIR / "baseline_metrics.json"
    if not baseline_path.exists():
        pytest.skip("reports/baseline_metrics.json not found; run `python -m src.evaluation.evaluate --approve-baseline` first")

    approved = json.loads(baseline_path.read_text())
    config_under_test = os.environ.get("EVAL_CONFIG", "baseline")

    corpus = load_corpus()
    golden = load_golden_set()
    result = run_config(config_under_test, corpus, golden)
    new_recall10 = result["metrics"]["overall"]["recall@10"]

    gate = check_regression(baseline_recall10=approved["recall@10"], new_recall10=new_recall10)
    assert gate.passed, (
        f"\nRegression gate FAILED for config '{config_under_test}':\n{gate.message}"
    )
