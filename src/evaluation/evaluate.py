"""Runs retrieval evaluation across one or more configurations and produces
a comparison report.

Usage:
    python -m src.evaluation.evaluate                 # evaluate all configs, write reports/
    python -m src.evaluation.evaluate --config hybrid  # evaluate a single config, print only
    python -m src.evaluation.evaluate --approve-baseline
        # re-evaluates the baseline config and OVERWRITES reports/baseline_metrics.json.
        # This is the only command that should ever touch that file, and only
        # after a human has reviewed and accepted the new numbers.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.retrieval.configs import CONFIGS, BASELINE_CONFIG_NAME, TOP_K
from src.retrieval.retriever import Retriever
from src.evaluation.metrics import evaluate_query, aggregate_by_category

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

ALL_CONFIG_NAMES = ["baseline", "chunk_change", "hybrid", "reranker", "broken"]


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def load_corpus() -> list[dict]:
    return load_jsonl(DATA_DIR / "corpus.jsonl")


def load_golden_set() -> list[dict]:
    return load_jsonl(DATA_DIR / "golden_set.jsonl")


def run_config(config_name: str, corpus: list[dict], golden: list[dict]) -> dict:
    retriever = Retriever(corpus, config_name)
    per_query_results = []
    categories = []
    per_query_details = []

    for ex in golden:
        retrieved = retriever.retrieve(ex["query"], top_k=TOP_K)
        result = evaluate_query(retrieved, ex["relevant_passage_ids"])
        per_query_results.append(result)
        categories.append(ex["category"])
        per_query_details.append({
            "query_id": ex["query_id"],
            "category": ex["category"],
            "retrieved": retrieved,
            **result,
        })

    metrics = aggregate_by_category(per_query_results, categories)
    return {
        "config_name": config_name,
        "config": CONFIGS[config_name],
        "metrics": metrics,
        "per_query": per_query_details,
    }


def print_metrics_table(config_name: str, metrics: dict):
    df = pd.DataFrame(metrics).T[["recall@5", "recall@10", "mrr", "ndcg@10"]]
    df = df.rename(index={"overall": "Overall"})
    df.index = [i.replace("_", " ").title() if i != "Overall" else i for i in df.index]
    print(f"\n=== {config_name} ===")
    print(df.round(4).to_string())


def build_comparison(results: dict[str, dict], baseline_name: str = BASELINE_CONFIG_NAME):
    baseline_overall = results[baseline_name]["metrics"]["overall"]
    rows = []
    for name, res in results.items():
        overall = res["metrics"]["overall"]
        cfg = res["config"]
        rows.append({
            "configuration": name,
            "chunk_size": cfg["chunk_size"],
            "retrieval_method": cfg["method"],
            "reranker": cfg["reranker"],
            "candidate_pool": cfg.get("candidate_pool") or "full",
            "recall@5": round(overall["recall@5"], 4),
            "recall@10": round(overall["recall@10"], 4),
            "mrr": round(overall["mrr"], 4),
            "ndcg@10": round(overall["ndcg@10"], 4),
            "delta_recall@10": round(overall["recall@10"] - baseline_overall["recall@10"], 4),
        })
    return pd.DataFrame(rows)


def build_category_breakdown(results: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for name, res in results.items():
        for category, m in res["metrics"].items():
            rows.append({
                "configuration": name,
                "category": category,
                "recall@5": round(m["recall@5"], 4),
                "recall@10": round(m["recall@10"], 4),
                "mrr": round(m["mrr"], 4),
                "ndcg@10": round(m["ndcg@10"], 4),
            })
    return pd.DataFrame(rows)


def write_reports(comparison_df: pd.DataFrame, category_df: pd.DataFrame):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(REPORTS_DIR / "comparison.csv", index=False)

    lines = ["# Retrieval Configuration Comparison\n"]
    lines.append("Overall metrics, deltas relative to the `baseline` configuration:\n")
    lines.append(comparison_df.to_markdown(index=False))
    lines.append("\n\n## Per-category breakdown\n")
    for name in comparison_df["configuration"]:
        sub = category_df[category_df["configuration"] == name].drop(columns=["configuration"])
        lines.append(f"\n### {name}\n")
        lines.append(sub.to_markdown(index=False))
    (REPORTS_DIR / "comparison.md").write_text("\n".join(lines) + "\n")
    print(f"\nWrote {REPORTS_DIR / 'comparison.md'} and {REPORTS_DIR / 'comparison.csv'}")


def approve_baseline(results: dict[str, dict]):
    overall = results[BASELINE_CONFIG_NAME]["metrics"]["overall"]
    payload = {
        "config_name": BASELINE_CONFIG_NAME,
        "recall@5": overall["recall@5"],
        "recall@10": overall["recall@10"],
        "mrr": overall["mrr"],
        "ndcg@10": overall["ndcg@10"],
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_DIR / "baseline_metrics.json", "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Approved new baseline: {payload}")
    print(f"Wrote {REPORTS_DIR / 'baseline_metrics.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", choices=ALL_CONFIG_NAMES, help="Evaluate a single config only (no report written).")
    parser.add_argument("--approve-baseline", action="store_true", help="Overwrite reports/baseline_metrics.json with the current baseline config's metrics.")
    args = parser.parse_args()

    corpus = load_corpus()
    golden = load_golden_set()

    if args.config:
        result = run_config(args.config, corpus, golden)
        print_metrics_table(args.config, result["metrics"])
        return

    config_names = ALL_CONFIG_NAMES
    results = {}
    for name in config_names:
        print(f"Evaluating '{name}'...")
        results[name] = run_config(name, corpus, golden)
        print_metrics_table(name, results[name]["metrics"])

    comparison_df = build_comparison(results)
    category_df = build_category_breakdown(results)
    print("\n=== Comparison (overall, delta vs baseline) ===")
    print(comparison_df.to_string(index=False))
    write_reports(comparison_df, category_df)

    if args.approve_baseline:
        approve_baseline(results)


if __name__ == "__main__":
    main()
