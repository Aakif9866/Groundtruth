"""Generation layer built on top of retrieval, with its evaluation kept
strictly separate from retrieval metrics (Recall@K / MRR / nDCG live in
src/evaluation/metrics.py and never mix with the scores computed here).

A retrieval failure and a generation failure are different problems: a
generator can produce a faithful, relevant answer from bad context (masking
a retrieval regression) or an unfaithful answer from perfect context. This
module only ever measures the second kind of failure.

Metrics (all three exist in both modes):
  - faithfulness       heuristic: answer vocabulary grounded in context | llm judge (Groq)
  - answer_relevance   heuristic: query vocabulary covered by the answer | llm judge (Groq)
  - context_relevance  heuristic: query vocabulary covered by the context | llm judge (Groq)

Default mode is a free, deterministic lexical-overlap heuristic (no API key
needed, safe for CI). Setting USE_LLM_JUDGE=true with GROQ_API_KEY switches to a
Groq-hosted LLM judge instead. Groq is the project's only LLM provider.
"""
from __future__ import annotations

import json
import logging
import os

from src.generation.llm import LLMError, groq_available, groq_chat, groq_model
from src.retrieval.retriever import tokenize

logger = logging.getLogger(__name__)


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


def heuristic_context_relevance(query: str, retrieved_texts: list[str]) -> float:
    """Proxy for context relevance: fraction of the query's vocabulary present
    in the retrieved context as a whole. Unlike answer relevance it ignores the
    generated answer, so it isolates how useful the retrieved context was."""
    query_tokens = set(tokenize(query))
    context_tokens = set(tokenize(" ".join(retrieved_texts)))
    return _lexical_overlap(query_tokens, context_tokens)


def evaluate_generation_heuristic(query: str, retrieved_texts: list[str], answer: str | None = None) -> dict:
    """Free, deterministic generation metrics (no LLM, no network).

    Returns faithfulness, answer_relevance and context_relevance, all lexical
    proxies in [0, 1]. Pass ``answer`` to score an externally generated answer.
    """
    if answer is None:
        answer = generate_answer(query, retrieved_texts)
    return {
        "answer": answer,
        "faithfulness": heuristic_faithfulness(answer, retrieved_texts),
        "answer_relevance": heuristic_answer_relevance(answer, query),
        "context_relevance": heuristic_context_relevance(query, retrieved_texts),
        "method": "heuristic",
    }


JUDGE_KEYS = ("faithfulness", "answer_relevance", "context_relevance")


def build_judge_prompt(query: str, context_passages: list[str], answer: str) -> str:
    """Prompt asking an LLM judge for three 0-1 scores as strict JSON."""
    context = "\n\n".join(f"[{i}] {t}" for i, t in enumerate(context_passages, start=1))
    return (
        "You are grading a retrieval-augmented answer. Score each criterion from 0.0 to 1.0.\n"
        "- faithfulness: every claim in the answer is supported by the context (1 = fully supported).\n"
        "- answer_relevance: the answer addresses the question (1 = fully addresses it).\n"
        "- context_relevance: the context contains what is needed to answer the question (1 = fully).\n"
        'Reply with ONLY a JSON object: {"faithfulness": x, "answer_relevance": y, "context_relevance": z}\n\n'
        f"Question: {query}\n\nContext:\n{context}\n\nAnswer: {answer}"
    )


def parse_judge_scores(text: str) -> dict[str, float]:
    """Parse the judge's JSON reply into scores clamped to [0, 1]; raises LLMError if malformed."""
    try:
        raw = json.loads(text)
        return {k: min(1.0, max(0.0, float(raw[k]))) for k in JUDGE_KEYS}
    except (ValueError, KeyError, TypeError):
        raise LLMError(f"Judge reply was not the expected JSON: {text[:200]!r}") from None


def evaluate_generation_llm_judge(query: str, retrieved_texts: list[str], answer: str | None = None) -> dict:
    """LLM-judged faithfulness / answer relevance / context relevance via Groq.

    Requires GROQ_API_KEY. Raises ``LLMError`` if the call or the reply fails.
    """
    if answer is None:
        answer = generate_answer(query, retrieved_texts)
    reply = groq_chat(
        [{"role": "user", "content": build_judge_prompt(query, retrieved_texts, answer)}],
        max_tokens=400, json_mode=True)
    return {"answer": answer, **parse_judge_scores(reply), "method": f"llm_judge:{groq_model()}"}


def evaluate_generation(query: str, retrieved_texts: list[str]) -> dict:
    """Heuristic scores by default; Groq LLM judge when USE_LLM_JUDGE=true and GROQ_API_KEY is set.

    If the judge call fails, falls back to the heuristic and logs a warning.
    """
    if os.environ.get("USE_LLM_JUDGE", "false").lower() == "true" and groq_available():
        try:
            return evaluate_generation_llm_judge(query, retrieved_texts)
        except LLMError as e:
            logger.warning("LLM judge failed (%s); using heuristic metrics instead", e)
    return evaluate_generation_heuristic(query, retrieved_texts)


# --- Cited answers for the RAG demo ------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in text.replace("\n", " ").split(". ") if s.strip()]


def build_llm_prompt(query: str, passages: list[dict]) -> str:
    """Prompt asking an LLM to answer only from numbered sources and cite them as [n]."""
    sources = "\n\n".join(f"[{i}] {p['title']}\n{p['text']}" for i, p in enumerate(passages, start=1))
    return (
        "Answer the question using ONLY the numbered sources below. Cite sources inline as [n]. "
        "If the sources do not contain the answer, say so.\n\n"
        f"Sources:\n{sources}\n\nQuestion: {query}"
    )


def _generate_extractive(query: str, passages: list[dict], max_sources: int = 2) -> dict:
    q_tokens = set(tokenize(query))
    parts, citations = [], []
    for rank, p in enumerate(passages[:max_sources], start=1):
        sentences = _split_sentences(p["text"])
        if not sentences:
            continue
        best = max(sentences, key=lambda s: len(q_tokens & set(tokenize(s))))
        parts.append(f"{best.rstrip('.')}. [{rank}]")
        citations.append({"passage_id": p["passage_id"], "source_number": rank})
    return {"answer": " ".join(parts), "citations": citations, "method": "extractive"}


def _generate_llm(query: str, passages: list[dict]) -> dict:
    answer = groq_chat([{"role": "user", "content": build_llm_prompt(query, passages)}], max_tokens=600)
    cited = [i for i in range(1, len(passages) + 1) if f"[{i}]" in answer]
    citations = [{"passage_id": passages[i - 1]["passage_id"], "source_number": i} for i in cited]
    return {"answer": answer, "citations": citations, "method": f"llm:{groq_model()}"}


def generate_cited_answer(query: str, passages: list[dict]) -> dict:
    """Answer from retrieved passages (rank order) with citations.

    Extractive by default (no key, deterministic). With GENERATION_BACKEND=llm and
    GROQ_API_KEY set, a Groq-hosted model writes the answer from the numbered sources.
    If the LLM call fails the extractive answer is returned and the failure is
    reported in an ``llm_error`` field, so a fallback is never mistaken for an LLM answer.
    """
    if os.environ.get("GENERATION_BACKEND", "extractive") == "llm" and groq_available():
        try:
            return _generate_llm(query, passages)
        except LLMError as e:
            logger.warning("LLM generation failed (%s); using extractive answer", e)
            return {**_generate_extractive(query, passages), "llm_error": str(e)}
    return _generate_extractive(query, passages)
