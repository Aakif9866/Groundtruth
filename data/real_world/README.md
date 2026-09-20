# Real-World Benchmark (public-domain legal text)

A small, static benchmark built from **real** legal text, used to check that
retrieval behavior seen on the synthetic dataset is not purely an artifact of
templated documents.

## What it is

- 12 documents: 8 U.S. judicial opinions and 4 federal rules/statutes.
- 19 hand-written queries across `precedent`, `statute`, `procedural`,
  `factual`, and `multi_hop`, each labeled by hand against the text.
- Each document is a **verbatim excerpt** (not a full opinion), prefixed with
  a title/citation/source line. Only a short passage per case is included, so
  documents are much shorter than the synthetic ones.

## Licensing

U.S. judicial opinions and federal statutes/rules are works of the U.S.
government or judicial edicts and are **not subject to copyright**. Excerpts
were retrieved once on 2026-09-20 and checked in as a fixture; nothing is
downloaded at test, evaluation, or CI time.

| ID | Document | Source |
|---|---|---|
| rw001 | Marbury v. Madison, 5 U.S. (1 Cranch) 137 (1803) | law.cornell.edu/supremecourt/text/5/137 |
| rw002 | Miranda v. Arizona, 384 U.S. 436 (1966) | law.cornell.edu/supremecourt/text/384/436 |
| rw003 | Katz v. United States, 389 U.S. 347 (1967) | law.cornell.edu/supremecourt/text/389/347 |
| rw004 | International Shoe Co. v. Washington, 326 U.S. 310 (1945) | law.cornell.edu/supremecourt/text/326/310 |
| rw005 | MacPherson v. Buick Motor Co., 217 N.Y. 382 (1916) | en.wikisource.org (syllabus text, not the opinion body) |
| rw006 | Palsgraf v. Long Island Railroad Co., 248 N.Y. 339 (1928) | en.wikisource.org (opinion of the Court) |
| rw007 | Daubert v. Merrell Dow Pharmaceuticals, 509 U.S. 579 (1993) | law.cornell.edu/supct/html/92-102.ZS.html |
| rw008 | Gideon v. Wainwright, 372 U.S. 335 (1963) | law.cornell.edu/supremecourt/text/372/335 |
| rw009 | Fed. R. Evid. 702 (current text) | law.cornell.edu/rules/fre/rule_702 |
| rw010 | Fed. R. Civ. P. 12(b) (excerpt) | law.cornell.edu/rules/frcp/rule_12 |
| rw011 | 17 U.S.C. § 107 (excerpt) | law.cornell.edu/uscode/text/17/107 |
| rw012 | 9 U.S.C. § 2 | law.cornell.edu/uscode/text/9/2 |

Excerpts were obtained through a summarizing fetch tool that was asked for
verbatim quotes. They match the well-known wording of these passages, but
they have **not** been proofread character-by-character against the official
reporters. Treat them as faithful excerpts, not authoritative citations.

## How to use it (and how not to)

- **Synthetic** (`data/synthetic/`) is the deterministic regression benchmark;
  CI gates on it.
- **Real-world** (this directory) tests generalization. It is **never** used
  for the CI gate or the approved baseline.
- With 12 documents and 19 queries, differences between configurations here
  are usually within noise (see the bootstrap intervals from
  `python -m src.evaluation.compare --dataset real_world`). Its absolute
  numbers say nothing about real legal-retrieval performance.
- Two documents (rw009, rw010) carry several distinct queries, and several
  queries were written with knowledge of the text, so scores are optimistic.

## Rebuilding

`python scripts/build_real_world.py` regenerates the three JSON/JSONL files
from the excerpts embedded in that script. Changing an excerpt, query, or
label requires bumping `dataset_version` and adding a changelog entry below.

## Changelog

- `1.0.0` — initial 12-document, 19-query fixture.
