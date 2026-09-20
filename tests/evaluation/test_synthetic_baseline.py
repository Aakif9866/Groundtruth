"""Full retrieval over the synthetic golden set (the deterministic regression benchmark)."""
import json

import pytest

from src.evaluation.evaluate import load_corpus, load_golden_set, run_config
from src.evaluation.regression_gate import BASELINE_PATH, check_regression


@pytest.fixture(scope="module")
def corpus_and_golden():
    return load_corpus("synthetic"), load_golden_set("synthetic")


def test_baseline_reproduces_the_approved_numbers(corpus_and_golden):
    # Tolerance allows for tiny floating-point differences between machines/accelerators
    # (the approved numbers were produced on a Mac; CI runs on Linux CPU). It is far tighter
    # than the 0.01 regression threshold, so a real behaviour change is still caught here.
    approved = json.loads(BASELINE_PATH.read_text())
    overall = run_config("baseline", *corpus_and_golden)["metrics"]["overall"]
    for key in ("recall@5", "recall@10", "mrr", "ndcg@10"):
        assert overall[key] == pytest.approx(approved[key], abs=0.005), key


def test_baseline_is_deterministic_within_a_machine(corpus_and_golden):
    first = run_config("baseline", *corpus_and_golden)["metrics"]["overall"]
    second = run_config("baseline", *corpus_and_golden)["metrics"]["overall"]
    assert first == second


def test_deliberately_broken_config_is_caught_by_the_gate(corpus_and_golden):
    approved = json.loads(BASELINE_PATH.read_text())
    broken = run_config("broken", *corpus_and_golden)["metrics"]["overall"]["recall@10"]
    gate = check_regression(approved["recall@10"], broken, threshold=0.01)
    assert not gate.passed
    assert gate.drop < -0.5


def test_every_category_has_enough_queries_for_per_category_metrics(corpus_and_golden):
    metrics = run_config("baseline", *corpus_and_golden)["metrics"]
    assert {"precedent", "statute", "procedural", "factual", "multi_hop"} <= set(metrics)
