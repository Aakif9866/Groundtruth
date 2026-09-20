# Data

**This is a synthetic dataset.** `corpus.jsonl` is not composed of real
law-firm documents, filings, or opinions — it is a generated, fictional
legal-style corpus created specifically for retrieval-evaluation
engineering. No party names, case names, courts, or statutes are real. A
production version of this project would replace this dataset with a
human-reviewed set of actual (and appropriately access-controlled) firm
documents; this repository exists to demonstrate the *evaluation
methodology*, not to provide real legal data.

## Files

- `corpus.jsonl` — one synthetic legal document per line:
  `{passage_id, doc_type, practice_area, title, text}`. `doc_type` is one
  of `opinion`, `statute`, `filing`, `memo`.
- `golden_set.jsonl` — one evaluation example per line:
  `{query_id, query, relevant_passage_ids, category, difficulty, review_status}`.
  `category` is one of `precedent`, `statute`, `procedural`, `factual`,
  `multi_hop`.
- `dataset_meta.json` — dataset-level version and review metadata.

## How this dataset was built

1. `scripts/build_dataset.py` generates the corpus and a *candidate*
   golden set from parameterized templates (fixed random seed), grouped
   into "clusters" of one legal doctrine each. Every query is derived from
   the same cluster as its target passage(s), so relevance labels are
   correct by construction rather than hand-labeled after the fact.
2. `scripts/validate_dataset.py` runs structural checks (referenced
   passage IDs exist, no duplicate queries, category balance, minimum
   document length) and only then flips each example's `review_status`
   from `pending` to `reviewed`, and writes `dataset_meta.json`.

This two-step process stands in for a real human-review workflow. In a
production setting, step 2 would be an actual attorney/SME review, not an
automated structural check.

## Versioning rules

- The dataset is versioned (`dataset_version` in `dataset_meta.json`),
  currently `1.0.0`.
- **Never silently edit an existing example's `query`, `relevant_passage_ids`,
  `category`, or the referenced corpus document text.** If an example must
  change, bump `dataset_version` and record why in this file's changelog
  below (add one when the first change happens).
- Never modify the dataset merely to make a retrieval experiment pass.

## Changelog

- `1.0.0` — initial synthetic corpus (158 documents) and golden set (100
  queries, 20 per category).
