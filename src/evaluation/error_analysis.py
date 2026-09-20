"""Rule-based failure analysis for retrieval results.

Every diagnosis is derived from signals that are actually computed from the
query, the corpus, and the retrieval result (term overlap, corpus-wide term
frequency, chunk counts, BM25 rank, candidate pool size). Nothing is invented:
the evidence string attached to each diagnosis lists the numbers behind it.
When no rule fires the label is ``unknown``.

Usage:
    python -m src.evaluation.error_analysis                         # baseline, worst 5
    python -m src.evaluation.error_analysis --config hybrid --n 8
    python -m src.evaluation.error_analysis --config baseline --compare-with hybrid
    python -m src.evaluation.error_analysis --dataset real_world
"""
from __future__ import annotations

import argparse
import logging
from collections import Counter
from dataclasses import asdict, dataclass, field

import numpy as np

from src.evaluation.evaluate import (
    DATASETS, DEFAULT_DATASET, REPORTS_DIR, load_corpus, load_golden_set,
)
from src.evaluation.metrics import evaluate_query
from src.retrieval.configs import CONFIGS, TOP_K
from src.retrieval.retriever import Retriever, tokenize

logger = logging.getLogger(__name__)

FAILURE_TYPES = [
    "chunk_boundary", "lexical_mismatch", "semantic_mismatch", "distractor_confusion",
    "multi_hop_failure", "candidate_pool_limitation", "ranking_failure",
    "generic_term_collision", "unknown",
]

STOPWORDS = frozenset(
    "a an the of in to and or is are was were what which who how does do did for on by with that this under when "
    "as at be from it its between into than then there their have has had not must may can about".split()
)
GENERIC_DF = 3            # a query term appearing in >= this many documents is "generic"
LOW_OVERLAP = 0.35        # fraction of query content terms present in a document
SCATTER_RATIO = 0.6       # best single chunk holds < this share of the document's matching terms
GENERIC_SHARE = 0.6       # competitor matches >= this share of the query's generic terms


@dataclass
class Diagnosis:
    """A single failure label and the evidence behind it."""

    failure_type: str
    evidence: str


@dataclass
class FailureRecord:
    """One imperfectly retrieved query with its diagnosis."""

    query_id: str
    category: str
    difficulty: str
    query: str
    recall_at_5: float
    recall_at_10: float
    mrr: float
    relevant_ids: list[str]
    retrieved_ids: list[str]
    relevant_ranks: dict[str, int | None]
    failure_type: str
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CorpusStats:
    """Precomputed per-document term sets and document frequencies."""

    doc_terms: dict[str, set[str]] = field(default_factory=dict)
    df: Counter = field(default_factory=Counter)

    @classmethod
    def from_corpus(cls, corpus_by_id: dict[str, dict]) -> "CorpusStats":
        stats = cls()
        for pid, doc in corpus_by_id.items():
            terms = set(tokenize(doc["text"]))
            stats.doc_terms[pid] = terms
            stats.df.update(terms)
        return stats


def content_terms(query: str) -> set[str]:
    """Query tokens minus stopwords and very short tokens."""
    return {t for t in tokenize(query) if t not in STOPWORDS and len(t) > 2}


def _passage_bm25_rank(retriever: Retriever, query: str, pid: str) -> int | None:
    """1-based rank of a passage under BM25 alone (best chunk per passage); None if it has no lexical match."""
    if retriever._bm25 is None:
        return None
    scores = retriever._bm25_scores(query)
    best: dict[str, float] = {}
    for chunk, score in zip(retriever.chunks, scores):
        best[chunk.passage_id] = max(best.get(chunk.passage_id, -np.inf), float(score))
    if pid not in best or best[pid] <= 0:  # no lexical match at all -> no meaningful BM25 rank
        return None
    ordered = sorted(best, key=lambda p: -best[p])
    return ordered.index(pid) + 1


