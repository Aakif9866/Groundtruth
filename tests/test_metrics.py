from src.evaluation.metrics import (
    recall_at_k,
    reciprocal_rank,
    ndcg_at_k,
    evaluate_query,
    aggregate,
    aggregate_by_category,
)


def test_recall_at_k_all_found():
    retrieved = ["a", "b", "c"]
    relevant = ["a", "c"]
    assert recall_at_k(retrieved, relevant, 5) == 1.0


def test_recall_at_k_partial():
    retrieved = ["a", "x", "y"]
    relevant = ["a", "c"]
    assert recall_at_k(retrieved, relevant, 5) == 0.5


def test_recall_at_k_respects_k():
    retrieved = ["x", "y", "a"]
    relevant = ["a"]
    assert recall_at_k(retrieved, relevant, 2) == 0.0
    assert recall_at_k(retrieved, relevant, 3) == 1.0


def test_recall_at_k_no_relevant_docs():
    assert recall_at_k(["a", "b"], [], 5) == 0.0


def test_reciprocal_rank_first_position():
    assert reciprocal_rank(["a", "b"], ["a"]) == 1.0


def test_reciprocal_rank_third_position():
    assert reciprocal_rank(["x", "y", "a"], ["a"]) == 1 / 3


def test_reciprocal_rank_not_found():
    assert reciprocal_rank(["x", "y"], ["a"]) == 0.0


def test_ndcg_perfect_ranking():
    retrieved = ["a", "b", "x"]
    relevant = ["a", "b"]
    assert ndcg_at_k(retrieved, relevant, 5) == 1.0


def test_ndcg_worse_ranking_scores_lower():
    perfect = ndcg_at_k(["a", "b", "x"], ["a", "b"], 5)
    worse = ndcg_at_k(["x", "a", "b"], ["a", "b"], 5)
    assert worse < perfect


def test_ndcg_no_hits_is_zero():
    assert ndcg_at_k(["x", "y"], ["a"], 5) == 0.0


def test_ndcg_no_relevant_docs_is_zero():
    assert ndcg_at_k(["x", "y"], [], 5) == 0.0


def test_evaluate_query_bundles_all_metrics():
    result = evaluate_query(["a", "b"], ["a"])
    assert set(result.keys()) == {"recall@5", "recall@10", "mrr", "ndcg@10"}
    assert result["recall@5"] == 1.0
    assert result["mrr"] == 1.0


def test_aggregate_averages_across_queries():
    results = [
        {"recall@10": 1.0, "mrr": 1.0},
        {"recall@10": 0.0, "mrr": 0.0},
    ]
    agg = aggregate(results)
    assert agg["recall@10"] == 0.5
    assert agg["mrr"] == 0.5


def test_aggregate_empty_list():
    agg = aggregate([])
    assert agg["recall@10"] == 0.0


def test_aggregate_by_category_splits_correctly():
    results = [
        {"recall@10": 1.0, "mrr": 1.0},
        {"recall@10": 0.0, "mrr": 0.0},
        {"recall@10": 1.0, "mrr": 1.0},
    ]
    categories = ["precedent", "precedent", "statute"]
    agg = aggregate_by_category(results, categories)
    assert agg["overall"]["recall@10"] == (1.0 + 0.0 + 1.0) / 3
    assert agg["precedent"]["recall@10"] == 0.5
    assert agg["statute"]["recall@10"] == 1.0
