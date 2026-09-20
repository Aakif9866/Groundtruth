"""Builds the small real-world (public-domain) benchmark under data/real_world/.

Every document is a verbatim excerpt of a U.S. judicial opinion or a federal
rule/statute. These are U.S. government works / judicial edicts and are not
subject to copyright. Excerpts were retrieved once (2026-09-20) from the
sources listed in SOURCES below and are stored as a static fixture, so tests
and CI never need network access.

Queries are hand-written against the real text. Relevance labels are set by
hand next to each query; nothing here is generated or guessed.

Usage:
    python scripts/build_real_world.py
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "real_world"
DATASET_VERSION = "1.0.0"
GENERATOR_VERSION = "1.0.0"
RETRIEVED_ON = "2026-09-20"

# passage_id, doc_type, practice_area, title, citation, source_url, verbatim excerpt(s)
DOCS = [
    ("rw001", "opinion", "constitutional_law", "Marbury v. Madison", "5 U.S. (1 Cranch) 137 (1803)",
     "https://www.law.cornell.edu/supremecourt/text/5/137",
     ["It is emphatically the province and duty of the judicial department to say what the law is. "
      "Those who apply the rule to particular cases, must of necessity expound and interpret that rule."]),
    ("rw002", "opinion", "criminal_procedure", "Miranda v. Arizona", "384 U.S. 436 (1966)",
     "https://www.law.cornell.edu/supremecourt/text/384/436",
     ["He must be warned prior to any questioning that he has the right to remain silent, that anything he says "
      "can be used against him in a court of law, that he has the right to the presence of an attorney, and that "
      "if he cannot afford an attorney one will be appointed for him prior to any questioning if he so desires."]),
    ("rw003", "opinion", "criminal_procedure", "Katz v. United States", "389 U.S. 347 (1967)",
     "https://www.law.cornell.edu/supremecourt/text/389/347",
     ["For the Fourth Amendment protects people, not places.",
      "But what he seeks to preserve as private, even in an area accessible to the public, may be constitutionally protected."]),
    ("rw004", "opinion", "civil_procedure", "International Shoe Co. v. Washington", "326 U.S. 310 (1945)",
     "https://www.law.cornell.edu/supremecourt/text/326/310",
     ["due process requires only that in order to subject a defendant to a judgment in personam, if he be not present "
      "within the territory of the forum, he have certain minimum contacts with it such that the maintenance of the "
      "suit does not offend 'traditional notions of fair play and substantial justice.'"]),
    ("rw005", "opinion", "torts", "MacPherson v. Buick Motor Co.", "217 N.Y. 382 (1916)",
     "https://en.wikisource.org/wiki/MacPherson_v._Buick_Motor_Co. (syllabus text)",
     ["If to the element of danger there is added knowledge that the thing will be used by persons other than the "
      "purchaser, and used without new tests, then, irrespective of contract, the manufacturer of this thing of danger "
      "is under a duty to make it carefully."]),
    ("rw006", "opinion", "torts", "Palsgraf v. Long Island Railroad Co.", "248 N.Y. 339 (1928)",
     "https://en.wikisource.org/wiki/Palsgraf_v._Long_Island_Railroad_Co./Opinion_of_the_Court",
     ["Plaintiff was standing on a platform of defendant's railroad after buying a ticket to go to Rockaway Beach. "
      "A train stopped at the station, bound for another place. Two men ran forward to catch it. One of the men reached "
      "the platform of the car without mishap, though the train was already moving. The other man, carrying a package, "
      "jumped aboard the car, but seemed unsteady as if about to fall. A guard on the car, who had held the door open, "
      "reached forward to help him in, and another guard on the platform pushed him from behind. In this act, the package "
      "was dislodged, and fell upon the rails. It was a package of small size, about fifteen inches long, and was covered "
      "by a newspaper. In fact it contained fireworks, but there was nothing in its appearance to give notice of its "
      "contents. The fireworks when they fell exploded. The shock of the explosion threw down some scales at the other end "
      "of the platform, many feet away. The scales struck the plaintiff, causing injuries for which she sues.",
      "The risk reasonably to be perceived defines the duty to be obeyed, and risk imports relation; it is risk to another "
      "or to others within the range of apprehension."]),
    ("rw007", "opinion", "evidence", "Daubert v. Merrell Dow Pharmaceuticals, Inc.", "509 U.S. 579 (1993)",
     "https://www.law.cornell.edu/supct/html/92-102.ZS.html",
     ["the trial judge, pursuant to Rule 104(a), must make a preliminary assessment of whether the testimony's underlying "
      "reasoning or methodology is scientifically valid",
      "whether the theory or technique in question can be (and has been) tested, whether it has been subjected to peer "
      "review and publication, its known or potential error rate, and the existence and maintenance of standards "
      "controlling its operation, and whether it has attracted widespread acceptance within a relevant scientific community"]),
    ("rw008", "opinion", "criminal_procedure", "Gideon v. Wainwright", "372 U.S. 335 (1963)",
     "https://www.law.cornell.edu/supremecourt/text/372/335",
     ["in our adversary system of criminal justice, any person haled into court, who is too poor to hire a lawyer, "
      "cannot be assured a fair trial unless counsel is provided for him."]),
    ("rw009", "statute", "evidence", "Federal Rule of Evidence 702", "Fed. R. Evid. 702 (current text)",
     "https://www.law.cornell.edu/rules/fre/rule_702",
     ["Rule 702. Testimony by Expert Witnesses. A witness who is qualified as an expert by knowledge, skill, experience, "
      "training, or education may testify in the form of an opinion or otherwise if the proponent demonstrates to the court "
      "that it is more likely than not that: (a) the expert's scientific, technical, or other specialized knowledge will help "
      "the trier of fact to understand the evidence or to determine a fact in issue; (b) the testimony is based on sufficient "
      "facts or data; (c) the testimony is the product of reliable principles and methods; and (d) the expert's opinion "
      "reflects a reliable application of the principles and methods to the facts of the case."]),
    ("rw010", "statute", "civil_procedure", "Federal Rule of Civil Procedure 12(b)", "Fed. R. Civ. P. 12(b) (excerpt)",
     "https://www.law.cornell.edu/rules/frcp/rule_12",
     ["Rule 12(b) permits parties to assert these defenses by motion: (1) lack of subject-matter jurisdiction; (2) lack of "
      "personal jurisdiction; (3) improper venue; (4) insufficient process; (5) insufficient service of process; (6) failure "
      "to state a claim upon which relief can be granted; and (7) failure to join a party under Rule 19.",
      "A motion asserting any of these defenses must be made before pleading if a responsive pleading is allowed."]),
    ("rw011", "statute", "intellectual_property", "17 U.S.C. § 107 (Fair Use)", "17 U.S.C. § 107 (excerpt)",
     "https://www.law.cornell.edu/uscode/text/17/107",
     ["Notwithstanding the provisions of sections 106 and 106A, the fair use of a copyrighted work...is not an infringement "
      "of copyright. The factors to be considered include: (1) the purpose and character of the use, including whether such "
      "use is of a commercial nature or is for nonprofit educational purposes; (2) the nature of the copyrighted work; (3) the "
      "amount and substantiality of the portion used in relation to the copyrighted work as a whole; and (4) the effect of the "
      "use upon the potential market for or value of the copyrighted work."]),
    ("rw012", "statute", "contracts", "9 U.S.C. § 2 (Federal Arbitration Act)", "9 U.S.C. § 2",
     "https://www.law.cornell.edu/uscode/text/9/2",
     ["A written provision in any maritime transaction or a contract evidencing a transaction involving commerce to settle "
      "by arbitration a controversy thereafter arising out of such contract or transaction, or the refusal to perform the "
      "whole or any part thereof, or an agreement in writing to submit to arbitration an existing controversy arising out of "
      "such a contract, transaction, or refusal, shall be valid, irrevocable, and enforceable, save upon such grounds as exist "
      "at law or in equity for the revocation of any contract or as otherwise provided in chapter 4."]),
]

# query, relevant ids, category, difficulty (hand-written against the text above)
QUERIES = [
    ("Which Supreme Court case said it is emphatically the province and duty of the judicial department to say what the law is?", ["rw001"], "precedent", "easy"),
    ("What warnings must be given to a suspect before custodial questioning?", ["rw002"], "precedent", "easy"),
    ("Does the Fourth Amendment protect places or people?", ["rw003"], "precedent", "easy"),
    ("What test decides whether a defendant outside the forum can be subjected to a judgment in personam?", ["rw004"], "precedent", "medium"),
    ("When is a manufacturer under a duty of care to someone who did not buy the product from it?", ["rw005"], "precedent", "medium"),
    ("How does the risk reasonably to be perceived relate to the duty a defendant owes?", ["rw006"], "precedent", "medium"),
    ("What must a trial judge assess before admitting scientific expert testimony?", ["rw007"], "precedent", "medium"),
    ("Is a poor criminal defendant assured a fair trial without a lawyer being provided?", ["rw008"], "precedent", "medium"),
    ("What must the proponent demonstrate to the court before an expert may give opinion testimony?", ["rw009"], "statute", "medium"),
    ("What are the four factors used to decide whether a use of a copyrighted work is fair?", ["rw011"], "statute", "easy"),
    ("Which federal statute makes written arbitration agreements valid and enforceable?", ["rw012"], "statute", "easy"),
    ("Which defenses may a party raise by motion, such as improper venue or insufficient service of process?", ["rw010"], "statute", "medium"),
    ("How does a defendant challenge a complaint for failure to state a claim before filing an answer?", ["rw010"], "procedural", "hard"),
    ("Must a motion asserting a lack of personal jurisdiction be made before pleading?", ["rw010"], "procedural", "hard"),
    ("What was inside the package that fell onto the railroad tracks?", ["rw006"], "factual", "easy"),
    ("How was the plaintiff injured while standing on the railroad platform?", ["rw006"], "factual", "medium"),
    ("How does the Supreme Court's gatekeeping standard for scientific testimony relate to the federal rule on expert witnesses?", ["rw007", "rw009"], "multi_hop", "hard"),
    ("Which decision and which federal rule together address when a court may reach a nonresident defendant and how to object to it?", ["rw004", "rw010"], "multi_hop", "hard"),
    ("Which decisions address what protections a person has when questioned in custody and when tried without money for a lawyer?", ["rw002", "rw008"], "multi_hop", "hard"),
]


def main() -> None:
    corpus = []
    for pid, doc_type, area, title, citation, url, excerpts in DOCS:
        body = "\n\n".join(excerpts)
        text = (
            f"{title}, {citation}.\n"
            f"Source: {url} (retrieved {RETRIEVED_ON}). Public-domain U.S. government/judicial work; excerpt is verbatim.\n\n"
            f"{body}"
        )
        corpus.append({"passage_id": pid, "doc_type": doc_type, "practice_area": area, "title": f"{title}, {citation}", "text": text})

    ids = {d["passage_id"] for d in corpus}
    golden = []
    for i, (query, rel, category, difficulty) in enumerate(QUERIES, start=1):
        assert all(r in ids for r in rel), f"unknown passage id in query {i}"
        golden.append({
            "query_id": f"rq{i:03d}", "query": query, "relevant_passage_ids": rel,
            "category": category, "difficulty": difficulty, "review_status": "reviewed",
        })
    assert len({g["query"] for g in golden}) == len(golden), "duplicate queries"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "corpus.jsonl").write_text("".join(json.dumps(d) + "\n" for d in corpus))
    (DATA_DIR / "golden_set.jsonl").write_text("".join(json.dumps(g) + "\n" for g in golden))
    meta = {
        "dataset_version": DATASET_VERSION,
        "generator_version": GENERATOR_VERSION,
        "seed": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "description": (
            "Small hand-curated benchmark of verbatim public-domain U.S. judicial opinion and federal "
            "rule/statute excerpts, used as a generalization smoke-check. Not statistically meaningful "
            "on its own; see README.md in this directory."
        ),
        "review_status": "reviewed",
        "document_count": len(corpus),
        "query_count": len(golden),
        "categories": dict(Counter(g["category"] for g in golden)),
        "difficulty_counts": dict(Counter(g["difficulty"] for g in golden)),
        "doc_type_counts": dict(Counter(d["doc_type"] for d in corpus)),
    }
    (DATA_DIR / "dataset_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Wrote {len(corpus)} documents and {len(golden)} queries to {DATA_DIR}")
    print(f"Categories: {meta['categories']}")


if __name__ == "__main__":
    main()