def _diagnose_pid(pid: str, rank: int | None, ex: dict, retrieved_ids: list[str],
                  retriever: Retriever, stats: CorpusStats) -> Diagnosis | None:
    q_terms = content_terms(ex["query"])
    rel_terms = stats.doc_terms.get(pid, set())
    rel_overlap = q_terms & rel_terms
    ahead = retrieved_ids[: rank - 1] if rank else retrieved_ids[:5]
    competitors = [p for p in ahead if p not in ex["relevant_passage_ids"]]

    best_comp, best_comp_overlap = None, set()
    for p in competitors:
        ov = q_terms & stats.doc_terms.get(p, set())
        if best_comp is None or len(ov) > len(best_comp_overlap):
            best_comp, best_comp_overlap = p, ov

    generic = {t for t in q_terms if stats.df[t] >= GENERIC_DF}
    distinctive = q_terms - generic
    rel_distinctive = distinctive & rel_terms

    if best_comp and len(generic) >= 2 and rel_distinctive:
        comp_generic = generic & stats.doc_terms[best_comp]
        comp_distinctive = rel_distinctive & stats.doc_terms[best_comp]
        if len(comp_generic) >= GENERIC_SHARE * len(generic) and len(comp_distinctive) < len(rel_distinctive):
            gen_desc = ", ".join(f"{t}(df={stats.df[t]})" for t in sorted(comp_generic))
            return Diagnosis("generic_term_collision", (
                f"{best_comp} ranked above {pid} and matches {len(comp_generic)}/{len(generic)} generic query terms "
                f"[{gen_desc}] but only {len(comp_distinctive)}/{len(rel_distinctive)} of the terms distinctive to "
                f"{pid} [{', '.join(sorted(rel_distinctive))}]."))

    if best_comp and rel_overlap and len(best_comp_overlap) >= len(rel_overlap):
        return Diagnosis("distractor_confusion", (
            f"{best_comp} ranked above {pid} while matching {len(best_comp_overlap)} query terms vs "
            f"{len(rel_overlap)} for {pid}: a competing passage was at least as lexically close to the query."))

    pid_chunks = [c for c in retriever.chunks if c.passage_id == pid]
    if len(pid_chunks) > 1 and len(rel_overlap) >= 2:
        best_chunk = max(len(q_terms & set(tokenize(c.text))) for c in pid_chunks)
        if best_chunk < SCATTER_RATIO * len(rel_overlap):
            return Diagnosis("chunk_boundary", (
                f"{pid} was split into {len(pid_chunks)} chunks; its best single chunk contains {best_chunk} of the "
                f"{len(rel_overlap)} query terms found anywhere in the document "
                f"[{', '.join(sorted(rel_overlap))}], so matching terms are scattered across chunks."))

    overlap_ratio = len(rel_overlap) / max(len(q_terms), 1)
    bm25_rank = _passage_bm25_rank(retriever, ex["query"], pid)
    if bm25_rank is not None and bm25_rank <= 5 and (rank is None or rank > bm25_rank):
        return Diagnosis("semantic_mismatch", (
            f"BM25 alone ranks {pid} at {bm25_rank} ({len(rel_overlap)}/{len(q_terms)} query terms present) but this "
            f"config ranked it {rank if rank else 'outside the top ' + str(TOP_K)}: the vocabulary matches, the "
            f"embedding ranking did not follow."))
    if overlap_ratio < LOW_OVERLAP or (bm25_rank is not None and bm25_rank > TOP_K):
        return Diagnosis("lexical_mismatch", (
            f"only {len(rel_overlap)}/{len(q_terms)} query content terms appear in {pid}"
            + (f" and BM25 alone ranks it {bm25_rank}" if bm25_rank else "")
            + ": the query and document use different vocabulary."))

    if rank is not None and rank > 1:
        return Diagnosis("ranking_failure", (
            f"{pid} was retrieved at rank {rank} with {len(rel_overlap)}/{len(q_terms)} query terms present; no "
            f"competing passage matched the query better lexically and no chunk or vocabulary signal explains the "
            f"lower rank."))
    return None


