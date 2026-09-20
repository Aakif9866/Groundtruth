# Error Analysis: 'baseline' configuration (synthetic dataset)

30 of 100 queries were imperfectly retrieved (Recall@5 < 1, Recall@10 < 1, or the first relevant passage not ranked first).

## Failure type summary

```
Failure Type                 Count   Percentage
-----------------------------------------------
semantic_mismatch               12          40%
chunk_boundary                   8          27%
ranking_failure                  6          20%
distractor_confusion             2           7%
multi_hop_failure                1           3%
generic_term_collision           1           3%
```

## Comparison with 'hybrid'

```
Failure Type                      baseline        hybrid   Change
-----------------------------------------------------------------
chunk_boundary                           8             6       -2
semantic_mismatch                       12             8       -4
distractor_confusion                     2             1       -1
multi_hop_failure                        1             0       -1
ranking_failure                          6             8       +2
generic_term_collision                   1             0       -1
```

## Worst 5 queries (lowest Recall@10, then Recall@5, then MRR)

## Query ID: q003
Category: factual | Difficulty: easy | Recall@5: 0.00 | Recall@10: 0.00 | MRR: 0.00

Query:
In the Duarte Matter, what key facts were identified concerning consideration?

Relevant passage IDs: p003
Relevant passage rank(s): p003: not in top 10
Retrieved passage IDs: p138, p151, p118, p026, p070, p122, p001, p126, p060, p156

Top retrieved:
  1. p138 - Business Corporations Act § 10.372 — Board Independence Standards
  2. p151 - Calloway Holdings, Ltd. v. Silverpine Inc., the Superior Court of Meridian County (2020)
  3. p118 - Motion to Compel Discovery in Constance Ashworth v. Ingrid Ashworth, the Superior Court of Meridian County, Docket No. 40-CV-7658
  4. p026 - Internal Research Memorandum — Ferro Matter
  5. p070 - Intellectual Property Protection Act § 23.846 — Trademark Likelihood Of Confusion

Diagnosis: chunk_boundary
Evidence: p003 was split into 6 chunks; its best single chunk contains 3 of the 6 query terms found anywhere in the document [consideration, duarte, facts, identified, key, matter], so matching terms are scattered across chunks.

---

## Query ID: q024
Category: multi_hop | Difficulty: hard | Recall@5: 0.50 | Recall@10: 0.50 | MRR: 0.50

Query:
How does the court's resolution of reasonable reliance in a Franklin State dispute relate to the statutory requirements for detrimental reliance under the Uniform Commercial Code?

Relevant passage IDs: p018, p019
Relevant passage rank(s): p018: not in top 10, p019: 2
Retrieved passage IDs: p002, p019, p007, p058, p051, p047, p049, p036, p001, p135

Top retrieved:
  1. p002 - Uniform Commercial Code § 2.195 — Consideration
  2. p019 - Uniform Commercial Code § 10.742 — Promissory Estoppel
  3. p007 - Uniform Commercial Code § 40.982 — The Parol Evidence Rule
  4. p058 - Fair Workplace Standards Act § 3.954 — Whistleblower Protection
  5. p051 - Internal Research Memorandum — Pemberton Matter

Diagnosis: multi_hop_failure
Evidence: needs 2 passages; retrieved 1 (p019), missing p018 from the top 10.

---

## Query ID: q089
Category: procedural | Difficulty: hard | Recall@5: 0.00 | Recall@10: 1.00 | MRR: 0.17

Query:
What standard applies when a party raises custody determination in a motion to quash subpoena?

Relevant passage IDs: p084
Relevant passage rank(s): p084: 6
Retrieved passage IDs: p031, p099, p093, p144, p116, p084, p158, p150, p085, p083

