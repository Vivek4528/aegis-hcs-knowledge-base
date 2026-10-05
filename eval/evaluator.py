"""
Evaluation harness — real metrics scored against eval/gold_answers.json.
Run: python eval/evaluator.py
Writes: output/eval_results.json

Correctness definition (v2):
  overall_correct = (
      status_correct                    # for gap/not_found questions
      AND key_fact_score >= 0.8         # for answered questions (80% of key facts present)
  )

Abstention split:
  - not_found: entity does not appear in any source
  - false_premise: question contains a false assumption
  - gap_missing_document: entity known but specific fact is absent from package
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search
from query.query_engine import EVALUATION_QUESTIONS

GOLD_PATH = os.path.join(os.path.dirname(__file__), "gold_answers.json")
FACT_THRESHOLD = 0.80   # must be present for an answerable question to count as correct

GAP_SUBTYPES = {
    "not_found":         "not_found",
    "gap":               "gap_missing_document",
    "gap_false_premise": "false_premise",
}


def load_gold() -> dict:
    with open(GOLD_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {g["question_id"]: g for g in data}


def score_one(result: dict, gold: dict) -> dict:
    predicted_status = result["status"]
    expected_status  = gold["expected_status"]
    answer_text      = (result.get("answer") or "").lower()
    evidence_sources = {e["source_file"] for e in result.get("evidence", [])}

    gap_types = {"gap", "gap_false_premise", "not_found"}

    # ── Status match ──────────────────────────────────────────────────────────
    if expected_status in gap_types:
        status_correct     = predicted_status in gap_types
        abstention_correct = status_correct
    else:
        status_correct     = (predicted_status == expected_status)
        abstention_correct = True   # n/a for answerable questions

    # ── Structured abstention comparison (Item 4) ─────────────────────────────
    # Compare structured fields (status, entity, missing predicate/unknown_id)
    if expected_status in gap_types:
        ent_match = True
        if gold.get("expected_entities"):
            rec_ents = result.get("recognized_entities", [])
            uid = result.get("unknown_id", "")
            res_ent = result.get("entity", "")
            ent_match = any(e in rec_ents or e == uid or e == res_ent for e in gold["expected_entities"])
        abstention_correct = status_correct and ent_match

    # ── Key fact match ────────────────────────────────────────────────────────
    if expected_status not in gap_types:
        key_facts  = gold.get("key_facts", [])
        facts_hit  = sum(1 for kf in key_facts if kf.lower() in answer_text)
        fact_score = facts_hit / len(key_facts) if key_facts else 1.0
        missing_facts = [kf for kf in key_facts if kf.lower() not in answer_text]
    else:
        # Abstentions: fact score is 1.0 if abstention was correctly structured
        key_facts = []
        facts_hit = 1 if abstention_correct else 0
        fact_score = 1.0 if abstention_correct else 0.0
        missing_facts = []

    # ── Citation precision / recall ───────────────────────────────────────────
    exp_sources = set(gold.get("expected_sources", []))
    if evidence_sources and exp_sources:
        precision = len(evidence_sources & exp_sources) / len(evidence_sources)
        recall    = len(evidence_sources & exp_sources) / len(exp_sources)
    elif not exp_sources:
        precision = recall = 1.0   # gap questions have no required sources
    else:
        precision = recall = 0.0

    # ── Overall correct ───────────────────────────────────────────────────────
    # Gap questions: correct iff structured abstention is correct
    # Answered questions: correct iff status correct AND fact_score >= 0.8 AND citation_recall > 0
    if expected_status in gap_types:
        overall_correct = abstention_correct
    else:
        has_source = (recall > 0) or (not exp_sources)
        overall_correct = status_correct and (fact_score >= FACT_THRESHOLD) and has_source

    # ── Abstention sub-type (3-way split) ────────────────────────────────────
    abstention_subtype = GAP_SUBTYPES.get(expected_status, "n/a")

    return {
        "q":                  gold.get("question_id", gold.get("id", 0)),
        "question":           gold["question"][:60] + "…",
        "expected_status":    expected_status,
        "predicted_status":   predicted_status,
        "status_correct":     status_correct,
        "fact_score":         round(fact_score, 2),
        "facts_hit":          facts_hit,
        "facts_total":        len(key_facts),
        "missing_facts":      missing_facts,
        "citation_precision": round(precision, 2),
        "citation_recall":    round(recall, 2),
        "has_source":         has_source if expected_status not in gap_types else True,
        "abstention_correct": abstention_correct,
        "abstention_subtype": abstention_subtype,
        "overall_correct":    overall_correct,
        "n_evidence":         len(result.get("evidence", [])),
        "recognized_entities": result.get("recognized_entities", []),
    }


def run_evaluation():
    kb = KnowledgeBase()
    kb.load()
    gold = load_gold()

    results = []
    answers = []
    for q_id, q_text in EVALUATION_QUESTIONS.items():
        r = search(q_text, kb)
        r["question_id"] = q_id
        r["question"]    = q_text
        answers.append(r)
        results.append(score_one(r, gold[q_id]))

    n = len(results)
    correct   = sum(1 for s in results if s["overall_correct"])
    status_ok = sum(1 for s in results if s["status_correct"])

    # ── Answerable metrics (n=18) ─────────────────────────────────────────────
    answ_qs = [s for s in results if s["expected_status"] == "answered"]
    n_answ  = len(answ_qs)
    answ_ok = sum(1 for s in answ_qs if s["overall_correct"])
    answ_fact = sum(s["fact_score"] for s in answ_qs) / n_answ if n_answ else 0.0
    answ_prec = sum(s["citation_precision"] for s in answ_qs) / n_answ if n_answ else 0.0
    answ_rec  = sum(s["citation_recall"] for s in answ_qs) / n_answ if n_answ else 0.0

    # ── All questions metrics (n=23) ──────────────────────────────────────────
    avg_facts = sum(s["fact_score"] for s in results) / n
    avg_prec  = sum(s["citation_precision"] for s in results) / n
    avg_rec   = sum(s["citation_recall"]    for s in results) / n

    # ── Abstention split by type ───────────────────────────────────────────────
    gap_types_all = {"gap", "gap_false_premise", "not_found"}
    abs_by_type: dict = {}
    for s in results:
        subtype = s["abstention_subtype"]
        if subtype == "n/a":
            continue
        bucket = abs_by_type.setdefault(subtype, {"correct": 0, "total": 0})
        bucket["total"] += 1
        if s["abstention_correct"]:
            bucket["correct"] += 1

    gap_qs = [s for s in results if s["expected_status"] in gap_types_all]
    gap_ok = sum(1 for s in gap_qs if s["abstention_correct"])

    abs_by_type_final = {}
    for k, v in abs_by_type.items():
        pct = round(v["correct"] / v["total"] * 100, 1) if v["total"] else 0
        abs_by_type_final[k] = {"correct": v["correct"], "total": v["total"], "pct": pct}

    metrics = {
        "total":                  n,
        "overall_correct":        correct,
        "overall_accuracy_pct":   round(correct / n * 100, 1),
        "status_correct":         status_ok,
        "status_accuracy_pct":    round(status_ok / n * 100, 1),
        "avg_fact_score":         round(avg_facts, 2),
        "avg_key_fact_score":     round(avg_facts, 2),
        "avg_citation_precision": round(avg_prec, 2),
        "avg_citation_recall":    round(avg_rec, 2),
        "fact_threshold":         FACT_THRESHOLD,
        "answerable_count":       n_answ,
        "answerable_correct":     answ_ok,
        "answerable_fact_score":  round(answ_fact, 3),
        "answerable_citation_prec": round(answ_prec, 3),
        "answerable_citation_rec":  round(answ_rec, 3),
        "abstention_all": {
            "correct": gap_ok,
            "total":   len(gap_qs),
            "pct":     round(gap_ok / len(gap_qs) * 100, 1) if gap_qs else 0,
        },
        "abstention_overall": {
            "correct": gap_ok,
            "total":   len(gap_qs),
            "pct":     round(gap_ok / len(gap_qs) * 100, 1) if gap_qs else 0,
        },
        "abstention_by_type":     abs_by_type_final,
        "answered_correct":       answ_ok,
        "answered_accuracy_pct":  round(answ_ok / len(answ_qs) * 100, 1) if answ_qs else 0,
        "per_question":           results,
    }

    os.makedirs("output", exist_ok=True)
    with open("output/eval_results.json", "w", encoding="utf-8") as f:
        json.dump({"metrics": metrics, "answers": answers}, f, indent=2, ensure_ascii=False)

    # ── Print report ──────────────────────────────────────────────────────────
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    SEP = "=" * 74
    print(SEP)
    print(f"AEGIS SERIES-7 HCS -- EVALUATION RESULTS  (fact threshold >= {FACT_THRESHOLD})")
    print(SEP)
    print(f"  Overall correct      : {correct}/{n}  ({metrics['overall_accuracy_pct']}%)")
    print(f"  Status accuracy      : {status_ok}/{n}  ({metrics['status_accuracy_pct']}%)")
    print(f"  Avg key-fact score   : {metrics['avg_key_fact_score']}")
    print(f"  Avg citation prec    : {metrics['avg_citation_precision']}")
    print(f"  Avg citation recall  : {metrics['avg_citation_recall']}")
    print()
    print(f"  Abstention (all gap) : {gap_ok}/{len(gap_qs)}")
    for subtype, v in abs_by_type_final.items():
        print(f"    {subtype:<30}: {v['correct']}/{v['total']}  ({v['pct']}%)")
    print()
    print(f"  Answerable (>=0.8 facts): {answ_ok}/{len(answ_qs)}  ({metrics['answered_accuracy_pct']}%)")
    print()
    print(f"  {'Q':>3}  {'Expected':<18} {'Got':<18} {'OK':>3} {'Facts':>5} {'Missing facts'}")
    print("  " + "-" * 74)
    for s in results:
        ok = "YES" if s["overall_correct"] else "NO "
        miss = ", ".join(f"'{f}'" for f in s["missing_facts"][:3]) if s["missing_facts"] else "-"
        print(f"  {s['q']:>3}  {s['expected_status']:<18} {s['predicted_status']:<18} "
              f"{ok} {s['fact_score']:>5.2f}  {miss}")
    print()
    print(f"  Results written to: output/eval_results.json")
    print(SEP)
    return metrics


if __name__ == "__main__":
    run_evaluation()