def classify_failure(ex: dict, retrieved_ids: list[str], retriever: Retriever,
                     stats: CorpusStats) -> Diagnosis:
    """Assign exactly one failure label to an imperfectly retrieved query.

    Rule order: candidate_pool_limitation, multi_hop_failure, then per-passage
    signals (generic_term_collision, distractor_confusion, chunk_boundary,
    semantic_mismatch, lexical_mismatch, ranking_failure); otherwise unknown.
    """
    relevant = ex["relevant_passage_ids"]
    ranks = {p: (retrieved_ids.index(p) + 1 if p in retrieved_ids else None) for p in relevant}
    missing = [p for p, r in ranks.items() if r is None]

    pool = retriever.config.get("candidate_pool")
    indexed = {c.passage_id for c in retriever.chunks}
    unreachable = [p for p in relevant if p not in indexed]
    if pool is not None and unreachable:
        return Diagnosis("candidate_pool_limitation", (
            f"config searches only {pool} chunks; {', '.join(unreachable)} has no chunk in that pool so it cannot be "
            f"retrieved by any ranking."))

    if ex["category"] == "multi_hop" and missing:
        found = [p for p in relevant if p not in missing]
        return Diagnosis("multi_hop_failure", (
            f"needs {len(relevant)} passages; retrieved {len(found)} ({', '.join(found) or 'none'}), "
            f"missing {', '.join(missing)} from the top {TOP_K}."))

    for pid in missing + [p for p in relevant if ranks[p] and ranks[p] > 1]:
        diagnosis = _diagnose_pid(pid, ranks[pid], ex, retrieved_ids, retriever, stats)
        if diagnosis:
            return diagnosis
    return Diagnosis("unknown", "no diagnostic rule matched the available signals.")


def analyze_queries(retriever: Retriever, corpus: list[dict], golden: list[dict],
                    retrieved: dict[str, list[str]] | None = None) -> tuple[list[FailureRecord], int]:
    """Classify every imperfectly retrieved query (MRR < 1 or recall < 1).

    ``retrieved`` optionally maps query_id to an already computed top-K list
    (e.g. from ``evaluate.run_config``) so retrieval is not repeated.
    Returns the records (worst first) and the total number of queries evaluated.
    """
    corpus_by_id = {d["passage_id"]: d for d in corpus}
    stats = CorpusStats.from_corpus(corpus_by_id)
    records: list[FailureRecord] = []
    for ex in golden:
        ranked = retrieved[ex["query_id"]] if retrieved else retriever.retrieve(ex["query"], top_k=TOP_K)
        m = evaluate_query(ranked, ex["relevant_passage_ids"])
        if m["recall@10"] >= 1.0 and m["recall@5"] >= 1.0 and m["mrr"] >= 1.0:
            continue
        diagnosis = classify_failure(ex, ranked, retriever, stats)
        records.append(FailureRecord(
            query_id=ex["query_id"], category=ex["category"], difficulty=ex["difficulty"], query=ex["query"],
            recall_at_5=m["recall@5"], recall_at_10=m["recall@10"], mrr=m["mrr"],
            relevant_ids=list(ex["relevant_passage_ids"]), retrieved_ids=ranked,
            relevant_ranks={p: (ranked.index(p) + 1 if p in ranked else None) for p in ex["relevant_passage_ids"]},
            failure_type=diagnosis.failure_type, evidence=diagnosis.evidence,
        ))
    records.sort(key=lambda r: (r.recall_at_10, r.recall_at_5, r.mrr))
    return records, len(golden)


def aggregate_failure_types(records: list[FailureRecord]) -> list[tuple[str, int, float]]:
    """(failure_type, count, percentage) for every type with at least one record, most common first."""
    counts = Counter(r.failure_type for r in records)
    total = sum(counts.values())
    return [(t, n, 100.0 * n / total) for t, n in counts.most_common()] if total else []


def format_summary_table(rows: list[tuple[str, int, float]]) -> str:
    """Plain-text failure-type table."""
    lines = [f"{'Failure Type':<28}{'Count':>6}{'Percentage':>13}", "-" * 47]
    lines += [f"{t:<28}{n:>6}{pct:>12.0f}%" for t, n, pct in rows]
    return "\n".join(lines)


