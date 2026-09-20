import json

from src.evaluation.evaluate import ROOT
from src.evaluation.run import execute_run, new_run_dir

BASELINE_YAML = ROOT / "experiments" / "baseline.yaml"
REQUIRED_FILES = {"config.yaml", "metrics.json", "query_results.json", "error_analysis.md", "report.md"}


def strip_volatile(metrics: dict) -> dict:
    return {k: v for k, v in metrics.items() if k not in {"run_id", "timestamp"}}


def test_run_writes_all_artifacts_and_records_provenance(tmp_path):
    run_dir = execute_run(BASELINE_YAML, "real_world", runs_dir=tmp_path)
    assert {p.name for p in run_dir.iterdir()} == REQUIRED_FILES
    m = json.loads((run_dir / "metrics.json").read_text())
    assert m["dataset"] == "real_world" and m["dataset_version"] == "1.0.0" and m["query_count"] == 19
    assert m["config"]["chunk_size"] == 300 and m["config"]["chunk_overlap"] == 50
    assert m["config"]["method"] == "dense" and m["config"]["candidate_pool"] is None
    assert m["config"]["embedding_model"] and m["config"]["reranker_model"] is None
    assert m["timestamp"] and set(m["metrics"]["overall"]) == {"recall@5", "recall@10", "mrr", "ndcg@10"}
    assert (run_dir / "config.yaml").read_text() == BASELINE_YAML.read_text()
    results = json.loads((run_dir / "query_results.json").read_text())
    assert len(results) == 19 and {"query", "retrieved", "relevant_passage_ids"} <= set(results[0])


def test_same_experiment_same_dataset_is_reproducible_and_never_overwrites(tmp_path):
    first = execute_run(BASELINE_YAML, "real_world", runs_dir=tmp_path)
    before = (first / "metrics.json").read_text()
    second = execute_run(BASELINE_YAML, "real_world", runs_dir=tmp_path)
    assert first != second and first.exists() and second.exists()
    assert (first / "metrics.json").read_text() == before  # earlier run untouched
    a = json.loads((first / "metrics.json").read_text())
    b = json.loads((second / "metrics.json").read_text())
    assert strip_volatile(a) == strip_volatile(b)
    assert (first / "query_results.json").read_text() == (second / "query_results.json").read_text()


def test_run_directory_names_never_collide(tmp_path):
    from datetime import datetime, timezone
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dirs = {new_run_dir(tmp_path, "x", "synthetic", now) for _ in range(3)}
    assert len(dirs) == 3
