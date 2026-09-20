from src.generation.generate import (
    build_llm_prompt, evaluate_generation_heuristic, generate_cited_answer, heuristic_context_relevance,
)

PASSAGES = [
    {"passage_id": "a", "title": "Katz", "text": "For the Fourth Amendment protects people, not places. Other sentence here."},
    {"passage_id": "b", "title": "Other", "text": "Unrelated text about arbitration agreements. More text."},
]


def test_context_relevance_is_independent_of_the_answer():
    q = "fourth amendment people places"
    good = heuristic_context_relevance(q, [PASSAGES[0]["text"]])
    bad = heuristic_context_relevance(q, [PASSAGES[1]["text"]])
    assert good > bad
    assert evaluate_generation_heuristic(q, [PASSAGES[1]["text"]], answer="fourth amendment people places")["context_relevance"] == bad


def test_heuristic_evaluation_returns_all_three_metrics_in_unit_range():
    r = evaluate_generation_heuristic("fourth amendment", [PASSAGES[0]["text"]])
    assert {"faithfulness", "answer_relevance", "context_relevance", "answer", "method"} <= set(r)
    assert r["method"] == "heuristic"
    assert all(0 <= r[k] <= 1 for k in ("faithfulness", "answer_relevance", "context_relevance"))


def test_extractive_answer_cites_the_sources_it_used(monkeypatch):
    monkeypatch.delenv("GENERATION_BACKEND", raising=False)
    out = generate_cited_answer("Does the Fourth Amendment protect people?", PASSAGES)
    assert out["method"] == "extractive"
    assert "protects people, not places" in out["answer"] and "[1]" in out["answer"]
    assert [c["passage_id"] for c in out["citations"]] == ["a", "b"]


def test_llm_backend_without_api_key_falls_back_to_extractive(monkeypatch):
    monkeypatch.setenv("GENERATION_BACKEND", "llm")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert generate_cited_answer("q", PASSAGES)["method"] == "extractive"


def test_llm_prompt_numbers_sources_and_restricts_to_them():
    prompt = build_llm_prompt("What?", PASSAGES)
    assert "[1] Katz" in prompt and "[2] Other" in prompt and "ONLY" in prompt and "Question: What?" in prompt
