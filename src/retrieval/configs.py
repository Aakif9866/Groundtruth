"""Single source of truth for retrieval configurations.

Experiments are defined as YAML files under ``experiments/``. This module
loads them and translates the YAML schema into the flat dict shape the
``Retriever`` consumes. Add or change an experiment by editing/adding a YAML
file, not by scattering values through the code.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
EXPERIMENTS_DIR = ROOT / "experiments"

EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
RERANKER_MODEL_NAME = os.environ.get("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")

TOP_K = 10  # candidates returned per query, at the (deduplicated) passage level
BASELINE_CONFIG_NAME = "baseline"
DEFAULT_CONFIG_ORDER = ["baseline", "chunk_change", "hybrid", "reranker", "broken"]


def translate_experiment(raw: dict[str, Any]) -> dict[str, Any]:
    """Translate one parsed experiment YAML into the flat internal config dict."""
    for key in ("name", "retrieval", "chunking"):
        if key not in raw:
            raise ValueError(f"Experiment config is missing required key '{key}'")

    retrieval = raw["retrieval"]
    dense, bm25 = bool(retrieval.get("dense")), bool(retrieval.get("bm25"))
    if dense and bm25:
        if retrieval.get("fusion") != "rrf":
            raise ValueError(f"{raw['name']}: hybrid retrieval requires fusion: rrf")
        method = "hybrid"
    elif dense:
        method = "dense"
    else:
        raise ValueError(f"{raw['name']}: retrieval must enable dense (bm25-only is not supported)")

    chunking = raw["chunking"]
    size, overlap = int(chunking["size"]), int(chunking.get("overlap", 0))
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError(f"{raw['name']}: invalid chunking (size={size}, overlap={overlap})")

    reranker = raw.get("reranker") or {}
    pool = raw.get("candidate_pool")
    if pool is not None and int(pool) <= 0:
        raise ValueError(f"{raw['name']}: candidate_pool must be positive or null")

    cfg: dict[str, Any] = {
        "name": raw["name"],
        "description": raw.get("description", ""),
        "chunk_size": size,
        "chunk_overlap": overlap,
        "method": method,
        "reranker": bool(reranker.get("enabled", False)),
        "candidate_pool": int(pool) if pool is not None else None,
        "embedding_model": raw.get("embedding_model") or EMBEDDING_MODEL_NAME,
        "reranker_model": (reranker.get("model") or RERANKER_MODEL_NAME) if reranker.get("enabled") else None,
    }
    if cfg["reranker"]:
        cfg["rerank_pool_size"] = int(reranker.get("top_n", 20))
    return cfg


def load_experiment_config(path: str | Path) -> dict[str, Any]:
    """Load and translate a single experiment YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    return translate_experiment(raw)


def _load_all() -> dict[str, dict[str, Any]]:
    loaded = {}
    for path in sorted(EXPERIMENTS_DIR.glob("*.yaml")):
        cfg = load_experiment_config(path)
        loaded[cfg["name"]] = cfg
    ordered = {n: loaded[n] for n in DEFAULT_CONFIG_ORDER if n in loaded}
    ordered.update({n: c for n, c in loaded.items() if n not in ordered})
    return ordered


CONFIGS = _load_all()
