import copy

import pytest

from src.retrieval.configs import CONFIGS, EXPERIMENTS_DIR, load_experiment_config, translate_experiment

VALID = {
    "name": "t",
    "retrieval": {"dense": True, "bm25": False, "fusion": None},
    "chunking": {"size": 300, "overlap": 50},
    "reranker": {"enabled": False, "model": None, "top_n": 20},
    "candidate_pool": None,
}


def test_all_expected_experiments_are_loaded():
    assert {"baseline", "chunk_change", "hybrid", "reranker", "broken"} <= set(CONFIGS)


def test_baseline_values_match_documented_settings():
    c = CONFIGS["baseline"]
    assert (c["chunk_size"], c["chunk_overlap"], c["method"], c["reranker"], c["candidate_pool"]) == (300, 50, "dense", False, None)


def test_hybrid_yaml_translates_to_hybrid_method():
    assert load_experiment_config(EXPERIMENTS_DIR / "hybrid.yaml")["method"] == "hybrid"


def test_reranker_yaml_records_models_and_pool_size():
    c = CONFIGS["reranker"]
    assert c["reranker"] and c["reranker_model"] and c["rerank_pool_size"] == 20


def test_disabled_reranker_has_no_reranker_model():
    assert CONFIGS["baseline"]["reranker_model"] is None


def test_broken_config_is_deliberately_restricted():
    assert CONFIGS["broken"]["candidate_pool"] == 3


def test_translate_is_pure():
    raw = copy.deepcopy(VALID)
    translate_experiment(raw)
    assert raw == VALID


@pytest.mark.parametrize("mutate", [
    lambda r: r.pop("name"),
    lambda r: r.pop("chunking"),
    lambda r: r["retrieval"].update(dense=False),                       # bm25-only unsupported
    lambda r: r["retrieval"].update(bm25=True, fusion="weighted"),      # hybrid needs rrf
    lambda r: r["chunking"].update(size=0),
    lambda r: r["chunking"].update(overlap=300),                        # overlap must be < size
    lambda r: r.update(candidate_pool=0),
])
def test_invalid_configs_are_rejected(mutate):
    raw = copy.deepcopy(VALID)
    mutate(raw)
    with pytest.raises(ValueError):
        translate_experiment(raw)