def format_comparison_table(name_a: str, rows_a: list, name_b: str, rows_b: list) -> str:
    """Side-by-side failure-type counts for two configurations."""
    a = {t: n for t, n, _ in rows_a}
    b = {t: n for t, n, _ in rows_b}
    types = [t for t in FAILURE_TYPES if t in a or t in b]
    lines = [f"{'Failure Type':<28}{name_a:>14}{name_b:>14}{'Change':>9}", "-" * 65]
    lines += [f"{t:<28}{a.get(t, 0):>14}{b.get(t, 0):>14}{b.get(t, 0) - a.get(t, 0):>+9}" for t in types]
    return "\n".join(lines)


def format_record(rec: FailureRecord, corpus_by_id: dict[str, dict]) -> str:
    """Markdown block for one failing query."""
    def title(pid: str) -> str:
        return corpus_by_id.get(pid, {}).get("title", "?")

    ranks = ", ".join(f"{p}: {r if r else f'not in top {TOP_K}'}" for p, r in rec.relevant_ranks.items())
    lines = [
        f"## Query ID: {rec.query_id}",
        f"Category: {rec.category} | Difficulty: {rec.difficulty} | Recall@5: {rec.recall_at_5:.2f} | "
        f"Recall@10: {rec.recall_at_10:.2f} | MRR: {rec.mrr:.2f}",
        "", f"Query:\n{rec.query}", "",
        f"Relevant passage IDs: {', '.join(rec.relevant_ids)}",
        f"Relevant passage rank(s): {ranks}",
        f"Retrieved passage IDs: {', '.join(rec.retrieved_ids)}",
        "", "Top retrieved:",
    ]
    lines += [f"  {i}. {p} - {title(p)}" for i, p in enumerate(rec.retrieved_ids[:5], start=1)]
    lines += ["", f"Diagnosis: {rec.failure_type}", f"Evidence: {rec.evidence}", "", "---", ""]
    return "\n".join(lines)


def build_report(config_name: str, dataset: str, records: list[FailureRecord], total_queries: int,
                 corpus_by_id: dict[str, dict], n: int, compare: tuple[str, list] | None = None) -> str:
    """Full markdown error-analysis report."""
    summary = aggregate_failure_types(records)
    lines = [
        f"# Error Analysis: '{config_name}' configuration ({dataset} dataset)\n",
        f"{len(records)} of {total_queries} queries were imperfectly retrieved "
        f"(Recall@5 < 1, Recall@10 < 1, or the first relevant passage not ranked first).\n",
        "## Failure type summary\n", "```", format_summary_table(summary), "```\n",
    ]
    if compare:
        lines += [f"## Comparison with '{compare[0]}'\n", "```",
                  format_comparison_table(config_name, summary, compare[0], compare[1]), "```\n"]
    lines += [f"## Worst {min(n, len(records))} queries (lowest Recall@10, then Recall@5, then MRR)\n"]
    lines += [format_record(r, corpus_by_id) for r in records[:n]]
    return "\n".join(lines)


def run(config_name: str, n: int, dataset: str = DEFAULT_DATASET, compare_with: str | None = None) -> str:
    """Analyze one config (optionally against another) and write reports/error_analysis.md."""
    corpus, golden = load_corpus(dataset), load_golden_set(dataset)
    corpus_by_id = {d["passage_id"]: d for d in corpus}
    records, total = analyze_queries(Retriever(corpus, config_name), corpus, golden)

    compare = None
    if compare_with:
        other, _ = analyze_queries(Retriever(corpus, compare_with), corpus, golden)
        compare = (compare_with, aggregate_failure_types(other))

    report = build_report(config_name, dataset, records, total, corpus_by_id, n, compare)
    print(report)
    out = REPORTS_DIR / ("error_analysis.md" if dataset == DEFAULT_DATASET else f"error_analysis_{dataset}.md")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(f"\nWrote {out}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="baseline", choices=list(CONFIGS.keys()))
    parser.add_argument("--n", type=int, default=5, help="How many of the worst queries to show in detail.")
    parser.add_argument("--dataset", choices=DATASETS, default=DEFAULT_DATASET)
    parser.add_argument("--compare-with", choices=list(CONFIGS.keys()), default=None,
                        help="Also show this config's failure-type distribution side by side.")
    args = parser.parse_args()
    run(args.config, args.n, args.dataset, args.compare_with)


if __name__ == "__main__":
    main()
