# The AI parts

This document covers everything in the project that involves machine learning or an LLM: what is used,
what it is trusted with, how it is kept separate from evaluation, and where it can be wrong.

## Where AI appears

1. **Retrieval models** (local): an embedding model, a cross-encoder reranker. These are the things the
   harness evaluates. See `model.md`.
2. **Answer generation** (optional LLM): the RAG demo can have a Groq-hosted LLM write a cited answer.
3. **Generation evaluation** (optional LLM judge): an LLM can score faithfulness, answer relevance and
   context relevance.

Everything except the local retrieval models is opt-in and off by default. With no API key the project
works completely: extractive answers and lexical-heuristic generation metrics.

## One provider: Groq

Groq is the only LLM provider. The key is read from `GROQ_API_KEY` (environment or a local, git-ignored
`.env`, loaded by `python-dotenv` when `src` is imported). `src/generation/llm.py` is a ~90-line client over
Groq's OpenAI-compatible endpoint using only the standard library:

- `groq_chat(messages, model, max_tokens, temperature, json_mode)` returns the reply text.
- Retries HTTP 429 (free-tier rate limit) up to three attempts, honoring `Retry-After`.
- Raises `LLMError` for a missing key, HTTP or network errors, or an empty reply.
- Never logs or returns the key.

| Variable | Meaning | Default |
|---|---|---|
| `GROQ_API_KEY` | enables all LLM features | unset |
| `GROQ_MODEL` | Groq model id | `openai/gpt-oss-20b` |
| `GENERATION_BACKEND` | `extractive` or `llm` (RAG demo answers) | `extractive` |
| `USE_LLM_JUDGE` | `true` to score generation with the LLM judge | `false` |

## LLM answers (RAG demo)

With `GENERATION_BACKEND=llm` and a key, `generate_cited_answer` sends the numbered top passages and asks the
model to answer using only those sources and cite them as `[n]`:

> Answer the question using ONLY the numbered sources below. Cite sources inline as [n]. If the sources do
> not contain the answer, say so.

Citations returned by the API are the `[n]` markers the model actually wrote, mapped back to passage IDs. If
the call fails, the response is the extractive answer plus an `llm_error` field, so a fallback is never
mistaken for an LLM answer. The default extractive generator instead picks the best-overlapping sentence
from each of the top two passages.

## LLM judge (generation evaluation)

With `USE_LLM_JUDGE=true` and a key, `evaluate_generation` asks the model for three scores from 0 to 1 as a
strict JSON object (JSON mode on): `faithfulness` (claims supported by context), `answer_relevance`
(addresses the question), `context_relevance` (context contains what is needed). Scores are clamped to
[0, 1]; a malformed reply raises `LLMError` and the function falls back to the heuristic with a warning. The
`method` field says which path produced the numbers (`heuristic` or `llm_judge:<model>`).

The heuristic default is a set of lexical-overlap proxies (token overlap of answer vs. context, query vs.
answer, query vs. context). They are cheap and deterministic, and only directional.

## Separation from retrieval evaluation

A retrieval failure (right passage never retrieved) and a generation failure (bad answer from good context)
are different problems. Therefore:

- retrieval metrics come only from `src/evaluation/metrics.py` and gate CI;
- generation metrics come only from `src/generation/`, are never blended into a retrieval score, and are
  never used by the regression gate;
- the API returns `retrieval` and `generation` as independent blocks, plus `generation.context_passage_ids`
  and, for golden queries, `retrieval.golden_check`, so you can see which stage failed.

## Keeping tests and CI offline

`tests/conftest.py` sets `GENERATION_BACKEND=extractive`, `USE_LLM_JUDGE=false` and an empty
`GROQ_API_KEY` before anything imports `src`, so a developer's `.env` can never cause a test to call an
LLM. LLM code paths are tested with the network call monkeypatched (answer, citations, fallback on error,
judge parsing, malformed replies, judge fallback, missing key).

## What was verified live

Once, with a real key: a plain completion and a JSON-mode completion; then for the query "What warnings
must be given to a suspect before custodial questioning?" on the real-world dataset, retrieval returned
Miranda first, `openai/gpt-oss-20b` wrote an answer citing `[1]` (the correct passage), and the judge returned
1.0 for all three scores. That is a single example, not an evaluation; the judge has not been run over the
golden sets and no agreement with human judgment has been measured.

## Risks and limits

- **Judge scores are model opinions.** They can be biased (for example toward fluent or longer answers) and
  are not stable across models or prompts. Do not treat them as ground truth or gate CI on them.
- **LLM answers can hallucinate or mis-cite.** Citations are parsed from the model's own `[n]` markers, not
  verified against the text.
- **Free-tier limits.** Groq's free tier is rate-limited and its model catalogue changes; the client retries
  429s a few times and otherwise degrades to the offline behavior.
- **Data leaves the machine** when LLM features are on: the query and retrieved passages are sent to Groq.
  Do not enable them with confidential documents unless that is acceptable. The bundled datasets are
  fictional or public-domain.
- **Reasoning models** (this default is one) can return empty content if `max_tokens` is too small; the
  client raises a clear error in that case.
- **Ragas and other providers were deliberately not used.** Ragas defaults to other providers' LLMs and
  needs a separate embeddings setup; a small direct judge over Groq is simpler and was testable end to end.
  Any other provider would need new code and is out of scope by design.

## Security

`.env` is git-ignored. Never print, log or commit the key. If a key is ever exposed, revoke it in the Groq
console and create a new one.
