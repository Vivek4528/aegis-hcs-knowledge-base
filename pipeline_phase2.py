"""
Phase 2 pipeline — builds and validates the knowledge base.
Run: python pipeline_phase2.py
"""
import io, sys
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kb.knowledge_base import build_kb
from query.query_engine import answer_all, EVALUATION_QUESTIONS

KB_PATH = "output/knowledge_base.json"
ANSWERS_PATH = "output/all_answers.json"

def run():
    print("=" * 70)
    print("PHASE 2 — KNOWLEDGE BASE BUILD")
    print("=" * 70)

    # Build KB
    print("\n[1/3] Building knowledge base...")
    kb = build_kb(KB_PATH)
    stats = kb.stats()
    print(f"  Claims loaded   : {stats['total_claims']}")
    print(f"  By status       : {stats['by_status']}")
    print(f"  Conflicts       : {stats['conflicts']}")
    print(f"  Gaps            : {stats['gaps']}")
    print(f"  KB written to   : {KB_PATH}")

    # Answer all 23 questions
    print("\n[2/3] Answering all 23 evaluation questions...")
    answers = answer_all(kb)
    with open(ANSWERS_PATH, "w", encoding="utf-8") as f:
        json.dump(answers, f, indent=2, ensure_ascii=False)
    print(f"  Answers written to: {ANSWERS_PATH}")

    # Print summary table
    print("\n[3/3] Answer summary:")
    print(f"  {'Q':>3}  {'Type':<20} {'Conf':<8} {'Claims':>6}  Question (truncated)")
    print("  " + "-" * 80)
    for a in answers:
        q = a["question_id"]
        atype = a.get("answer_type", a.get("status", "unknown"))
        conf = a.get("confidence", "unknown")
        if isinstance(conf, dict):
            conf = conf.get("overall", "unknown")
        n_claims = len(a.get("claims", a.get("claims_used", [])))
        q_short = EVALUATION_QUESTIONS[q][:50]
        print(f"  {q:>3}  {atype:<20} {conf:<8} {n_claims:>6}  {q_short}")

    # Counts
    type_counts = {}
    for a in answers:
        t = a.get("answer_type", a.get("status", "unknown"))
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"\n  Answer type breakdown: {type_counts}")
    print(f"  Answered      : {type_counts.get('answered', 0)}/23")
    print(f"  Partial       : {type_counts.get('partial', 0)}/23")
    print(f"  Gap           : {type_counts.get('gap', 0)}/23")
    print(f"  Gap+FalsePrem : {type_counts.get('gap_false_premise', 0)}/23")

    print("\n" + "=" * 70)
    print("PHASE 2 COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    run()
