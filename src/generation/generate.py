"""Generation layer built on top of retrieval, with its evaluation kept
strictly separate from retrieval metrics (Recall@K / MRR / nDCG live in
src/evaluation/metrics.py and never mix with the scores computed here).

A retrieval failure and a generation failure are different problems: a
generator can produce a faithful, relevant answer from bad context (masking
a retrieval regression) or an unfaithful answer from perfect context. This
module only ever measures the second kind of failure.

Metrics (all three exist in both modes):
  - faithfulness       heuristic: answer vocabulary grounded in context | ragas: LLM judge
  - answer_relevance   heuristic: query vocabulary covered by the answer | ragas: LLM judge
  - context_relevance  heuristic: query vocabulary covered by the context | ragas: LLM judge

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


def evaluate_generation_ragas(query: str, retrieved_texts: list[str]) -> dict:
    """Requires `pip install -e ".[ragas]"` and ANTHROPIC_API_KEY or
    OPENAI_API_KEY set. Raises if ragas isn't installed or no key is set —
    callers should check USE_RAGAS and fall back to the heuristic path."""
    from ragas import SingleTurnSample
    from ragas.metrics import AnswerRelevancy, Faithfulness, LLMContextPrecisionWithoutReference

    answer = generate_answer(query, retrieved_texts)
    sample = SingleTurnSample(user_input=query, response=answer, retrieved_contexts=retrieved_texts)

    return {
        "answer": answer,
        "faithfulness": Faithfulness().single_turn_score(sample),
        "answer_relevance": AnswerRelevancy().single_turn_score(sample),
        "context_relevance": LLMContextPrecisionWithoutReference().single_turn_score(sample),
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
    import anthropic  # optional dependency: pip install anthropic

    client = anthropic.Anthropic()
    model = os.environ.get("GENERATION_MODEL", "claude-haiku-4-5-20251001")
    msg = client.messages.create(
        model=model, max_tokens=500, messages=[{"role": "user", "content": build_llm_prompt(query, passages)}])
    answer = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
    cited = [i for i in range(1, len(passages) + 1) if f"[{i}]" in answer]
    citations = [{"passage_id": passages[i - 1]["passage_id"], "source_number": i} for i in cited]
    return {"answer": answer, "citations": citations, "method": f"llm:{model}"}


def generate_cited_answer(query: str, passages: list[dict]) -> dict:
    """Answer from retrieved passages (rank order) with citations.

    Extractive by default (no API key, deterministic). If GENERATION_BACKEND=llm and
    ANTHROPIC_API_KEY is set, uses an Anthropic model; falls back to extractive if the
    ``anthropic`` package is missing. The LLM path has not been exercised against the
    live API in this repository's tests.
    """
    if os.environ.get("GENERATION_BACKEND", "extractive") == "llm" and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _generate_llm(query, passages)
        except ImportError:
            pass
    return _generate_extractive(query, passages)
