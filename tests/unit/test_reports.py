import pandas as pd

from src.evaluation.report import render_comparison_markdown, render_dashboard_html, render_run_report
from src.evaluation.statistics import paired_bootstrap_delta


def fake_result(name, recall, mrr, method="dense", reranker=False, pool=None):
    per_query = [{"query_id": f"q{i}", "recall@10": recall, "mrr": mrr, "ndcg@10": mrr, "recall@5": recall} for i in range(10)]
    overall = {"recall@5": recall, "recall@10": recall, "mrr": mrr, "ndcg@10": mrr}
    return {
        "config_name": name, "per_query": per_query,
        "metrics": {"overall": overall, "precedent": overall, "statute": overall},
        "config": {"chunk_size": 300, "chunk_overlap": 50, "method": method, "reranker": reranker,
                   "candidate_pool": pool, "embedding_model": "emb-model", "reranker_model": "rr-model" if reranker else None},
    }


def build():
    results = {"baseline": fake_result("baseline", 0.9, 0.7), "hybrid": fake_result("hybrid", 1.0, 0.8, "hybrid")}
    stats = {"hybrid": {"recall@10": paired_bootstrap_delta([0.9] * 10, [1.0] * 10, n_resamples=200)}}
    failures = {"baseline": [("ranking_failure", 3, 60.0), ("chunk_boundary", 2, 40.0)], "hybrid": []}
    return results, failures, stats


def test_markdown_contains_every_required_section():
    results, failures, stats = build()
    md = render_comparison_markdown(results, "synthetic", "1.1.0", 10, failures, stats)
    for section in ("## Overall metrics", "## Configuration details", "## Statistical analysis",
                    "## Failure types", "## Per-category breakdown", "delta_recall@10", "emb-model", "ranking_failure",
                    "improvement: CI excludes 0", "synthetic", "1.1.0"):
        assert section in md, section


def test_dashboard_is_self_contained_html_with_charts():
    results, failures, stats = build()
    html = render_dashboard_html(results, "synthetic", "1.1.0", 10, failures, stats)
    assert html.startswith("<!doctype html>") and "<svg" in html and "ranking_failure" in html
    assert "<script" not in html and "http://" not in html and "https://" not in html


def test_dashboard_escapes_html_in_names():
    results, failures, stats = build()
    results["<b>x</b>"] = fake_result("<b>x</b>", 0.5, 0.5)
    html = render_dashboard_html(results, "synthetic", "1.1.0", 10, failures, stats)
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html


def test_run_report_includes_config_and_metrics():
    meta = {"experiment_name": "e", "run_id": "r", "timestamp": "t", "dataset": "real_world", "dataset_version": "1.0.0",
            "query_count": 19, "config": build()[0]["hybrid"]["config"], "metrics": build()[0]["hybrid"]["metrics"]}
    md = render_run_report(meta, [("ranking_failure", 1, 100.0)])
    assert "real_world" in md and "1.000" in md and "emb-model" in md and "ranking_failure" in md
