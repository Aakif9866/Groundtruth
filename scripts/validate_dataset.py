"""Programmatic review pass over the candidate golden set.

This stands in for human review in this synthetic-data project: it checks
structural correctness (every relevant_passage_ids entry actually exists,
no duplicate queries, sane category/difficulty balance, minimum content
length), and only then flips each example's review_status from "pending"
to "reviewed". A real deployment would replace this script with an actual
human review workflow before flipping that flag.

Usage:
    python scripts/validate_dataset.py

Exits non-zero and leaves review_status untouched if validation fails.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"
DATASET_VERSION = "1.1.0"
GENERATOR_VERSION = "1.1.0"
SEED = 42


def load_jsonl(path: Path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def validate(corpus, golden) -> list[str]:
    errors = []
    corpus_ids = {d["passage_id"] for d in corpus}

    if len(corpus_ids) != len(corpus):
        errors.append("Duplicate passage_id values found in corpus.jsonl")

    seen_queries = set()
    for ex in golden:
        for pid in ex["relevant_passage_ids"]:
            if pid not in corpus_ids:
                errors.append(f"{ex['query_id']}: relevant passage '{pid}' not found in corpus")
        if not ex["relevant_passage_ids"]:
            errors.append(f"{ex['query_id']}: has no relevant_passage_ids")
        if len(ex["query"]) < 15:
            errors.append(f"{ex['query_id']}: query text suspiciously short")
        if ex["query"] in seen_queries:
            errors.append(f"{ex['query_id']}: duplicate query text")
        seen_queries.add(ex["query"])
        if ex["category"] == "multi_hop" and len(ex["relevant_passage_ids"]) < 2:
            errors.append(f"{ex['query_id']}: multi_hop query should reference 2+ passages")

    for doc in corpus:
        if len(doc["text"]) < 200:
            errors.append(f"{doc['passage_id']}: document text suspiciously short ({len(doc['text'])} chars)")

    category_counts = Counter(ex["category"] for ex in golden)
    for cat, n in category_counts.items():
        if n < 10:
            errors.append(f"category '{cat}' has only {n} examples (expected >= 10)")

    return errors


def main():
    corpus = load_jsonl(DATA_DIR / "corpus.jsonl")
    golden = load_jsonl(DATA_DIR / "golden_set.jsonl")

    errors = validate(corpus, golden)
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} issue(s)):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    for ex in golden:
        ex["review_status"] = "reviewed"
    with open(DATA_DIR / "golden_set.jsonl", "w") as f:
        for ex in golden:
            f.write(json.dumps(ex) + "\n")

    category_counts = Counter(ex["category"] for ex in golden)
    difficulty_counts = Counter(ex["difficulty"] for ex in golden)
    doc_type_counts = Counter(d["doc_type"] for d in corpus)

    meta = {
        "dataset_version": DATASET_VERSION,
        "generator_version": GENERATOR_VERSION,
        "seed": SEED,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": (
            "Synthetic legal-style corpus and golden evaluation set for retrieval "
            "evaluation engineering. Not real law-firm documents; see README.md in this directory."
        ),
        "review_status": "reviewed",
        "document_count": len(corpus),
        "query_count": len(golden),
        "categories": dict(category_counts),
        "difficulty_counts": dict(difficulty_counts),
        "doc_type_counts": dict(doc_type_counts),
    }
    with open(DATA_DIR / "dataset_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Validation passed: {len(golden)} examples reviewed, dataset_version={DATASET_VERSION}")
    print(f"Category counts: {dict(category_counts)}")
    print("Wrote data/synthetic/dataset_meta.json")


if __name__ == "__main__":
    main()
