"""Chunking, dense/BM25/hybrid retrieval, and cross-encoder reranking.

Kept intentionally simple: this is not meant to be a production search
engine, just enough retrieval machinery to make the evaluation harness'
configurations (see configs.py) meaningfully different from each other.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.metrics.pairwise import cosine_similarity

from src.retrieval.configs import CONFIGS, EMBEDDING_MODEL_NAME, RERANKER_MODEL_NAME, TOP_K

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@lru_cache(maxsize=1)
def _get_embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


@lru_cache(maxsize=1)
def _get_reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(RERANKER_MODEL_NAME)


@dataclass
class Chunk:
    chunk_id: str
    passage_id: str
    text: str


def chunk_document(passage_id: str, text: str, chunk_size: int, overlap: int) -> list[Chunk]:
    """Splits text into overlapping character windows. Small chunk_size with
    little/no overlap deliberately fragments context (used by the
    chunk_change and broken configs to demonstrate real chunk-boundary
    effects, not simulated ones)."""
    if len(text) <= chunk_size:
        return [Chunk(f"{passage_id}-0", passage_id, text)]
    chunks = []
    step = max(chunk_size - overlap, 1)
    start = 0
    i = 0
    while start < len(text):
        window = text[start:start + chunk_size]
        if window.strip():
            chunks.append(Chunk(f"{passage_id}-{i}", passage_id, window))
            i += 1
        start += step
    return chunks


class Retriever:
    def __init__(self, corpus: list[dict], config_name: str):
        if config_name not in CONFIGS:
            raise ValueError(f"Unknown retrieval config: {config_name}")
        self.config_name = config_name
        self.config = CONFIGS[config_name]
        self.corpus_by_id = {d["passage_id"]: d for d in corpus}

        self.chunks: list[Chunk] = []
        for doc in corpus:
            self.chunks.extend(
                chunk_document(doc["passage_id"], doc["text"], self.config["chunk_size"], self.config["chunk_overlap"])
            )

        pool = self.config.get("candidate_pool")
        if pool is not None:
            self.chunks = self.chunks[:pool]

        self._chunk_texts = [c.text for c in self.chunks]
        self._bm25 = BM25Okapi([tokenize(t) for t in self._chunk_texts]) if self._chunk_texts else None
        self._chunk_embeddings = None  # computed lazily, only if a dense method is used

    def _ensure_embeddings(self):
        if self._chunk_embeddings is None:
            embedder = _get_embedder()
            self._chunk_embeddings = embedder.encode(self._chunk_texts, show_progress_bar=False, normalize_embeddings=True)

    def _dense_scores(self, query: str) -> np.ndarray:
        self._ensure_embeddings()
        embedder = _get_embedder()
        q_emb = embedder.encode([query], show_progress_bar=False, normalize_embeddings=True)
        return cosine_similarity(q_emb, self._chunk_embeddings)[0]

    def _bm25_scores(self, query: str) -> np.ndarray:
        return np.array(self._bm25.get_scores(tokenize(query)))

    @staticmethod
    def _rank_from_scores(scores: np.ndarray) -> list[int]:
        return list(np.argsort(-scores))

    def _reciprocal_rank_fusion(self, rankings: list[list[int]], k: int = 60) -> np.ndarray:
        n = len(self._chunk_texts)
        fused = np.zeros(n)
        for ranking in rankings:
            for rank, idx in enumerate(ranking):
                fused[idx] += 1.0 / (k + rank + 1)
        return fused

    def retrieve_chunks(self, query: str, pool_size: int | None = None) -> list[tuple[Chunk, float]]:
        """Returns (chunk, score) pairs ranked best-first, before passage-level dedup."""
        if not self._chunk_texts:
            return []

        method = self.config["method"]
        if method == "dense":
            scores = self._dense_scores(query)
        elif method == "hybrid":
            dense_scores = self._dense_scores(query)
            bm25_scores = self._bm25_scores(query)
            fused = self._reciprocal_rank_fusion([
                self._rank_from_scores(dense_scores),
                self._rank_from_scores(bm25_scores),
            ])
            scores = fused
        else:
            raise ValueError(f"Unknown retrieval method: {method}")

        order = np.argsort(-scores)

        if self.config.get("reranker"):
            n = pool_size or self.config.get("rerank_pool_size", 20)
            candidate_idxs = list(order[:n])
            reranker = _get_reranker()
            pairs = [(query, self._chunk_texts[i]) for i in candidate_idxs]
            rerank_scores = reranker.predict(pairs)
            reranked = sorted(zip(candidate_idxs, rerank_scores), key=lambda x: -x[1])
            return [(self.chunks[i], float(s)) for i, s in reranked]

        return [(self.chunks[i], float(scores[i])) for i in order]

    def retrieve(self, query: str, top_k: int = TOP_K) -> list[str]:
        """Returns up to top_k unique passage_ids, ranked best-first (chunk
        results deduplicated to their parent document since golden relevance
        labels are document-level)."""
        seen = []
        for chunk, _score in self.retrieve_chunks(query):
            if chunk.passage_id not in seen:
                seen.append(chunk.passage_id)
            if len(seen) >= top_k:
                break
        return seen
