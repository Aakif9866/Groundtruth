# Models

Every model used, what it does, and where it is configured. No model is trained or fine-tuned here; all
are used off the shelf.

| Role | Model | Where | Runs |
|---|---|---|---|
| Dense retrieval (embeddings) | `sentence-transformers/all-MiniLM-L6-v2` | every config | locally |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `reranker` config only | locally |
| Lexical retrieval | BM25 (Okapi, `rank-bm25`) | `hybrid` config, and error analysis | locally, no model files |
| LLM answers (optional) | `openai/gpt-oss-20b` on Groq | RAG demo, `GENERATION_BACKEND=llm` | Groq API |
| LLM judge (optional) | `openai/gpt-oss-20b` on Groq | generation evaluation, `USE_LLM_JUDGE=true` | Groq API |

## Embedding model

A small sentence-embedding model (MiniLM, 6 layers). Chunks and queries are encoded with
`normalize_embeddings=True`, so cosine similarity is a dot product. Similarity against all chunk vectors is
computed with scikit-learn's `cosine_similarity`; there is no vector database or ANN index (the corpora are
tiny). Chunk embeddings are computed lazily once per `Retriever` instance and not cached on disk.

Change it with `EMBEDDING_MODEL_NAME` or an `embedding_model:` key in an experiment YAML. Any
sentence-transformers hub id works. Absolute metrics change when the model changes, so re-approve the
baseline deliberately (never to hide a regression).

## Reranker

A cross-encoder that scores (query, chunk) pairs jointly. In the `reranker` config the dense retriever's top
`top_n` chunks (default 20) are rescored and reordered; chunks outside that pool cannot be recovered, which is
a real trade-off of reranking. Set with `RERANKER_MODEL_NAME` or `reranker.model` in YAML.

## BM25 and fusion

`BM25Okapi` over lowercase alphanumeric tokens of each chunk. In the `hybrid` config the dense ranking and
the BM25 ranking are fused with Reciprocal Rank Fusion (`score = sum 1/(60 + rank)`), which needs no weight
tuning. BM25 is also used by the error analysis to decide whether a lexical signal existed
(`semantic_mismatch` vs `lexical_mismatch`).

## Chunking

Overlapping character windows (size and overlap per config). Small windows fragment context, which is
exactly what the `chunk_change` and `broken` configs demonstrate.

## LLM (Groq)

`GROQ_MODEL` selects the model, defaulting to `openai/gpt-oss-20b`. Groq's available model list changes over
time (a previously common Llama model was not offered when this was integrated), so if a call fails with a
model error, list current models with your key at `https://api.groq.com/openai/v1/models` and set
`GROQ_MODEL`. Calls use temperature 0 and `reasoning_effort: "low"`, because this model family otherwise
spends output tokens on hidden reasoning. See `ai.md` for prompts and behavior.

## Device and determinism

sentence-transformers picks an accelerator automatically (Apple `mps` locally, CPU in CI/Docker). Results
are deterministic on one machine (tested) but can differ in the last floating-point digits across
hardware, so the CI reproduction test allows a 0.005 tolerance while the regression gate itself uses the
0.01 threshold.

## Model downloads

The two Hugging Face models download on first use (about tens of MB each); the Dockerfile bakes them into
the image. No Hugging Face token is required, though unauthenticated downloads are rate-limited.
