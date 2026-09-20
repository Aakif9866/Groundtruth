"""Compare two retrieval configurations with paired bootstrap confidence intervals.

Usage:
    python -m src.evaluation.compare --baseline baseline --candidate hybrid
    python -m src.evaluation.compare --baseline baseline --candidate hybrid --dataset real_world
"""
from __future__ import annotations

import argparse
import logging

from src.evaluation.evaluate import (
    ALL_CONFIG_NAMES, DATASETS, DEFAULT_DATASET, load_corpus, load_dataset_meta, load_golden_set, run_config,
)
from src.evaluation.statistics import DEFAULT_RESAMPLES, DEFAULT_SEED, BootstrapResult, paired_bootstrap_delta

logger = logging.getLogger(__name__)

COMPARED_METRICS = ["recall@10", "mrr", "ndcg@10"]


def compare_results(baseline: dict, candidate: dict, n_resamples: int = DEFAULT_RESAMPLES,
                    seed: int = DEFAULT_SEED) -> dict[str, BootstrapResult]:
    """Bootstrap each compared metric between two ``run_config`` results (same golden set)."""
    base_q, cand_q = baseline["per_query"], candidate["per_query"]
    if [q["query_id"] for q in base_q] != [q["query_id"] for q in cand_q]:
        raise ValueError("baseline and candidate were not evaluated on the same queries in the same order")
    return {
        m: paired_bootstrap_delta([q[m] for q in base_q], [q[m] for q in cand_q], n_resamples=n_resamples, seed=seed)
        for m in COMPARED_METRICS
    }


def format_comparison(baseline_name: str, candidate_name: str, results: dict[str, BootstrapResult],
                      dataset: str, dataset_version: str) -> str:
    """Render a comparison as plain text."""
    any_result = next(iter(results.values()))
    level = int(any_result.ci_level * 100)
    lines = [
        f"Dataset: {dataset} (version {dataset_version}), {any_result.n_queries} queries, "
        f"{any_result.n_resamples} paired bootstrap resamples",
        "",
    ]
    for metric, r in results.items():
        lines += [
            f"{metric}",
            f"  {baseline_name:<14}{r.baseline_mean:.3f}",
            f"  {candidate_name:<14}{r.candidate_mean:.3f}",
            f"  Delta: {r.delta:+.3f}   {level}% CI: [{r.ci_low:+.3f}, {r.ci_high:+.3f}]   -> {r.verdict}",
            "",
        ]
    lines.append(
        "Note: with a small golden set, wide intervals are expected. "
        "'Inconclusive' means the data cannot distinguish the two configs, not that they are equal."
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, choices=ALL_CONFIG_NAMES)
    parser.add_argument("--candidate", required=True, choices=ALL_CONFIG_NAMES)
    parser.add_argument("--dataset", choices=DATASETS, default=DEFAULT_DATASET)
    parser.add_argument("--resamples", type=int, default=DEFAULT_RESAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    corpus, golden = load_corpus(args.dataset), load_golden_set(args.dataset)
    version = load_dataset_meta(args.dataset)["dataset_version"]
    base = run_config(args.baseline, corpus, golden)
    cand = run_config(args.candidate, corpus, golden)
    results = compare_results(base, cand, n_resamples=args.resamples, seed=args.seed)
    print(format_comparison(args.baseline, args.candidate, results, args.dataset, version))


if __name__ == "__main__":
    main()
