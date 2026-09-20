import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from src.api.app import app  # noqa: E402

client = TestClient(app)
GOLDEN_QUERY = "Does the Fourth Amendment protect places or people?"  # rq003 in the real_world set


def post(path, **body):
    body.setdefault("dataset", "real_world")
    return client.post(path, json=body)


def test_health_lists_datasets_and_configs():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert {"synthetic", "real_world"} <= set(body["datasets"])
    assert "baseline" in body["configs"]


def test_retrieve_returns_ranked_passages_with_scores():
    r = post("/retrieve", query=GOLDEN_QUERY, top_k=3)
    assert r.status_code == 200
    block = r.json()["retrieval"]
    results = block["results"]
    assert [x["rank"] for x in results] == [1, 2, 3]
    scores = [x["score"] for x in results]
    assert scores == sorted(scores, reverse=True)
    assert block["score_type"] == "cosine" and block["dataset_version"]
    assert "generation" not in r.json()


def test_retrieve_finds_the_expected_passage_and_reports_golden_check():
    block = post("/retrieve", query=GOLDEN_QUERY, top_k=5).json()["retrieval"]
    assert "rw003" in [x["passage_id"] for x in block["results"]]
    assert block["golden_check"]["query_id"] == "rq003"
    assert block["golden_check"]["all_relevant_retrieved"] is True


def test_non_golden_query_has_no_golden_check():
    block = post("/retrieve", query="What is the capital of France?").json()["retrieval"]
    assert "golden_check" not in block


def test_ask_keeps_retrieval_and_generation_separate_with_citations():
    r = post("/ask", query=GOLDEN_QUERY, top_k=3)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"retrieval", "generation"}  # no combined score anywhere
    retrieved_ids = [x["passage_id"] for x in body["retrieval"]["results"]]
    gen = body["generation"]
    assert gen["answer"] and gen["method"] == "extractive"
    assert gen["context_passage_ids"] == retrieved_ids
    assert gen["citations"] and all(c["passage_id"] in retrieved_ids for c in gen["citations"])
    assert set(gen["heuristic_metrics"]) == {"faithfulness", "answer_relevance", "context_relevance"}
    assert all("recall" not in k and "mrr" not in k for k in gen["heuristic_metrics"])


def test_config_changes_score_type():
    assert post("/retrieve", query=GOLDEN_QUERY, config="hybrid").json()["retrieval"]["score_type"] == "rrf"


@pytest.mark.parametrize("body", [
    {"query": "x", "config": "nope"},
    {"query": "x", "dataset": "nope"},
    {"query": "   "},
    {"query": ""},
    {"query": "x", "top_k": 0},
    {"query": "x", "top_k": 50},
])
def test_invalid_requests_are_rejected(body):
    body.setdefault("dataset", "real_world")
    assert client.post("/retrieve", json=body).status_code == 422
    assert client.post("/ask", json=body).status_code == 422


def test_static_demo_page_is_served():
    r = client.get("/")
    assert r.status_code == 200 and "Groundtruth RAG demo" in r.text
