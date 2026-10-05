"""
Ablation study — measures per-question accuracy drop, key-fact score, and citation recall when disabling:
  1. Alias resolution (entity_resolver recognizes nothing)
  2. Supersession / version scoping (all claims treated as active/same version)
  3. Trust ranking (all claims treated as T1)

Run: python ablation.py
"""
import sys, os, json, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search
from query.query_engine import EVALUATION_QUESTIONS
import query.entity_resolver as er_mod

kb = KnowledgeBase()
kb.load()

# Load gold answers for key-fact and citation recall computation
GOLD_PATH = os.path.join(os.path.dirname(__file__), "eval", "gold_answers.json")
with open(GOLD_PATH, encoding="utf-8") as f:
    GOLD = {g["question_id"]: g for g in json.load(f)}

GAP_TYPES = {"gap", "not_found", "gap_false_premise"}


def evaluate_run(run_results):
    """Compute status accuracy, avg key-fact score, and avg citation recall."""
    total_q = len(EVALUATION_QUESTIONS)
    status_hits = 0
    fact_scores = []
    recall_scores = []

    for q_id, r in run_results.items():
        g = GOLD[q_id]
        exp_status = g["expected_status"]
        got_status = r["status"]
        ans = (r.get("answer") or "").lower()
        ev_sources = {e["source_file"] for e in r.get("evidence", [])}

        # Status
        if exp_status in GAP_TYPES:
            st_ok = got_status in GAP_TYPES
        else:
            st_ok = (got_status == exp_status)
        if st_ok:
            status_hits += 1

        # Key facts & citation recall for answerable
        if exp_status not in GAP_TYPES:
            kfs = g.get("key_facts", [])
            f_hit = sum(1 for kf in kfs if kf.lower() in ans)
            fact_scores.append(f_hit / len(kfs) if kfs else 1.0)

            exp_src = set(g.get("expected_sources", []))
            if ev_sources and exp_src:
                rec = len(ev_sources & exp_src) / len(exp_src)
            elif not exp_src:
                rec = 1.0
            else:
                rec = 0.0
            recall_scores.append(rec)

    return {
        "status_acc": status_hits / total_q,
        "status_hits": status_hits,
        "total": total_q,
        "avg_fact": sum(fact_scores) / len(fact_scores) if fact_scores else 0.0,
        "avg_recall": sum(recall_scores) / len(recall_scores) if recall_scores else 0.0,
    }


# ── 1. Baseline ──────────────────────────────────────────────────────────────
baseline_results = {}
for q_id, q_text in EVALUATION_QUESTIONS.items():
    baseline_results[q_id] = search(q_text, kb)

# ── 2. Ablation 1: Alias resolution OFF ──────────────────────────────────────
orig_recognize = er_mod.recognize_entities
er_mod.recognize_entities = lambda q: []
no_alias_results = {}
for q_id, q_text in EVALUATION_QUESTIONS.items():
    no_alias_results[q_id] = search(q_text, kb)
er_mod.recognize_entities = orig_recognize

# ── 3. Ablation 2: Version scoping OFF ───────────────────────────────────────
orig_vs = {}
for cid, c in kb.claims.items():
    orig_vs[cid] = c.get("version_scope")
    c["version_scope"] = None
no_version_results = {}
for q_id, q_text in EVALUATION_QUESTIONS.items():
    no_version_results[q_id] = search(q_text, kb)
for cid, c in kb.claims.items():
    c["version_scope"] = orig_vs[cid]

# ── 4. Ablation 3: Trust ranking OFF (all T1) ────────────────────────────────
orig_tier = {}
for cid, c in kb.claims.items():
    orig_tier[cid] = c.get("trust_tier", 1)
    c["trust_tier"] = 1
no_trust_results = {}
for q_id, q_text in EVALUATION_QUESTIONS.items():
    no_trust_results[q_id] = search(q_text, kb)
for cid, c in kb.claims.items():
    c["trust_tier"] = orig_tier[cid]

# ── Metrics Table ────────────────────────────────────────────────────────────
m_base = evaluate_run(baseline_results)
m_alias = evaluate_run(no_alias_results)
m_ver = evaluate_run(no_version_results)
m_trust = evaluate_run(no_trust_results)

print("=" * 78)
print("ABLATION STUDY  (Full Metrics per Component Switch; n=23)")
print("=" * 78)
print(f"{'Configuration':<32} {'Status Acc':<14} {'Fact Score':<14} {'Citation Recall':<14}")
print("-" * 78)
print(f"{'Baseline (all components on)':<32} {m_base['status_hits']}/{m_base['total']} ({m_base['status_acc']*100:.1f}%)    {m_base['avg_fact']:.3f}          {m_base['avg_recall']:.3f}")
print(f"{'1. No alias resolution':<32} {m_alias['status_hits']}/{m_alias['total']} ({m_alias['status_acc']*100:.1f}%)    {m_alias['avg_fact']:.3f}          {m_alias['avg_recall']:.3f}")
print(f"{'2. No version scoping':<32} {m_ver['status_hits']}/{m_ver['total']} ({m_ver['status_acc']*100:.1f}%)    {m_ver['avg_fact']:.3f}          {m_ver['avg_recall']:.3f}")
print(f"{'3. No trust ranking':<32} {m_trust['status_hits']}/{m_trust['total']} ({m_trust['status_acc']*100:.1f}%)    {m_trust['avg_fact']:.3f}          {m_trust['avg_recall']:.3f}")
print("=" * 78)

# ── Before vs After Answer Diffs ─────────────────────────────────────────────
print("\n" + "=" * 78)
print("BEFORE AND AFTER ANSWER DIFFS PER SWITCH")
print("=" * 78)


def print_diff(title, q_num, base_res, ablated_res):
    print(f"\n--- {title} (Example: Q{q_num}) ---")
    b_ans = base_res[q_num].get("answer", "").strip().splitlines()
    a_ans = ablated_res[q_num].get("answer", "").strip().splitlines()
    diff = list(difflib.unified_diff(b_ans, a_ans, fromfile="Baseline", tofile="Ablated", lineterm=""))
    if diff:
        print("\n".join(diff[:15]))
    else:
        print("  [Identical text; status or evidence citation differs]")


print_diff("Switch 1: No Alias Resolution (Q1: 'hydraulic power pack')", 1, baseline_results, no_alias_results)
print_diff("Switch 2: No Version Scoping (Q9: 'legacy manual pressure')", 9, baseline_results, no_version_results)
print_diff("Switch 3: No Trust Ranking (Q1: 'unreviewed T6 note treated as T1')", 1, baseline_results, no_trust_results)
print("=" * 78)
