"""Single source of truth for retrieval configurations.

Every experiment the evaluation harness runs is one of these named configs.
Do not scatter chunk sizes, model names, or method flags elsewhere in the
codebase — add or change a configuration here.
"""
import os

EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
RERANKER_MODEL_NAME = os.environ.get("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")

TOP_K = 10  # candidates returned per query, at the (deduplicated) passage level

CONFIGS = {
    "baseline": {
        "description": "Fixed chunk size, dense embedding retrieval, no reranker.",
        "chunk_size": 300,
        "chunk_overlap": 50,
        "method": "dense",
        "reranker": False,
        "candidate_pool": None,  # None = search the full chunk index
    },
    "chunk_change": {
        "description": "Same as baseline but with a much smaller chunk size.",
        "chunk_size": 100,
        "chunk_overlap": 20,
        "method": "dense",
        "reranker": False,
        "candidate_pool": None,
    },
    "hybrid": {
        "description": "Baseline chunking; dense + BM25 combined via Reciprocal Rank Fusion.",
        "chunk_size": 300,
        "chunk_overlap": 50,
        "method": "hybrid",
        "reranker": False,
        "candidate_pool": None,
    },
    "reranker": {
        "description": "Baseline dense retrieval, then a cross-encoder reranks the top candidates.",
        "chunk_size": 300,
        "chunk_overlap": 50,
        "method": "dense",
        "reranker": True,
        "candidate_pool": None,
        "rerank_pool_size": 20,
    },
    "broken": {
        "description": (
            "Deliberately bad configuration: tiny chunks and a candidate pool "
            "clamped to 3 chunks, so most relevant documents are structurally "
            "unreachable regardless of ranking quality."
        ),
        "chunk_size": 40,
        "chunk_overlap": 0,
        "method": "dense",
        "reranker": False,
        "candidate_pool": 3,
    },
}

BASELINE_CONFIG_NAME = "baseline"
