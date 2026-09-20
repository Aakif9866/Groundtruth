"""Generation layer built on top of retrieval, with its evaluation kept
strictly separate from retrieval metrics (Recall@K / MRR / nDCG live in
src/evaluation/metrics.py and never mix with the scores computed here).

A retrieval failure and a generation failure are different problems: a
generator can produce a faithful, relevant answer from bad context (masking
a retrieval regression) or an unfaithful answer from perfect context. This
module only ever measures the second kind of failure.

Default mode is a free, deterministic lexical-overlap heuristic (no API key
needed, safe for CI). Setting USE_RAGAS=true (with an API key and `ragas`
installed via `pip install -e ".[ragas]"`) switches to Ragas's
faithfulness / answer_relevancy metrics with an LLM judge instead.
"""
from __future__ import annotations

import os

from src.retrieval.retriever import tokenize


def generate_answer(query: str, retrieved_texts: list[str], max_sentences: int = 3) -> str:
    """Extractive baseline generator: takes the top retrieved chunk(s) and
    trims to the first few sentences. Deliberately simple — the point of
    this project is evaluation, not building a strong generator."""
    if not retrieved_texts:
        return ""
    context = " ".join(retrieved_texts[:2])
    sentences = [s.strip() for s in context.replace("\n", " ").split(". ") if s.strip()]
    return ". ".join(sentences[:max_sentences]).rstrip(".") + "."


def _lexical_overlap(a_tokens: set, b_tokens: set) -> float:
    if not a_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens)


def heuristic_faithfulness(answer: str, retrieved_texts: list[str]) -> float:
    """Proxy for faithfulness: fraction of the answer's vocabulary that is
    grounded in the retrieved context. Not a substitute for an LLM judge,
    but free, deterministic, and always available."""
    answer_tokens = set(tokenize(answer))
    context_tokens = set(tokenize(" ".join(retrieved_texts)))
    return _lexical_overlap(answer_tokens, context_tokens)


def heuristic_answer_relevance(answer: str, query: str) -> float:
    """Proxy for answer relevance: fraction of the query's vocabulary that
    the answer actually addresses."""
    query_tokens = set(tokenize(query))
    answer_tokens = set(tokenize(answer))
    return _lexical_overlap(query_tokens, answer_tokens)


def evaluate_generation_heuristic(query: str, retrieved_texts: list[str]) -> dict:
    answer = generate_answer(query, retrieved_texts)
    return {
        "answer": answer,
        "faithfulness": heuristic_faithfulness(answer, retrieved_texts),
        "answer_relevance": heuristic_answer_relevance(answer, query),
        "method": "heuristic",
    }


def evaluate_generation_ragas(query: str, retrieved_texts: list[str]) -> dict:
    """Requires `pip install -e ".[ragas]"` and ANTHROPIC_API_KEY or
    OPENAI_API_KEY set. Raises if ragas isn't installed or no key is set —
    callers should check USE_RAGAS and fall back to the heuristic path."""
    from ragas import SingleTurnSample
    from ragas.metrics import Faithfulness, AnswerRelevancy

    answer = generate_answer(query, retrieved_texts)
    sample = SingleTurnSample(user_input=query, response=answer, retrieved_contexts=retrieved_texts)

    faithfulness_score = Faithfulness().single_turn_score(sample)
    relevance_score = AnswerRelevancy().single_turn_score(sample)
    return {
        "answer": answer,
        "faithfulness": faithfulness_score,
        "answer_relevance": relevance_score,
        "method": "ragas",
    }


def evaluate_generation(query: str, retrieved_texts: list[str]) -> dict:
    use_ragas = os.environ.get("USE_RAGAS", "false").lower() == "true"
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    if use_ragas and has_key:
        try:
            return evaluate_generation_ragas(query, retrieved_texts)
        except ImportError:
            pass  # ragas extra not installed; fall back below
    return evaluate_generation_heuristic(query, retrieved_texts)
