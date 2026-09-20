"""Run one experiment from a YAML file and persist everything to a new run directory.

Usage:
    python -m src.evaluation.run --config experiments/hybrid.yaml
    python -m src.evaluation.run --config experiments/hybrid.yaml --dataset real_world

Each invocation creates ``runs/<timestamp>_<experiment>[_<dataset>]/`` containing
config.yaml, metrics.json, query_results.json, error_analysis.md and report.md.
Existing run directories are never overwritten or modified.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.evaluation.error_analysis import aggregate_failure_types, analyze_queries, build_report
from src.evaluation.evaluate import (
    DATASETS, DEFAULT_DATASET, ROOT, load_corpus, load_dataset_meta, load_golden_set, run_config,
)
from src.evaluation.report import render_run_report
from src.retrieval.configs import load_experiment_config
from src.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

RUNS_DIR = ROOT / "runs"


def new_run_dir(runs_dir: Path, experiment: str, dataset: str, now: datetime | None = None) -> Path:
    """Create a fresh, uniquely named run directory (never reuses an existing one)."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S")
    suffix = "" if dataset == DEFAULT_DATASET else f"_{dataset}"
    base = f"{stamp}_{experiment}{suffix}"
    runs_dir.mkdir(parents=True, exist_ok=True)
    candidate, n = runs_dir / base, 1
    while True:
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            candidate = runs_dir / f"{base}-{n}"
            n += 1


def execute_run(config_path: str | Path, dataset: str = DEFAULT_DATASET, runs_dir: Path = RUNS_DIR,
                error_top_n: int = 5) -> Path:
    """Evaluate one experiment YAML on a dataset and write a run directory. Returns its path."""
    config_path = Path(config_path)
    cfg = load_experiment_config(config_path)
    name = cfg["name"]
    corpus, golden = load_corpus(dataset), load_golden_set(dataset)
    meta = load_dataset_meta(dataset)
    logger.info("Running experiment '%s' on %s v%s (%d queries)", name, dataset, meta["dataset_version"], len(golden))

    result = run_config(name, corpus, golden, config=cfg)
    retriever = Retriever(corpus, name, config=cfg)
    retrieved = {q["query_id"]: q["retrieved"] for q in result["per_query"]}
    records, total = analyze_queries(retriever, corpus, golden, retrieved=retrieved)

    run_dir = new_run_dir(runs_dir, name, dataset)
    now = datetime.now(timezone.utc)
    metrics_doc = {
        "run_id": run_dir.name,
        "timestamp": now.isoformat(),
        "experiment_name": name,
        "dataset": dataset,
        "dataset_version": meta["dataset_version"],
        "query_count": total,
        "config": {k: cfg.get(k) for k in (
            "method", "chunk_size", "chunk_overlap", "candidate_pool", "embedding_model", "reranker_model", "reranker")},
        "metrics": result["metrics"],
    }
    golden_by_id = {g["query_id"]: g for g in golden}
    query_results = [
        {**q, "query": golden_by_id[q["query_id"]]["query"],
         "relevant_passage_ids": golden_by_id[q["query_id"]]["relevant_passage_ids"]}
        for q in result["per_query"]
    ]

    shutil.copyfile(config_path, run_dir / "config.yaml")
    (run_dir / "metrics.json").write_text(json.dumps(metrics_doc, indent=2))
    (run_dir / "query_results.json").write_text(json.dumps(query_results, indent=2))
    corpus_by_id = {d["passage_id"]: d for d in corpus}
    (run_dir / "error_analysis.md").write_text(
        build_report(name, dataset, records, total, corpus_by_id, error_top_n))
    (run_dir / "report.md").write_text(render_run_report(metrics_doc, aggregate_failure_types(records)))
    logger.info("Wrote run to %s", run_dir)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to an experiment YAML, e.g. experiments/hybrid.yaml")
    parser.add_argument("--dataset", choices=DATASETS, default=DEFAULT_DATASET)
    parser.add_argument("--runs-dir", default=str(RUNS_DIR))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for noisy in ("httpx", "httpcore", "huggingface_hub", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    run_dir = execute_run(args.config, args.dataset, Path(args.runs_dir))
    overall = json.loads((run_dir / "metrics.json").read_text())["metrics"]["overall"]
    print(f"Run written to {run_dir}")
    print("  " + "  ".join(f"{k}={v:.4f}" for k, v in overall.items()))


if __name__ == "__main__":
    main()
