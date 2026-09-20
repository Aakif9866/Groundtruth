"""One constructed scenario per failure label. No embeddings are involved:
``classify_failure`` is fed hand-built retrieval results and a tiny corpus."""
import pytest

from src.evaluation import error_analysis as ea
from src.evaluation.error_analysis import (
    CorpusStats, FailureRecord, aggregate_failure_types, classify_failure, format_comparison_table, format_summary_table,
)
from src.retrieval.retriever import Retriever


def make(docs: dict[str, str], chunk_size: int = 10_000, pool=None):
    corpus = [{"passage_id": pid, "text": text, "title": pid} for pid, text in docs.items()]
    cfg = {"chunk_size": chunk_size, "chunk_overlap": 0, "method": "dense", "reranker": False, "candidate_pool": pool}
    return Retriever(corpus, "t", config=cfg), CorpusStats.from_corpus({d["passage_id"]: d for d in corpus})


def ex(query, relevant, category="procedural"):
    return {"query_id": "q1", "query": query, "relevant_passage_ids": relevant, "category": category}


FILLER = {"f1": "unrelated tax filing words", "f2": "another unrelated memo text", "f3": "third unrelated note here"}


def test_candidate_pool_limitation():
    r, stats = make({"d1": "alpha beta gamma", "d2": "delta epsilon zeta", **FILLER}, pool=1)
    d = classify_failure(ex("delta epsilon", ["d2"]), ["d1"], r, stats)
    assert d.failure_type == "candidate_pool_limitation"
    assert "only 1 chunks" in d.evidence


def test_multi_hop_failure():
    r, stats = make({"d1": "alpha beta gamma", "d2": "delta epsilon zeta", **FILLER})
    d = classify_failure(ex("alpha delta", ["d1", "d2"], "multi_hop"), ["d1", "f1"], r, stats)
    assert d.failure_type == "multi_hop_failure"
    assert "d2" in d.evidence and "retrieved 1" in d.evidence


def test_generic_term_collision():
    docs = {
        "R": "motion quash subpoena custody determination standard",
        "C1": "motion quash subpoena filing one", "C2": "motion quash subpoena filing two",
        "C3": "motion quash subpoena filing three", **FILLER,
    }
    r, stats = make(docs)
    d = classify_failure(ex("standard custody determination motion quash subpoena", ["R"]), ["C1", "C2", "C3", "R"], r, stats)
    assert d.failure_type == "generic_term_collision"
    assert "motion(df=4)" in d.evidence


def test_distractor_confusion():
    docs = {"R": "alpha beta gamma", "D": "alpha beta gamma delta", **FILLER}
    r, stats = make(docs)
    d = classify_failure(ex("alpha beta gamma", ["R"]), ["D", "R"], r, stats)
    assert d.failure_type == "distractor_confusion"


def test_chunk_boundary():
    text = "alpha beta " + "filler " * 40 + "gamma delta"
    r, stats = make({"R": text, **FILLER}, chunk_size=50)
    assert len([c for c in r.chunks if c.passage_id == "R"]) > 1
    d = classify_failure(ex("alpha beta gamma delta", ["R"], "factual"), ["f1"], r, stats)
    assert d.failure_type == "chunk_boundary"
    assert "scattered across chunks" in d.evidence


def test_semantic_mismatch_when_bm25_finds_it_but_result_did_not():
    r, stats = make({"R": "contract formation offer acceptance", **FILLER, "f4": "bakery recipe flour"})
    d = classify_failure(ex("offer acceptance formation", ["R"], "precedent"), ["f1"], r, stats)
    assert d.failure_type == "semantic_mismatch"
    assert "BM25 alone ranks R at 1" in d.evidence


def test_lexical_mismatch_when_vocabulary_differs():
    r, stats = make({"R": "wholly different vocabulary sentences", **FILLER})
    d = classify_failure(ex("offer acceptance formation", ["R"], "precedent"), ["f1"], r, stats)
    assert d.failure_type == "lexical_mismatch"
    assert "0/3" in d.evidence


def test_ranking_failure(monkeypatch):
    # BM25 rank is pinned to 3 so the semantic_mismatch rule (BM25 better than result) does not apply.
    monkeypatch.setattr(ea, "_passage_bm25_rank", lambda *a, **k: 3)
    r, stats = make({"R": "alpha beta gamma", "C": "alpha unrelated words", **FILLER})
    d = classify_failure(ex("alpha beta gamma", ["R"], "precedent"), ["C", "R"], r, stats)
    assert d.failure_type == "ranking_failure"
    assert "rank 2" in d.evidence


def test_unknown_when_no_rule_matches(monkeypatch):
    monkeypatch.setattr(ea, "_passage_bm25_rank", lambda *a, **k: 8)
    r, stats = make({"R": "alpha beta gamma", **FILLER})
    d = classify_failure(ex("alpha beta gamma", ["R"], "precedent"), ["f1"], r, stats)
    assert d.failure_type == "unknown"


def test_every_label_used_is_in_the_documented_taxonomy():
    assert set(ea.FAILURE_TYPES) == {
        "chunk_boundary", "lexical_mismatch", "semantic_mismatch", "distractor_confusion", "multi_hop_failure",
        "candidate_pool_limitation", "ranking_failure", "generic_term_collision", "unknown"}


def rec(t):
    return FailureRecord("q", "c", "easy", "x", 0, 0, 0, [], [], {}, t, "e")


def test_aggregate_counts_and_percentages():
    rows = aggregate_failure_types([rec("ranking_failure")] * 3 + [rec("chunk_boundary")])
    assert rows == [("ranking_failure", 3, 75.0), ("chunk_boundary", 1, 25.0)]
    assert aggregate_failure_types([]) == []


def test_tables_render_expected_rows():
    a = aggregate_failure_types([rec("ranking_failure")] * 2)
    b = aggregate_failure_types([rec("ranking_failure"), rec("chunk_boundary")])
    assert "ranking_failure" in format_summary_table(a) and "100%" in format_summary_table(a)
    table = format_comparison_table("base", a, "cand", b)
    assert "chunk_boundary" in table and "-1" in table and "+1" in table
