"""Small RAG demo API: retrieve, then (optionally) generate an answer with citations.

Retrieval and generation are reported under separate top-level keys and there is
deliberately no combined score, so a bad answer can be traced to either the
retrieved sources (retrieval failure) or the answer built from them
(generation failure).

Run:  uvicorn src.api.app:app --reload
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.evaluation.evaluate import (
    DATASETS, DEFAULT_DATASET, REPORTS_DIR, load_corpus, load_dataset_meta, load_golden_set,
)
from src.evaluation.regression_gate import (
    BASELINE_PATH, RegressionGateError, check_regression, get_threshold, load_baseline,
)
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
         "score": round(float(score), 4), "snippet": by_id[pid]["text"][:SNIPPET_CHARS], "text": by_id[pid]["text"]}
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
            **({"llm_error": generated["llm_error"]} if "llm_error" in generated else {}),
            "context_passage_ids": [p["passage_id"] for p in passages],
            "heuristic_metrics": {k: round(metrics[k], 3) for k in ("faithfulness", "answer_relevance", "context_relevance")},
        },
    }


def _summary_path(dataset: str) -> Path:
    return REPORTS_DIR / "summary.json" if dataset == DEFAULT_DATASET else REPORTS_DIR / dataset / "summary.json"


def _gate(dataset: str, summary: dict) -> dict | None:
    """Regression-gate verdict per config. Only defined for the synthetic dataset (the approved baseline's)."""
    if dataset != DEFAULT_DATASET:
        return None
    try:
        baseline = load_baseline(BASELINE_PATH)
        threshold = get_threshold()
        verdicts = {}
        for name, cfg in summary["configs"].items():
            result = check_regression(
                baseline["recall@10"], cfg["metrics"]["overall"]["recall@10"], threshold,
                baseline.get("dataset_version"), summary["dataset_version"])
            verdicts[name] = {"passed": result.passed, "drop": result.drop}
    except (RegressionGateError, ValueError) as e:
        return {"error": str(e)}
    return {"baseline_recall10": baseline["recall@10"], "threshold": threshold,
            "dataset_version": baseline.get("dataset_version"), "results": verdicts}


@app.get("/api/evaluation")
def evaluation(dataset: str = DEFAULT_DATASET) -> dict:
    """Latest committed evaluation summary for a dataset, plus regression-gate verdicts."""
    if dataset not in DATASETS:
        raise HTTPException(422, f"Unknown dataset '{dataset}'. Available: {DATASETS}")
    path = _summary_path(dataset)
    if not path.exists():
        raise HTTPException(404, f"No evaluation summary for '{dataset}'. Run `python -m src.evaluation.evaluate --dataset {dataset}`.")
    summary = json.loads(path.read_text())
    return {"summary": summary, "gate": _gate(dataset, summary)}


@app.get("/api/examples")
def examples(dataset: str = DEFAULT_DATASET, limit: int = 6) -> dict:
    """A few golden-set questions (one per category first) to try in the UI."""
    if dataset not in DATASETS:
        raise HTTPException(422, f"Unknown dataset '{dataset}'. Available: {DATASETS}")
    picked, seen = [], set()
    golden = load_golden_set(dataset)
    for ex in golden:  # one per category first
        if ex["category"] not in seen:
            seen.add(ex["category"])
            picked.append(ex)
    picked += [ex for ex in golden if ex not in picked]
    limit = max(1, min(limit, 12))
    return {"dataset": dataset, "examples": [
        {"query_id": e["query_id"], "query": e["query"], "category": e["category"]} for e in picked[:limit]]}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
