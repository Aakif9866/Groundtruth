import pytest

from src.generation import generate, llm
from src.generation.generate import (
    build_judge_prompt, build_llm_prompt, evaluate_generation, evaluate_generation_heuristic,
    generate_cited_answer, heuristic_context_relevance, parse_judge_scores,
)
from src.generation.llm import LLMError

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
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    out = generate_cited_answer("q", PASSAGES)
    assert out["method"] == "extractive" and "llm_error" not in out


def test_llm_backend_uses_groq_and_extracts_citations(monkeypatch):
    monkeypatch.setenv("GENERATION_BACKEND", "llm")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(generate, "groq_chat", lambda messages, **kw: "Answer from source [2] only.")
    out = generate_cited_answer("q", PASSAGES)
    assert out["method"].startswith("llm:") and out["answer"] == "Answer from source [2] only."
    assert out["citations"] == [{"passage_id": "b", "source_number": 2}]


def test_llm_failure_falls_back_visibly(monkeypatch):
    monkeypatch.setenv("GENERATION_BACKEND", "llm")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    def boom(*a, **k):
        raise LLMError("Groq HTTP 429")
    monkeypatch.setattr(generate, "groq_chat", boom)
    out = generate_cited_answer("q", PASSAGES)
    assert out["method"] == "extractive" and "429" in out["llm_error"]


def test_judge_prompt_and_score_parsing():
    prompt = build_judge_prompt("What?", ["ctx one"], "ans")
    assert "[1] ctx one" in prompt and "JSON" in prompt and "Question: What?" in prompt
    scores = parse_judge_scores('{"faithfulness": 1.4, "answer_relevance": 0.5, "context_relevance": -1}')
    assert scores == {"faithfulness": 1.0, "answer_relevance": 0.5, "context_relevance": 0.0}


@pytest.mark.parametrize("bad", ["not json", '{"faithfulness": 1}', '{"faithfulness": "x", "answer_relevance": 1, "context_relevance": 1}'])
def test_malformed_judge_reply_is_rejected(bad):
    with pytest.raises(LLMError):
        parse_judge_scores(bad)


def test_llm_judge_is_used_only_when_enabled_and_falls_back_on_error(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(generate, "groq_chat", lambda *a, **k: '{"faithfulness": 0.9, "answer_relevance": 0.8, "context_relevance": 0.7}')
    monkeypatch.setenv("USE_LLM_JUDGE", "false")
    assert evaluate_generation("q", ["ctx"])["method"] == "heuristic"
    monkeypatch.setenv("USE_LLM_JUDGE", "true")
    r = evaluate_generation("q", ["ctx"])
    assert r["method"].startswith("llm_judge:") and r["faithfulness"] == 0.9

    def boom(*a, **k):
        raise LLMError("down")
    monkeypatch.setattr(generate, "groq_chat", boom)
    assert evaluate_generation("q", ["ctx"])["method"] == "heuristic"


def test_groq_client_requires_a_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert not llm.groq_available()
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        llm.groq_chat([{"role": "user", "content": "hi"}])


def test_llm_prompt_numbers_sources_and_restricts_to_them():
    prompt = build_llm_prompt("What?", PASSAGES)
    assert "[1] Katz" in prompt and "[2] Other" in prompt and "ONLY" in prompt and "Question: What?" in prompt
