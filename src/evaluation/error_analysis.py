"""Identifies the worst-performing golden queries for a given retrieval
configuration and produces a rule-based (not invented) failure explanation
for each, grounded in signals actually available at query time: term
overlap, chunk fragmentation, candidate-pool size, and category.

Usage:
    python -m src.evaluation.error_analysis                # baseline config, top 5
    python -m src.evaluation.error_analysis --config hybrid --n 8
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.retrieval.configs import CONFIGS, TOP_K
from src.retrieval.retriever import Retriever, tokenize
from src.evaluation.metrics import evaluate_query
from src.evaluation.evaluate import load_corpus, load_golden_set, REPORTS_DIR


def diagnose_failure(ex: dict, retrieved_ids: list[str], retriever: Retriever, corpus_by_id: dict) -> str:
    relevant_ids = ex["relevant_passage_ids"]
    query_terms = set(tokenize(ex["query"]))
    retrieved_set = set(retrieved_ids)
    missing = [pid for pid in relevant_ids if pid not in retrieved_set]
    # Present but not ranked first: a milder failure (found, but not the top
    # hit), still worth surfacing since MRR/nDCG penalize it.
    outranked = [pid for pid in relevant_ids if pid in retrieved_set and retrieved_ids.index(pid) > 0]

    if not missing and not outranked:
        return "No failure: all relevant passages were retrieved and ranked first."

    reasons = []

    for pid in outranked:
        rank = retrieved_ids.index(pid) + 1
        window = "outside the top 5" if rank > 5 else "within the top 5 but not ranked first"
        reasons.append(
            f"ambiguous query / weak top-of-list separation for {pid}: the relevant "
            f"document was retrieved, but only at rank {rank} ({window}), meaning at "
            f"least one less-relevant chunk scored higher."
        )

    if ex["category"] == "multi_hop" and len(missing) < len(relevant_ids):
        reasons.append(
            "multi-hop retrieval failure: only part of the required passage set was "
            "retrieved, which is enough to look successful on a single-passage check "
            "but fails a query that depends on both sources."
        )

    n_chunks_for_corpus = len(retriever.chunks)
    pool = retriever.config.get("candidate_pool")
    if pool is not None and pool < n_chunks_for_corpus:
        reasons.append(
            f"insufficient candidate pool: this configuration only searches {pool} "
            f"chunks out of {n_chunks_for_corpus}, so most documents (including the "
            f"relevant one) are structurally unreachable."
        )

    for pid in missing:
        doc = corpus_by_id.get(pid)
        if doc is None:
            continue
        doc_terms = set(tokenize(doc["text"]))
        overlap = query_terms & doc_terms
        overlap_ratio = len(overlap) / max(len(query_terms), 1)
        n_doc_chunks = sum(1 for c in retriever.chunks if c.passage_id == pid)
        if n_doc_chunks == 0:
            continue  # already covered by the candidate-pool reason above
        if overlap_ratio < 0.35:
            reasons.append(
                f"semantic mismatch for {pid}: only {len(overlap)}/{len(query_terms)} "
                f"query terms appear anywhere in the target document, so lexical "
                f"overlap alone would not have surfaced it either — a genuine embedding "
                f"ranking miss rather than a vocabulary gap."
            )
        elif n_doc_chunks > 1:
            reasons.append(
                f"chunk boundary problem for {pid}: the document was split into "
                f"{n_doc_chunks} chunks, and the terms that would identify it "
                f"({', '.join(sorted(overlap)[:5])}) may be spread across chunks rather "
                f"than concentrated in the single highest-scoring one."
            )
        else:
            reasons.append(
                f"ranking miss for {pid}: lexical overlap with the query is high "
                f"({len(overlap)}/{len(query_terms)} terms) but the document still did "
                f"not rank in the top {TOP_K}, suggesting a reranker or scoring issue "
                f"rather than a content gap."
            )

    if not reasons:
        reasons.append("ambiguous query: relevant and irrelevant passages scored similarly close together.")

    return " ".join(reasons)


def run(config_name: str, n: int):
    corpus = load_corpus()
    golden = load_golden_set()
    corpus_by_id = {d["passage_id"]: d for d in corpus}
    retriever = Retriever(corpus, config_name)

    scored = []
    for ex in golden:
        retrieved = retriever.retrieve(ex["query"], top_k=TOP_K)
        metrics = evaluate_query(retrieved, ex["relevant_passage_ids"])
        scored.append((metrics["recall@10"], metrics["recall@5"], metrics["mrr"], ex, retrieved))

    # Worst first: rank by Recall@10 (a full miss), then Recall@5 (found too
    # late to matter in a tight context window), then MRR as a tiebreaker.
    # A query with recall@5 < 1.0 but recall@10 == 1.0 is a real, milder
    # failure mode (found, but ranked too low) and is reported as such below.
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    worst = [s for s in scored if s[0] < 1.0 or s[1] < 1.0]

    # This retriever performs well enough that outright misses are rare. If
    # fewer than n queries qualify as a real recall failure, top the list up
    # with the next-worst-by-MRR queries (correct passage retrieved, but not
    # ranked first) so the report still surfaces n queries worth reviewing.
    # These are reported honestly as ranking underperformance, not misses.
    if len(worst) < n:
        already = {id(s) for s in worst}
        filler = [s for s in scored if id(s) not in already and s[2] < 1.0]
        worst += filler[: n - len(worst)]
    worst = worst[:n]

    lines = [f"# Error Analysis: '{config_name}' configuration\n", f"Worst {len(worst)} queries by Recall@10 then Recall@5 (lowest first):\n"]
    for recall10, recall5, mrr, ex, retrieved in worst:
        doc = corpus_by_id[ex["relevant_passage_ids"][0]]
        block = [
            f"## Query ID: {ex['query_id']}",
            f"Category: {ex['category']} | Difficulty: {ex['difficulty']} | Recall@5: {recall5:.2f} | Recall@10: {recall10:.2f} | MRR: {mrr:.2f}",
            "",
            f"Query:\n{ex['query']}",
            "",
            f"Expected relevant passage(s): {', '.join(ex['relevant_passage_ids'])}",
            f"  (e.g. {doc['passage_id']}: \"{doc['title']}\")",
            "",
            "Retrieved results:",
        ]
        for i, pid in enumerate(retrieved[:5], start=1):
            title = corpus_by_id.get(pid, {}).get("title", "?")
            block.append(f"  {i}. {pid} - {title}")
        block.append("")
        block.append(f"Failure reason:\n{diagnose_failure(ex, retrieved, retriever, corpus_by_id)}")
        block.append("\n---\n")
        lines.append("\n".join(block))

    report = "\n".join(lines)
    print(report)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "error_analysis.md"
    out_path.write_text(report)
    print(f"\nWrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="baseline", choices=list(CONFIGS.keys()))
    parser.add_argument("--n", type=int, default=5)
    args = parser.parse_args()
    run(args.config, args.n)


if __name__ == "__main__":
    main()