Top retrieved:
  1. p031 - Motion to Quash Subpoena in Redgate LLC v. Kiyoshi Kowalczyk, the U.S. District Court for the Northern District of Calloway, Docket No. 93-CV-7118
  2. p099 - Motion to Quash Subpoena in Callum Fairweather v. Delphine Whitcombe, the Commercial Division, Harrow County Court, Docket No. 92-CV-8022
  3. p093 - Motion to Quash Subpoena in Redgate Holdings, Ltd. v. Marisol Alvear, the Appellate Division, Second Department, State of Ashford, Docket No. 84-CV-1320
  4. p144 - Motion to Quash Subpoena in Avery Nakashima v. Meridian Logistics, LLC, the U.S. District Court for the Northern District of Calloway, Docket No. 32-CV-8708
  5. p116 - Motion to Quash Subpoena in Bellhaven Logistics, LLC v. Wilhelmina Underdown, the Appellate Division, Second Department, State of Ashford, Docket No. 88-CV-7209

Diagnosis: ranking_failure
Evidence: p084 was retrieved at rank 6 with 7/9 query terms present; no competing passage matched the query better lexically and no chunk or vocabulary signal explains the lower rank.

---

## Query ID: q082
Category: procedural | Difficulty: hard | Recall@5: 1.00 | Recall@10: 1.00 | MRR: 0.20

Query:
What standard applies when a party raises merger doctrine in a motion to compel arbitration?

Relevant passage IDs: p076
Relevant passage rank(s): p076: 5
Retrieved passage IDs: p074, p133, p056, p077, p076, p014, p101, p132, p075, p131

Top retrieved:
  1. p074 - Ashwell Partners, Inc. v. Redgate Robotics, Inc., the Commercial Division, Harrow County Court (2017)
  2. p133 - Motion to Compel Arbitration in Lucienne Ferro v. Redgate Group, LLC, the Court of Chancery of Verrant, Docket No. 64-CV-6003
  3. p056 - Motion to Compel Arbitration in Ironvale LLC v. Wilhelmina Brightwater, the Court of Chancery of Verrant, Docket No. 21-CV-7939
  4. p077 - Internal Research Memorandum — Okafor Matter
  5. p076 - Motion to Compel Arbitration in Ashwell Partners, Inc. v. Redgate Robotics, Inc., the Commercial Division, Harrow County Court, Docket No. 82-CV-5930

Diagnosis: semantic_mismatch
Evidence: BM25 alone ranks p076 at 4 (7/9 query terms present) but this config ranked it 5: the vocabulary matches, the embedding ranking did not follow.

---

## Query ID: q029
Category: procedural | Difficulty: hard | Recall@5: 1.00 | Recall@10: 1.00 | MRR: 0.25

Query:
What standard applies when a party raises exclusive control in a motion to compel arbitration?

Relevant passage IDs: p025
Relevant passage rank(s): p025: 4
Retrieved passage IDs: p101, p014, p056, p025, p005, p127, p133, p087, p076, p141

Top retrieved:
  1. p101 - Motion to Compel Arbitration in Ironvale Holdings, Ltd. v. Fenwick Ashworth, the Commercial Division, Harrow County Court, Docket No. 20-CV-8705
  2. p014 - Motion to Compel Arbitration in Selene Halloran v. Selene Underdown, the Commercial Division, Harrow County Court, Docket No. 98-CV-4598
  3. p056 - Motion to Compel Arbitration in Ironvale LLC v. Wilhelmina Brightwater, the Court of Chancery of Verrant, Docket No. 21-CV-7939
  4. p025 - Motion to Compel Arbitration in Kiyoshi Bellrose v. Priya Larkspur, the U.S. District Court for the Northern District of Calloway, Docket No. 57-CV-3646
  5. p005 - Motion to Compel Discovery in Redgate LLC v. Ashwell Logistics, LLC, the Superior Court of Meridian County, Docket No. 64-CV-6574

Diagnosis: ranking_failure
Evidence: p025 was retrieved at rank 4 with 7/9 query terms present; no competing passage matched the query better lexically and no chunk or vocabulary signal explains the lower rank.

---
