"""Retrieval metrics: Recall@K, MRR, nDCG, and category aggregation.

All functions take retrieved_ids (ranked, best-first, deduplicated passage
ids) and relevant_ids (the golden set's relevant_passage_ids) and are pure /
side-effect free so they are easy to unit test with hand-built examples.
"""
from __future__ import annotations

import math
from collections import defaultdict


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for r in relevant_ids if r in top_k)
    return hits / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    relevant_set = set(relevant_ids)
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Binary graded relevance nDCG@k: gain is 1 for a relevant passage, 0 otherwise."""
    relevant_set = set(relevant_ids)
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k]):
        if doc_id in relevant_set:
            dcg += 1.0 / math.log2(i + 2)  # i is 0-indexed, rank = i+1, log2(rank+1)

    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def evaluate_query(retrieved_ids: list[str], relevant_ids: list[str]) -> dict:
    return {
        "recall@5": recall_at_k(retrieved_ids, relevant_ids, 5),
        "recall@10": recall_at_k(retrieved_ids, relevant_ids, 10),
        "mrr": reciprocal_rank(retrieved_ids, relevant_ids),
        "ndcg@10": ndcg_at_k(retrieved_ids, relevant_ids, 10),
    }


def aggregate(per_query_results: list[dict]) -> dict:
    """Averages metric dicts (as produced by evaluate_query) across queries."""
    if not per_query_results:
        return {"recall@5": 0.0, "recall@10": 0.0, "mrr": 0.0, "ndcg@10": 0.0}
    keys = per_query_results[0].keys()
    return {k: sum(r[k] for r in per_query_results) / len(per_query_results) for k in keys}


def aggregate_by_category(per_query_results: list[dict], categories: list[str]) -> dict[str, dict]:
    """per_query_results and categories must be the same length and order.
    Returns {"overall": {...}, "<category>": {...}, ...}."""
    by_category = defaultdict(list)
    for result, category in zip(per_query_results, categories):
        by_category[category].append(result)

    out = {"overall": aggregate(per_query_results)}
    for category, results in by_category.items():
        out[category] = aggregate(results)
    return out
