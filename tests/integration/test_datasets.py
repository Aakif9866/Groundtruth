import json

import pytest

from src.evaluation.compare import compare_results
from src.evaluation.evaluate import DATA_DIR, DATASETS, load_corpus, load_dataset_meta, load_golden_set
from src.evaluation.regression_gate import BASELINE_PATH

REQUIRED_META = {"dataset_version", "generator_version", "seed", "created_at", "review_status",
                 "document_count", "query_count", "categories"}


@pytest.mark.parametrize("dataset", DATASETS)
def test_metadata_is_complete_and_consistent_with_the_data(dataset):
    meta = load_dataset_meta(dataset)
    assert REQUIRED_META <= set(meta)
    assert meta["document_count"] == len(load_corpus(dataset))
    golden = load_golden_set(dataset)
    assert meta["query_count"] == len(golden)
    assert sum(meta["categories"].values()) == len(golden)
    assert meta["review_status"] == "reviewed"


@pytest.mark.parametrize("dataset", DATASETS)
def test_every_relevant_passage_exists_and_every_example_is_reviewed(dataset):
    ids = {d["passage_id"] for d in load_corpus(dataset)}
    for ex in load_golden_set(dataset):
        assert set(ex["relevant_passage_ids"]) <= ids
        assert ex["review_status"] == "reviewed"


def test_synthetic_metadata_values():
    meta = load_dataset_meta("synthetic")
    assert (meta["seed"], meta["document_count"], meta["query_count"]) == (42, 158, 100)


def test_approved_baseline_was_produced_on_the_current_synthetic_dataset():
    approved = json.loads(BASELINE_PATH.read_text())
    assert approved["dataset_version"] == load_dataset_meta("synthetic")["dataset_version"]


def test_real_world_sources_are_documented():
    readme = (DATA_DIR / "real_world" / "README.md").read_text()
    for doc in load_corpus("real_world"):
        assert doc["passage_id"] in readme


def test_comparing_runs_over_different_query_sets_is_refused():
    def result(ids):
        return {"per_query": [{"query_id": i, "recall@10": 1.0, "mrr": 1.0, "ndcg@10": 1.0} for i in ids]}
    with pytest.raises(ValueError, match="same queries"):
        compare_results(result(["a", "b"]), result(["a", "c"]))
    assert compare_results(result(["a", "b"]), result(["a", "b"]), n_resamples=50)["mrr"].delta == 0
