# Error Analysis: 'baseline' configuration

Worst 5 queries by Recall@10 then Recall@5 (lowest first):

## Query ID: q003
Category: factual | Difficulty: easy | Recall@5: 0.00 | Recall@10: 0.00 | MRR: 0.00

Query:
In the Duarte Matter, what key facts were identified concerning consideration?

Expected relevant passage(s): p003
  (e.g. p003: "Internal Research Memorandum — Duarte Matter")

Retrieved results:
  1. p138 - Business Corporations Act § 10.372 — Board Independence Standards
  2. p151 - Calloway Holdings, Ltd. v. Silverpine Inc., the Superior Court of Meridian County (2020)
  3. p118 - Motion to Compel Discovery in Constance Ashworth v. Ingrid Ashworth, the Superior Court of Meridian County, Docket No. 40-CV-7658
  4. p026 - Internal Research Memorandum — Ferro Matter
  5. p070 - Intellectual Property Protection Act § 23.846 — Trademark Likelihood Of Confusion

Failure reason:
chunk boundary problem for p003: the document was split into 6 chunks, and the terms that would identify it (consideration, duarte, facts, identified, key) may be spread across chunks rather than concentrated in the single highest-scoring one.

---

## Query ID: q024
Category: multi_hop | Difficulty: hard | Recall@5: 0.50 | Recall@10: 0.50 | MRR: 0.50

Query:
How does the court's resolution of reasonable reliance in a Franklin State dispute relate to the statutory requirements for detrimental reliance under the Uniform Commercial Code?

Expected relevant passage(s): p018, p019
  (e.g. p018: "Marisol Nyugen v. Bellhaven LLC, the Court of Chancery of Verrant (2022)")

Retrieved results:
  1. p002 - Uniform Commercial Code § 2.195 — Consideration
  2. p019 - Uniform Commercial Code § 10.742 — Promissory Estoppel
  3. p007 - Uniform Commercial Code § 40.982 — The Parol Evidence Rule
  4. p058 - Fair Workplace Standards Act § 3.954 — Whistleblower Protection
  5. p051 - Internal Research Memorandum — Pemberton Matter

Failure reason:
ambiguous query / weak top-of-list separation for p019: the relevant document was retrieved, but only at rank 2 (within the top 5 but not ranked first), meaning at least one less-relevant chunk scored higher. multi-hop retrieval failure: only part of the required passage set was retrieved, which is enough to look successful on a single-passage check but fails a query that depends on both sources. chunk boundary problem for p018: the document was split into 8 chunks, and the terms that would identify it (a, court, detrimental, dispute, for) may be spread across chunks rather than concentrated in the single highest-scoring one.

---

## Query ID: q089
Category: procedural | Difficulty: hard | Recall@5: 0.00 | Recall@10: 1.00 | MRR: 0.17

Query:
What standard applies when a party raises custody determination in a motion to quash subpoena?

Expected relevant passage(s): p084
  (e.g. p084: "Motion to Quash Subpoena in Kiyoshi Odenkirk v. Grigor Bellrose, the Court of Chancery of Verrant, Docket No. 41-CV-2988")

Retrieved results:
  1. p031 - Motion to Quash Subpoena in Redgate LLC v. Kiyoshi Kowalczyk, the U.S. District Court for the Northern District of Calloway, Docket No. 93-CV-7118
  2. p099 - Motion to Quash Subpoena in Callum Fairweather v. Delphine Whitcombe, the Commercial Division, Harrow County Court, Docket No. 92-CV-8022
  3. p093 - Motion to Quash Subpoena in Redgate Holdings, Ltd. v. Marisol Alvear, the Appellate Division, Second Department, State of Ashford, Docket No. 84-CV-1320
  4. p144 - Motion to Quash Subpoena in Avery Nakashima v. Meridian Logistics, LLC, the U.S. District Court for the Northern District of Calloway, Docket No. 32-CV-8708
  5. p116 - Motion to Quash Subpoena in Bellhaven Logistics, LLC v. Wilhelmina Underdown, the Appellate Division, Second Department, State of Ashford, Docket No. 88-CV-7209

Failure reason:
ambiguous query / weak top-of-list separation for p084: the relevant document was retrieved, but only at rank 6 (outside the top 5), meaning at least one less-relevant chunk scored higher.

---

## Query ID: q082
Category: procedural | Difficulty: hard | Recall@5: 1.00 | Recall@10: 1.00 | MRR: 0.20

Query:
What standard applies when a party raises merger doctrine in a motion to compel arbitration?

Expected relevant passage(s): p076
  (e.g. p076: "Motion to Compel Arbitration in Ashwell Partners, Inc. v. Redgate Robotics, Inc., the Commercial Division, Harrow County Court, Docket No. 82-CV-5930")

Retrieved results:
  1. p074 - Ashwell Partners, Inc. v. Redgate Robotics, Inc., the Commercial Division, Harrow County Court (2017)
  2. p133 - Motion to Compel Arbitration in Lucienne Ferro v. Redgate Group, LLC, the Court of Chancery of Verrant, Docket No. 64-CV-6003
  3. p056 - Motion to Compel Arbitration in Ironvale LLC v. Wilhelmina Brightwater, the Court of Chancery of Verrant, Docket No. 21-CV-7939
  4. p077 - Internal Research Memorandum — Okafor Matter
  5. p076 - Motion to Compel Arbitration in Ashwell Partners, Inc. v. Redgate Robotics, Inc., the Commercial Division, Harrow County Court, Docket No. 82-CV-5930

Failure reason:
ambiguous query / weak top-of-list separation for p076: the relevant document was retrieved, but only at rank 5 (within the top 5 but not ranked first), meaning at least one less-relevant chunk scored higher.

---

## Query ID: q029
Category: procedural | Difficulty: hard | Recall@5: 1.00 | Recall@10: 1.00 | MRR: 0.25

Query:
What standard applies when a party raises exclusive control in a motion to compel arbitration?

Expected relevant passage(s): p025
  (e.g. p025: "Motion to Compel Arbitration in Kiyoshi Bellrose v. Priya Larkspur, the U.S. District Court for the Northern District of Calloway, Docket No. 57-CV-3646")

Retrieved results:
  1. p101 - Motion to Compel Arbitration in Ironvale Holdings, Ltd. v. Fenwick Ashworth, the Commercial Division, Harrow County Court, Docket No. 20-CV-8705
  2. p014 - Motion to Compel Arbitration in Selene Halloran v. Selene Underdown, the Commercial Division, Harrow County Court, Docket No. 98-CV-4598
  3. p056 - Motion to Compel Arbitration in Ironvale LLC v. Wilhelmina Brightwater, the Court of Chancery of Verrant, Docket No. 21-CV-7939
  4. p025 - Motion to Compel Arbitration in Kiyoshi Bellrose v. Priya Larkspur, the U.S. District Court for the Northern District of Calloway, Docket No. 57-CV-3646
  5. p005 - Motion to Compel Discovery in Redgate LLC v. Ashwell Logistics, LLC, the Superior Court of Meridian County, Docket No. 64-CV-6574

Failure reason:
ambiguous query / weak top-of-list separation for p025: the relevant document was retrieved, but only at rank 4 (within the top 5 but not ranked first), meaning at least one less-relevant chunk scored higher.

---
