"""Runs retrieval evaluation across one or more configurations and produces
a comparison report.

Usage:
    python -m src.evaluation.evaluate                 # evaluate all configs, write reports/
    python -m src.evaluation.evaluate --config hybrid  # evaluate a single config, print only
    python -m src.evaluation.evaluate --dataset real_world   # generalization check, reports/real_world/
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
DATASETS = ["synthetic", "real_world"]
DEFAULT_DATASET = "synthetic"


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def dataset_dir(dataset: str = DEFAULT_DATASET) -> Path:
    if dataset not in DATASETS:
        raise ValueError(f"Unknown dataset '{dataset}' (choose from {DATASETS})")
    return DATA_DIR / dataset


def load_corpus(dataset: str = DEFAULT_DATASET) -> list[dict]:
    """Load the corpus for a dataset (``synthetic`` or ``real_world``)."""
    return load_jsonl(dataset_dir(dataset) / "corpus.jsonl")


def load_golden_set(dataset: str = DEFAULT_DATASET) -> list[dict]:
    """Load the golden query set for a dataset."""
    return load_jsonl(dataset_dir(dataset) / "golden_set.jsonl")


def load_dataset_meta(dataset: str = DEFAULT_DATASET) -> dict:
    """Load dataset_meta.json (version, seed, counts) for a dataset."""
    with open(dataset_dir(dataset) / "dataset_meta.json") as f:
        return json.load(f)


def run_config(config_name: str, corpus: list[dict], golden: list[dict], config: dict | None = None) -> dict:
    """Evaluate one retrieval config over a golden set.

    ``config`` may supply an ad-hoc (already translated) config; otherwise
    ``config_name`` is looked up in CONFIGS.
    """
    retriever = Retriever(corpus, config_name, config=config)
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
        "config": retriever.config,
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


def approve_baseline(results: dict[str, dict], dataset_version: str):
    overall = results[BASELINE_CONFIG_NAME]["metrics"]["overall"]
    payload = {
        "config_name": BASELINE_CONFIG_NAME,
        "dataset_version": dataset_version,
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
    parser.add_argument("--config", choices=list(CONFIGS.keys()), help="Evaluate a single config only (no report written).")
    parser.add_argument("--dataset", choices=DATASETS, default=DEFAULT_DATASET, help="Which dataset to evaluate (default: synthetic).")
    parser.add_argument("--approve-baseline", action="store_true", help="Overwrite reports/baseline_metrics.json with the current baseline config's metrics.")
    args = parser.parse_args()

    if args.approve_baseline and args.dataset != "synthetic":
        parser.error("--approve-baseline only applies to the synthetic dataset")

    corpus = load_corpus(args.dataset)
    golden = load_golden_set(args.dataset)
    dataset_version = load_dataset_meta(args.dataset)["dataset_version"]

    if args.config:
        result = run_config(args.config, corpus, golden)
        print_metrics_table(args.config, result["metrics"])
        return

    config_names = [n for n in ALL_CONFIG_NAMES if n in CONFIGS]
    results = {}
    for name in config_names:
        print(f"Evaluating '{name}'...")
        results[name] = run_config(name, corpus, golden)
        print_metrics_table(name, results[name]["metrics"])

    print("\n=== Comparison (overall, delta vs baseline) ===")
    print(build_comparison(results).to_string(index=False))

    from src.evaluation.report import write_comparison_reports  # local import: report imports this module

    out_dir = REPORTS_DIR if args.dataset == DEFAULT_DATASET else REPORTS_DIR / args.dataset
    write_comparison_reports(results, corpus, golden, args.dataset, dataset_version, out_dir)
    print(f"\nWrote comparison.md, comparison.csv and dashboard.html to {out_dir}")

    if args.approve_baseline:
        approve_baseline(results, dataset_version)


if __name__ == "__main__":
    main()
