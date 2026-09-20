"""Builds the synthetic legal-style corpus and candidate golden evaluation set.

This is a template-based generator, not free-form LLM output: every document
is assembled from parameterized legal templates driven by a fixed random
seed, so the corpus and queries are fully reproducible and every
relevant_passage_ids label is correct by construction (the query is derived
from the same "cluster" of facts as the passage it targets).

Usage:
    python scripts/build_dataset.py

Produces:
    data/corpus.jsonl        - synthetic long-form legal documents
    data/golden_set.jsonl    - candidate query/relevance examples (review_status="pending")

Run scripts/validate_dataset.py afterwards to structurally validate the
candidate set, mark examples "reviewed", and write data/dataset_meta.json.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

SEED = 42
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# Name pools (all fictional)
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Avery", "Marlowe", "Dashiell", "Priya", "Tobias", "Selene", "Renata",
    "Grigor", "Wilhelmina", "Idris", "Constance", "Osei", "Fenwick", "Marisol",
    "Callum", "Anouk", "Baptiste", "Delphine", "Emeka", "Farrah", "Giacomo",
    "Hazel", "Ingrid", "Jarrah", "Kiyoshi", "Lucienne",
]
LAST_NAMES = [
    "Whitcombe", "Alvear", "Nakashima", "Odenkirk", "Fairweather", "Bellrose",
    "Kowalczyk", "Duarte", "Ashworth", "Okafor", "Vasilenko", "Pemberton",
    "Solheim", "Trevisan", "Underdown", "Castellanos", "Brightwater",
    "Halloran", "Nyugen", "Ferro", "Larkspur", "Moreau",
]
COMPANY_SUFFIXES = ["Inc.", "LLC", "Holdings, Ltd.", "Group, LLC", "Partners, Inc.", "Robotics, Inc.", "Logistics, LLC"]
COMPANY_STEMS = ["Meridian", "Northbridge", "Calloway", "Bellhaven", "Ashwell", "Ironvale", "Redgate", "Silverpine"]

COURTS = [
    "the Superior Court of Meridian County",
    "the Court of Appeals for the Ninth Circuit of Franklin State",
    "the Delmar County Circuit Court",
    "the Appellate Division, Second Department, State of Ashford",
    "the U.S. District Court for the Northern District of Calloway",
    "the Supreme Court of Westbridge",
    "the Commercial Division, Harrow County Court",
    "the Court of Chancery of Verrant",
]

JURISDICTIONS = ["Meridian", "Franklin State", "Ashford", "Calloway", "Westbridge", "Harrow County", "Verrant", "Bellhaven"]

MOTION_TYPES = [
    "Motion to Compel Arbitration", "Motion for Summary Judgment", "Motion to Dismiss",
    "Motion to Compel Discovery", "Motion for a Protective Order", "Motion in Limine",
    "Motion for Preliminary Injunction", "Motion to Quash Subpoena",
]

# ---------------------------------------------------------------------------
# Practice areas: each has a code name and a list of (doctrine, definition, terms)
# ---------------------------------------------------------------------------

PRACTICE_AREAS = {
    "contracts": {
        "code_name": "Uniform Commercial Code",
        "doctrines": [
            ("consideration", "consideration requires a bargained-for exchange of legal value between the parties", ["bargained-for exchange", "legal detriment", "mutual assent"]),
            ("unconscionability", "a contract or clause is unconscionable when it is so one-sided at formation that no reasonable party would accept it absent unequal bargaining power", ["procedural unconscionability", "substantive unconscionability", "unequal bargaining power"]),
            ("the parol evidence rule", "the parol evidence rule bars extrinsic evidence of prior or contemporaneous agreements that contradict a fully integrated written contract", ["integrated writing", "extrinsic evidence", "merger clause"]),
            ("anticipatory repudiation", "anticipatory repudiation occurs when a party clearly communicates, before performance is due, that it will not perform", ["clear and unequivocal repudiation", "prospective breach", "adequate assurance"]),
            ("liquidated damages clauses", "a liquidated damages clause is enforceable only if actual damages were difficult to estimate at formation and the amount is a reasonable forecast rather than a penalty", ["reasonable forecast", "penalty clause", "difficulty of estimation"]),
            ("the statute of frauds", "the statute of frauds requires certain categories of contracts, including those not performable within one year, to be evidenced by a signed writing", ["signed writing requirement", "one-year rule", "part performance exception"]),
            ("promissory estoppel", "promissory estoppel allows enforcement of a promise without consideration where the promisee reasonably and detrimentally relied on it", ["reasonable reliance", "detrimental reliance", "injustice absent enforcement"]),
        ],
    },
    "torts": {
        "code_name": "Civil Liability Code",
        "doctrines": [
            ("comparative negligence", "under comparative negligence, a plaintiff's recovery is reduced in proportion to their own share of fault", ["apportionment of fault", "pure comparative fault", "modified comparative fault"]),
            ("res ipsa loquitur", "res ipsa loquitur permits an inference of negligence where the injury is of a kind that ordinarily does not occur absent negligence and was within the defendant's exclusive control", ["exclusive control", "inference of negligence", "circumstantial proof"]),
            ("proximate cause", "proximate cause limits liability to harms that were a foreseeable result of the defendant's conduct", ["foreseeability", "superseding cause", "scope of the risk"]),
            ("premises liability", "a landowner owes invitees a duty to exercise reasonable care to discover and remedy unreasonably dangerous conditions", ["duty to invitees", "open and obvious doctrine", "constructive notice"]),
            ("products liability", "a manufacturer is strictly liable for a defective product that is unreasonably dangerous when it leaves the manufacturer's control", ["design defect", "manufacturing defect", "failure to warn"]),
            ("intentional infliction of emotional distress", "intentional infliction of emotional distress requires extreme and outrageous conduct intentionally or recklessly causing severe emotional harm", ["extreme and outrageous conduct", "severe emotional distress", "reckless disregard"]),
            ("vicarious liability", "an employer is vicariously liable for an employee's tortious acts committed within the scope of employment", ["scope of employment", "respondeat superior", "frolic and detour"]),
        ],
    },
    "employment": {
        "code_name": "Fair Workplace Standards Act",
        "doctrines": [
            ("at-will employment", "at-will employment permits either party to terminate the relationship at any time for any lawful reason, subject to statutory and public-policy exceptions", ["public policy exception", "implied covenant of good faith", "wrongful termination"]),
            ("retaliation claims", "a retaliation claim requires protected activity, an adverse employment action, and a causal connection between the two", ["protected activity", "adverse action", "causal nexus"]),
            ("wage and hour overtime rules", "non-exempt employees must receive overtime compensation for hours worked beyond the statutory threshold in a workweek", ["non-exempt classification", "overtime threshold", "workweek calculation"]),
            ("non-compete enforceability", "a non-compete covenant is enforceable only if reasonable in duration, geographic scope, and protects a legitimate business interest", ["reasonable duration", "geographic scope", "legitimate business interest"]),
            ("hostile work environment", "a hostile work environment claim requires conduct severe or pervasive enough to alter the conditions of employment", ["severe or pervasive conduct", "objective reasonableness", "totality of circumstances"]),
            ("independent contractor classification", "worker classification turns on the degree of control the hiring entity retains over the manner and means of the work", ["right to control test", "economic realities test", "misclassification"]),
            ("whistleblower protection", "whistleblower statutes protect employees who report a good-faith belief of unlawful conduct from retaliation", ["good-faith belief", "protected disclosure", "internal reporting channel"]),
        ],
    },
    "intellectual_property": {
        "code_name": "Intellectual Property Protection Act",
        "doctrines": [
            ("trade secret misappropriation", "trade secret misappropriation requires information that derives independent economic value from secrecy, reasonable measures to maintain that secrecy, and improper acquisition or use", ["reasonable secrecy measures", "improper means", "independent economic value"]),
            ("patent claim construction", "claim construction determines the scope of patent claims by their ordinary meaning to a person of ordinary skill in the art, informed by the specification and prosecution history", ["person of ordinary skill", "intrinsic evidence", "claim differentiation"]),
            ("copyright fair use", "fair use weighs the purpose and character of the use, the nature of the work, the amount used, and the effect on the market for the original", ["transformative use", "market harm factor", "amount and substantiality"]),
            ("trademark likelihood of confusion", "likelihood of confusion is assessed through factors including mark similarity, goods relatedness, and evidence of actual confusion", ["mark similarity", "channels of trade", "actual confusion evidence"]),
            ("patent inequitable conduct", "inequitable conduct requires a material misrepresentation or omission to the patent office made with specific intent to deceive", ["materiality", "intent to deceive", "duty of candor"]),
            ("software copyright abstraction-filtration", "the abstraction-filtration-comparison test separates protectable expression from unprotected ideas, methods, and merger elements in software", ["merger doctrine", "scenes a faire", "protectable expression"]),
            ("license scope disputes", "a licensee that exceeds the scope of a license may be liable for infringement rather than mere breach of contract", ["scope of grant", "field-of-use restriction", "sublicense limits"]),
        ],
    },
    "criminal_procedure": {
        "code_name": "Criminal Procedure Code",
        "doctrines": [
            ("fourth amendment search and seizure", "a search is reasonable under the Fourth Amendment if supported by a warrant based on probable cause or falls within a recognized exception", ["probable cause", "warrant exception", "exclusionary rule"]),
            ("Miranda custodial interrogation", "Miranda warnings are required before custodial interrogation reasonably likely to elicit an incriminating response", ["custody determination", "interrogation defined", "voluntary waiver"]),
            ("speedy trial rights", "speedy trial analysis balances the length of delay, the reason for delay, assertion of the right, and resulting prejudice", ["length of delay", "reason for delay", "prejudice to the accused"]),
            ("chain of custody for evidence", "admissibility of physical evidence requires a sufficient chain of custody establishing the item's integrity from seizure to trial", ["evidentiary integrity", "custodian testimony", "gap in custody"]),
            ("prosecutorial discovery obligations", "due process requires disclosure of material exculpatory evidence favorable to the accused", ["exculpatory evidence", "materiality standard", "impeachment evidence"]),
            ("double jeopardy", "double jeopardy bars a second prosecution for the same offense after acquittal, conviction, or certain mistrials", ["same offense test", "attachment of jeopardy", "mistrial exception"]),
            ("plea agreement enforceability", "a plea agreement is interpreted under contract principles but subject to due process protections for the defendant", ["knowing and voluntary plea", "prosecutorial breach", "specific performance remedy"]),
        ],
    },
    "evidence": {
        "code_name": "Uniform Rules of Evidence",
        "doctrines": [
            ("hearsay exceptions", "hearsay is inadmissible unless it falls within a recognized exception such as present sense impression or business records", ["present sense impression", "business records exception", "declarant unavailability"]),
            ("expert witness reliability", "expert testimony must rest on reliable methodology reasonably applied to the facts of the case", ["reliable methodology", "gatekeeping function", "fit to the facts"]),
            ("authentication of digital evidence", "digital evidence must be authenticated with evidence sufficient to support a finding that the item is what its proponent claims", ["metadata authentication", "chain of custody", "distinctive characteristics"]),
            ("attorney-client privilege scope", "the attorney-client privilege protects confidential communications made for the purpose of obtaining legal advice", ["confidentiality requirement", "waiver by disclosure", "crime-fraud exception"]),
            ("character evidence limits", "evidence of a person's character is generally inadmissible to prove action in conformity therewith, subject to enumerated exceptions", ["propensity evidence", "specific instances exception", "impeachment use"]),
            ("spoliation sanctions", "spoliation sanctions may issue when a party fails to preserve evidence it had a duty to retain, causing prejudice to the opposing party", ["duty to preserve", "bad faith destruction", "adverse inference instruction"]),
            ("judicial notice of adjudicative facts", "a court may take judicial notice of a fact not subject to reasonable dispute because it is generally known or readily verifiable", ["indisputable accuracy", "generally known fact", "readily verifiable source"]),
        ],
    },
    "corporate": {
        "code_name": "Business Corporations Act",
        "doctrines": [
            ("business judgment rule", "the business judgment rule presumes directors acted on an informed basis, in good faith, and in the honest belief the action served the company's best interests", ["informed decision-making", "good faith presumption", "rebuttal by waste"]),
            ("fiduciary duty of loyalty", "the duty of loyalty prohibits a director or officer from using corporate position for personal gain at the company's expense", ["self-dealing transaction", "corporate opportunity doctrine", "entire fairness review"]),
            ("piercing the corporate veil", "courts may pierce the corporate veil where the entity was used to perpetrate fraud or is a mere instrumentality of its owner", ["alter ego doctrine", "undercapitalization factor", "disregard of formalities"]),
            ("shareholder derivative standing", "a shareholder must show demand futility or wrongful refusal before pursuing a derivative claim on the corporation's behalf", ["demand futility", "special litigation committee", "contemporaneous ownership"]),
            ("appraisal rights in mergers", "dissenting shareholders may seek appraisal to receive fair value for shares in lieu of merger consideration", ["fair value determination", "dissenter's rights", "merger consideration"]),
            ("insider trading under Rule 10b-5", "insider trading liability requires a material nondisclosed fact, a duty to disclose or abstain, and trading while in possession of that information", ["material nonpublic information", "duty to disclose or abstain", "misappropriation theory"]),
            ("board independence standards", "a director is not independent if outside relationships would reasonably compromise objective judgment on the matter at issue", ["material relationship test", "conflicted transaction", "objective judgment"]),
        ],
    },
    "real_estate": {
        "code_name": "Property and Conveyancing Act",
        "doctrines": [
            ("adverse possession", "adverse possession requires possession that is actual, open, notorious, exclusive, and continuous for the statutory period", ["hostile possession", "statutory period", "color of title"]),
            ("easement by necessity", "an easement by necessity arises when a parcel is landlocked and the necessity existed at the time of a common ownership severance", ["landlocked parcel", "unity of title", "strict necessity"]),
            ("landlord habitability warranty", "the implied warranty of habitability requires residential premises to be fit for human habitation throughout the tenancy", ["fitness for habitation", "material defect", "constructive eviction"]),
            ("mortgage foreclosure procedure", "foreclosure requires strict compliance with statutory notice and sale procedures to be enforceable against the mortgagor", ["notice of default", "right to cure", "deficiency judgment"]),
            ("restrictive covenants running with the land", "a covenant runs with the land when it touches and concerns the land and the parties intended it to bind successors", ["touch and concern", "privity of estate", "notice to successors"]),
            ("eminent domain just compensation", "just compensation for a taking is measured by the fair market value of the property at the time of the taking", ["fair market value standard", "public use requirement", "partial taking severance damages"]),
            ("boundary line disputes and surveys", "boundary disputes are resolved by construing the original conveyance and reconciling it with monuments, courses, and distances", ["monuments control over courses", "ambiguous conveyance", "practical location doctrine"]),
        ],
    },
}

CATEGORY_QUERY_TARGET = 20  # per category, 5 categories -> ~100 total


def _name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _company(rng: random.Random) -> str:
    return f"{rng.choice(COMPANY_STEMS)} {rng.choice(COMPANY_SUFFIXES)}"


def _party(rng: random.Random) -> str:
    return _company(rng) if rng.random() < 0.5 else _name(rng)


def build_clusters(rng: random.Random):
    """One cluster per (practice_area, doctrine); deterministically decides
    which document types exist for that cluster."""
    clusters = []
    idx = 0
    for area, meta in PRACTICE_AREAS.items():
        for doctrine, definition, terms in meta["doctrines"]:
            clusters.append({
                "idx": idx,
                "area": area,
                "code_name": meta["code_name"],
                "doctrine": doctrine,
                "definition": definition,
                "terms": terms,
                "has_statute": idx % 2 == 0,
                "has_filing": idx % 3 != 0,
                "has_memo": idx % 3 != 1,
                "plaintiff": _party(rng),
                "defendant": _party(rng),
                "court": rng.choice(COURTS),
                "jurisdiction": rng.choice(JURISDICTIONS),
                "year": rng.randint(1998, 2024),
                "docket": f"{rng.randint(10,99)}-CV-{rng.randint(1000,9999)}",
                "section": f"{rng.randint(1,40)}.{rng.randint(100,999)}",
                "motion_type": rng.choice(MOTION_TYPES),
                "matter_name": f"{rng.choice(LAST_NAMES)} Matter",
                "amount": rng.randint(15, 950) * 1000,
                "date_str": f"{rng.choice(['January','March','April','June','August','October','November'])} {rng.randint(2,28)}, {rng.randint(2015,2024)}",
            })
            idx += 1
    return clusters


def case_name(c):
    return f"{c['plaintiff']} v. {c['defendant']}"


def make_opinion(c, pid):
    title = f"{case_name(c)}, {c['court']} ({c['year']})"
    text = (
        f"In {case_name(c)}, {c['court']} considered a dispute arising under the law of "
        f"{c['jurisdiction']}, Docket No. {c['docket']}. The plaintiff, {c['plaintiff']}, brought "
        f"suit against {c['defendant']} following a disagreement rooted in {c['area'].replace('_',' ')} "
        f"practice, specifically the application of {c['doctrine']}.\n\n"
        f"The record showed that the parties' relationship had proceeded without incident until "
        f"{c['date_str']}, when a disagreement emerged over the proper application of "
        f"{c['doctrine']}. {c['plaintiff']} argued that {c['definition']}, and that the undisputed "
        f"facts satisfied every element of that standard. {c['defendant']} responded that the "
        f"doctrine was inapplicable on these facts and that, in any event, the relevant factors of "
        f"{', '.join(c['terms'][:2])} counseled against liability.\n\n"
        f"The court began by restating the governing rule: {c['definition']}. Applying that rule, "
        f"the court examined each of {', '.join(c['terms'])} in turn. The court found the record "
        f"particularly informative on the question of {c['terms'][0]}, noting that the parties had "
        f"created a substantial documentary record bearing directly on this element.\n\n"
        f"Held: the court held that, on these facts, the doctrine of {c['doctrine']} applied and "
        f"resolved the matter in favor of {c['plaintiff']}. The court explained that {c['definition']}, "
        f"and that {c['plaintiff']} had satisfied that standard by a preponderance of the evidence. "
        f"The court's opinion in {case_name(c)} is now regularly cited within {c['jurisdiction']} for "
        f"its treatment of {c['doctrine']}."
    )
    return {"passage_id": pid, "doc_type": "opinion", "practice_area": c["area"], "title": title, "text": text}


def make_statute(c, pid):
    title = f"{c['code_name']} § {c['section']} — {c['doctrine'].title()}"
    text = (
        f"{c['code_name']} § {c['section']} governs {c['doctrine']} within the jurisdiction of "
        f"{c['jurisdiction']}. This section codifies the standard that {c['definition']}.\n\n"
        f"Requirements. A party invoking this section must establish each of the following elements: "
        f"(1) {c['terms'][0]}; (2) {c['terms'][1] if len(c['terms']) > 1 else c['terms'][0]}; and "
        f"(3) {c['terms'][2] if len(c['terms']) > 2 else c['terms'][0]}. Failure to establish any "
        f"element is grounds for denial of relief under this section.\n\n"
        f"Application. Courts applying § {c['section']} have construed it consistently with its "
        f"text, holding that {c['definition']} Courts in {c['jurisdiction']} have further clarified "
        f"that the section's elements are not satisfied by conclusory assertions alone and require "
        f"a developed factual record addressing {c['terms'][0]}.\n\n"
        f"Effective date and scope. This section applies to matters arising within {c['jurisdiction']} "
        f"and controls over any conflicting common-law rule predating its enactment."
    )
    return {"passage_id": pid, "doc_type": "statute", "practice_area": c["area"], "title": title, "text": text}


def make_filing(c, pid):
    title = f"{c['motion_type']} in {case_name(c)}, {c['court']}, Docket No. {c['docket']}"
    text = (
        f"{c['motion_type'].upper()}\n\n"
        f"{case_name(c)}\n{c['court']}\nDocket No. {c['docket']}\n\n"
        f"Movant respectfully submits this {c['motion_type']} in the above-captioned matter, which "
        f"concerns the application of {c['doctrine']} under {c['jurisdiction']} law.\n\n"
        f"Procedural History. This matter was initiated on {c['date_str']} following a dispute "
        f"between {c['plaintiff']} and {c['defendant']} concerning {c['doctrine']}. The parties "
        f"engaged in preliminary discovery before movant filed the instant motion.\n\n"
        f"Standard. A {c['motion_type']} concerning {c['doctrine']} requires the moving party to "
        f"demonstrate that {c['definition']} The court's inquiry on this type of motion focuses "
        f"specifically on {c['terms'][0]} and whether the existing record permits resolution without "
        f"further proceedings.\n\n"
        f"Relief Requested. For the foregoing reasons, movant respectfully requests that the "
        f"{c['court']} grant the {c['motion_type']} and enter an order consistent with the standard "
        f"governing {c['doctrine']}."
    )
    return {"passage_id": pid, "doc_type": "filing", "practice_area": c["area"], "title": title, "text": text}


def make_memo(c, pid):
    title = f"Internal Research Memorandum — {c['matter_name']}"
    text = (
        f"TO: Supervising Partner\nFROM: Associate\nRE: {c['matter_name']} — {c['doctrine'].title()} "
        f"Analysis\nDATE: {c['date_str']}\n\n"
        f"Background. Our client {c['plaintiff']} engaged the firm regarding a dispute with "
        f"{c['defendant']} valued at approximately ${c['amount']:,}. The matter implicates "
        f"{c['doctrine']} under {c['jurisdiction']} law. Correspondence produced to date indicates "
        f"the parties' relationship began to deteriorate around {c['date_str']}, when {c['defendant']} "
        f"took a position inconsistent with the parties' prior course of dealing.\n\n"
        f"Key Facts. Our review of the client's files identified the following facts bearing on "
        f"{c['terms'][0]}: the parties exchanged written communications referencing the disputed "
        f"terms, and {c['plaintiff']} took contemporaneous notes documenting {c['defendant']}'s "
        f"representations. No party has yet produced a complete accounting of damages.\n\n"
        f"Analysis. Under the doctrine of {c['doctrine']}, {c['definition']} Applying this standard "
        f"to the facts above, the client's position on {c['terms'][0]} appears well supported, though "
        f"further factual development regarding {c['terms'][1] if len(c['terms'])>1 else c['terms'][0]} "
        f"is recommended before finalizing our assessment.\n\n"
        f"Recommendation. We recommend proceeding with targeted discovery focused on {c['terms'][0]} "
        f"before advising the client on litigation strategy."
    )
    return {"passage_id": pid, "doc_type": "memo", "practice_area": c["area"], "title": title, "text": text}


def build_corpus(clusters):
    corpus = []
    pid_counter = 1
    for c in clusters:
        pid = f"p{pid_counter:03d}"
        c["opinion_id"] = pid
        corpus.append(make_opinion(c, pid))
        pid_counter += 1
        if c["has_statute"]:
            pid = f"p{pid_counter:03d}"
            c["statute_id"] = pid
            corpus.append(make_statute(c, pid))
            pid_counter += 1
        if c["has_filing"]:
            pid = f"p{pid_counter:03d}"
            c["filing_id"] = pid
            corpus.append(make_filing(c, pid))
            pid_counter += 1
        if c["has_memo"]:
            pid = f"p{pid_counter:03d}"
            c["memo_id"] = pid
            corpus.append(make_memo(c, pid))
            pid_counter += 1
    return corpus


DIFFICULTY_CYCLE = ["easy", "medium", "hard"]


def build_golden_set(clusters, rng: random.Random):
    examples = []
    qid_counter = 1

    def next_qid():
        nonlocal qid_counter
        q = f"q{qid_counter:03d}"
        qid_counter += 1
        return q

    def add(query, relevant_ids, category, difficulty):
        examples.append({
            "query_id": next_qid(),
            "query": query,
            "relevant_passage_ids": relevant_ids,
            "category": category,
            "difficulty": difficulty,
            "review_status": "pending",
        })

    counts = {"precedent": 0, "statute": 0, "procedural": 0, "factual": 0, "multi_hop": 0}

    def term(c, i):
        return c["terms"][i] if len(c["terms"]) > i else c["terms"][0]

    for i, c in enumerate(clusters):
        difficulty = DIFFICULTY_CYCLE[i % 3]
        hard = difficulty == "hard"

        if counts["precedent"] < CATEGORY_QUERY_TARGET:
            if hard:
                # Paraphrased: omits both the doctrine name and the case name,
                # forcing retrieval to rely on semantic/topical similarity
                # rather than a near-verbatim keyword match.
                query = (
                    f"A court in {c['jurisdiction']} had to decide a dispute turning on "
                    f"{term(c, 0)} and {term(c, 1)}. How was that dispute resolved?"
                )
            else:
                query = f"What did the court hold regarding {c['doctrine']} in {case_name(c)}?"
            add(query, [c["opinion_id"]], "precedent", difficulty)
            counts["precedent"] += 1

        if counts["statute"] < CATEGORY_QUERY_TARGET and c.get("statute_id"):
            if hard:
                query = (
                    f"Under {c['jurisdiction']} law, what provision addresses the requirements of "
                    f"{term(c, 0)} and {term(c, 1)}?"
                )
            else:
                query = f"Which statute governs {c['doctrine']} under {c['jurisdiction']} law, and what must a party establish?"
            add(query, [c["statute_id"]], "statute", difficulty)
            counts["statute"] += 1

        if counts["procedural"] < CATEGORY_QUERY_TARGET and c.get("filing_id"):
            if hard:
                query = (
                    f"What standard applies when a party raises {term(c, 0)} in a "
                    f"{c['motion_type'].lower()}?"
                )
            else:
                query = f"What standard applies to a {c['motion_type']} concerning {c['doctrine']} in {case_name(c)}?"
            add(query, [c["filing_id"]], "procedural", difficulty)
            counts["procedural"] += 1

        if counts["factual"] < CATEGORY_QUERY_TARGET and c.get("memo_id"):
            if hard:
                query = (
                    f"In a matter valued at roughly ${c['amount']:,}, what factual findings bore on "
                    f"{term(c, 0)}?"
                )
            else:
                query = f"In the {c['matter_name']}, what key facts were identified concerning {c['doctrine']}?"
            add(query, [c["memo_id"]], "factual", difficulty)
            counts["factual"] += 1

        if counts["multi_hop"] < CATEGORY_QUERY_TARGET and c.get("statute_id"):
            # Multi-hop is always hard: it requires retrieving two distinct
            # documents (opinion + statute) to fully answer.
            query = (
                f"How does the court's resolution of {term(c, 0)} in a {c['jurisdiction']} dispute "
                f"relate to the statutory requirements for {term(c, 1)} under the "
                f"{c['code_name']}?"
            )
            add(query, [c["opinion_id"], c["statute_id"]], "multi_hop", "hard")
            counts["multi_hop"] += 1

    return examples, counts


def main():
    rng = random.Random(SEED)
    clusters = build_clusters(rng)
    corpus = build_corpus(clusters)
    golden, counts = build_golden_set(clusters, rng)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "corpus.jsonl", "w") as f:
        for doc in corpus:
            f.write(json.dumps(doc) + "\n")
    with open(DATA_DIR / "golden_set.jsonl", "w") as f:
        for ex in golden:
            f.write(json.dumps(ex) + "\n")

    print(f"Wrote {len(corpus)} corpus documents to data/corpus.jsonl")
    print(f"Wrote {len(golden)} candidate golden examples to data/golden_set.jsonl")
    print(f"Category counts: {counts}")
    print("Next: run `python scripts/validate_dataset.py` to review and version the dataset.")


if __name__ == "__main__":
    main()
