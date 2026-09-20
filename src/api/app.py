"""Small RAG demo API: retrieve, then (optionally) generate an answer with citations.

Retrieval and generation are reported under separate top-level keys and there is
deliberately no combined score, so a bad answer can be traced to either the
retrieved sources (retrieval failure) or the answer built from them
(generation failure).

Run:  uvicorn src.api.app:app --reload
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.evaluation.evaluate import DATASETS, DEFAULT_DATASET, load_corpus, load_dataset_meta, load_golden_set
from src.generation.generate import evaluate_generation_heuristic, generate_cited_answer
from src.retrieval.configs import CONFIGS
from src.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
SNIPPET_CHARS = 240


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    config: str = "baseline"
    dataset: str = DEFAULT_DATASET
    top_k: int = Field(default=5, ge=1, le=10)


@lru_cache(maxsize=8)
def _corpus(dataset: str) -> tuple[dict, ...]:
    return tuple(load_corpus(dataset))


@lru_cache(maxsize=8)
def _retriever(dataset: str, config: str) -> Retriever:
    return Retriever(list(_corpus(dataset)), config)


def _validate(req: QueryRequest) -> None:
    if req.config not in CONFIGS:
        raise HTTPException(422, f"Unknown config '{req.config}'. Available: {sorted(CONFIGS)}")
    if req.dataset not in DATASETS:
        raise HTTPException(422, f"Unknown dataset '{req.dataset}'. Available: {DATASETS}")
    if not req.query.strip():
        raise HTTPException(422, "query must not be blank")


def _score_type(config: str) -> str:
    cfg = CONFIGS[config]
    return "cross_encoder" if cfg["reranker"] else ("rrf" if cfg["method"] == "hybrid" else "cosine")


def _retrieve(req: QueryRequest) -> tuple[dict, list[dict]]:
    """Run retrieval and return (retrieval block, full passages in rank order)."""
    by_id = {d["passage_id"]: d for d in _corpus(req.dataset)}
    scored = _retriever(req.dataset, req.config).retrieve_scored(req.query.strip(), top_k=req.top_k)
    passages = [by_id[pid] for pid, _ in scored]
    results = [
        {"rank": i, "passage_id": pid, "title": by_id[pid]["title"], "doc_type": by_id[pid]["doc_type"],
         "score": round(float(score), 4), "snippet": by_id[pid]["text"][:SNIPPET_CHARS]}
        for i, (pid, score) in enumerate(scored, start=1)
    ]
    block: dict = {
        "config": req.config, "dataset": req.dataset,
        "dataset_version": load_dataset_meta(req.dataset)["dataset_version"],
        "score_type": _score_type(req.config), "results": results,
    }
    golden = next((g for g in load_golden_set(req.dataset) if g["query"].strip() == req.query.strip()), None)
    if golden:
        ranks = {p: next((r["rank"] for r in results if r["passage_id"] == p), None) for p in golden["relevant_passage_ids"]}
        block["golden_check"] = {"query_id": golden["query_id"], "relevant_ranks": ranks,
                                 "all_relevant_retrieved": all(r is not None for r in ranks.values())}
    return block, passages


app = FastAPI(title="Groundtruth RAG demo", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Liveness plus what the server can serve."""
    return {"status": "ok", "datasets": DATASETS, "configs": sorted(CONFIGS)}


@app.post("/retrieve")
def retrieve(req: QueryRequest) -> dict:
    """Ranked passages with scores. Retrieval only; no generation."""
    _validate(req)
    block, _ = _retrieve(req)
    return {"retrieval": block}


@app.post("/ask")
def ask(req: QueryRequest) -> dict:
    """Retrieve, then generate a cited answer from the retrieved passages.

    ``retrieval`` and ``generation`` are independent blocks; ``generation.context_passage_ids``
    shows exactly which sources the answer was allowed to use.
    """
    _validate(req)
    retrieval, passages = _retrieve(req)
    generated = generate_cited_answer(req.query.strip(), passages)
    metrics = evaluate_generation_heuristic(req.query.strip(), [p["text"] for p in passages], answer=generated["answer"])
    return {
        "retrieval": retrieval,
        "generation": {
            "answer": generated["answer"], "citations": generated["citations"], "method": generated["method"],
            "context_passage_ids": [p["passage_id"] for p in passages],
            "heuristic_metrics": {k: round(metrics[k], 3) for k in ("faithfulness", "answer_relevance", "context_relevance")},
        },
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
