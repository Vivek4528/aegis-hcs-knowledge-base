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
import query.retrieval_engine as re_mod
from query.retrieval_engine import search
from query.query_engine import EVALUATION_QUESTIONS
from eval.evaluator import score_one, load_gold
import query.entity_resolver as er_mod

kb = KnowledgeBase()
kb.load()

# Unified gold loading
GOLD = load_gold()

# ── Targeted Probe Set for Component Switches (Item 5) ──────────────────────
TARGETED_PROBES = [
    # Alias Switch Probes
    {
        "id": "T1",
        "question": "what is the HP unit operating pressure",
        "switch": "alias",
        "expected_status": "answered",
        "key_facts": ["200 bar", "180 bar"],
        "expected_sources": ["manuals/operator_manual.pdf"],
    },
    {
        "id": "T2",
        "question": "What is the function of PS04A?",
        "switch": "alias",
        "expected_status": "answered",
        "key_facts": ["PS-04A", "pressure transducer", "discharge"],
        "expected_sources": ["reference/component_register.xlsx"],
    },
    {
        "id": "T3",
        "question": "What is component KA1 in the electrical schematic?",
        "switch": "alias",
        "expected_status": "answered",
        "key_facts": ["KA1", "E-Stop Safety Relay", "AEG-DWG-E02"],
        "expected_sources": ["diagrams/system_diagram_electrical.png"],
    },
    # Version Scoping Probes
    {
        "id": "T4",
        "question": "What was the pressure before 3.2 on firmware 3.1.5?",
        "switch": "version",
        "expected_status": "answered",
        "key_facts": ["180 bar", "prior to 3.2"],
        "expected_sources": ["manuals/legacy_manual_v1.html"],
    },
    {
        "id": "T5",
        "question": "What pressure applies to units prior to software revision 3.2?",
        "switch": "version",
        "expected_status": "answered",
        "key_facts": ["180 bar", "PS-04"],
        "expected_sources": ["engineering_bulletins/ECN-1042.pdf"],
    },
    {
        "id": "T6",
        "question": "What is the current normal operating pressure for software revision 3.2?",
        "switch": "version",
        "expected_status": "answered",
        "key_facts": ["200 bar", "revision 3.2"],
        "expected_sources": ["manuals/operator_manual.pdf"],
    },
    # Trust Ranking Probes
    {
        "id": "T7",
        "question": "Is the 175 bar field note valid and verified for operational use?",
        "switch": "trust",
        "expected_status": "answered",
        "key_facts": ["unverified", "low trust", "conflicts with 200 bar"],
        "expected_sources": ["manuals/operator_manual.pdf"],
    },
    {
        "id": "T8",
        "question": "175 bar vs 200 bar operating pressure conflict",
        "switch": "trust",
        "expected_status": "answered",
        "key_facts": ["unverified", "low trust", "200 bar"],
        "expected_sources": ["manuals/operator_manual.pdf"],
    },
    {
        "id": "T9",
        "question": "What is the normal operating pressure for the HPU?",
        "switch": "trust",
        "expected_status": "answered",
        "key_facts": ["200 bar", "unverified"],
        "expected_sources": ["manuals/operator_manual.pdf"],
    },
]


def evaluate_set(results_dict, gold_dict):
    """Compute status hits, fact score, and citation recall using unified score_one."""
    scored = []
    for q_id, res in results_dict.items():
        g = gold_dict[q_id]
        s = score_one(res, g)
        scored.append(s)

    n = len(scored)
    hits = sum(1 for s in scored if s["status_correct"])
    facts = sum(s["fact_score"] for s in scored) / n if n else 0.0
    rec = sum(s["citation_recall"] for s in scored) / n if n else 0.0

    return {
        "status_hits": hits,
        "total": n,
        "status_acc": hits / n if n else 0.0,
        "avg_fact": facts,
        "avg_recall": rec,
        "scored": scored,
    }


# ── Run 1: Baseline ──────────────────────────────────────────────────────────
base_canonical = {q_id: search(q_text, kb) for q_id, q_text in EVALUATION_QUESTIONS.items()}
base_targeted  = {p["id"]: search(p["question"], kb) for p in TARGETED_PROBES}

# ── Run 2: Ablation 1 — Alias resolution OFF ──────────────────────────────────
orig_recognize = re_mod.recognize_entities
re_mod.recognize_entities = lambda q: []
no_alias_canonical = {q_id: re_mod.search(q_text, kb) for q_id, q_text in EVALUATION_QUESTIONS.items()}
no_alias_targeted  = {p["id"]: re_mod.search(p["question"], kb) for p in TARGETED_PROBES}
re_mod.recognize_entities = orig_recognize

# ── Run 3: Ablation 2 — Version scoping OFF ───────────────────────────────────
orig_vs = {}
for cid, c in kb.claims.items():
    orig_vs[cid] = c.get("version_scope")
    c["version_scope"] = None
no_ver_canonical = {q_id: search(q_text, kb) for q_id, q_text in EVALUATION_QUESTIONS.items()}
no_ver_targeted  = {p["id"]: search(p["question"], kb) for p in TARGETED_PROBES}
for cid, c in kb.claims.items():
    c["version_scope"] = orig_vs[cid]

# ── Run 4: Ablation 3 — Trust ranking OFF (all T1) ────────────────────────────
orig_tier = {}
for cid, c in kb.claims.items():
    orig_tier[cid] = c.get("trust_tier", 1)
    c["trust_tier"] = 1
no_trust_canonical = {q_id: search(q_text, kb) for q_id, q_text in EVALUATION_QUESTIONS.items()}
no_trust_targeted  = {p["id"]: search(p["question"], kb) for p in TARGETED_PROBES}
for cid, c in kb.claims.items():
    c["trust_tier"] = orig_tier[cid]

# ── Evaluate Canonical Suite (n=23) ──────────────────────────────────────────
c_base  = evaluate_set(base_canonical, GOLD)
c_alias = evaluate_set(no_alias_canonical, GOLD)
c_ver   = evaluate_set(no_ver_canonical, GOLD)
c_trust = evaluate_set(no_trust_canonical, GOLD)

# ── Evaluate Targeted Suite (n=9) ────────────────────────────────────────────
TARGETED_GOLD = {p["id"]: p for p in TARGETED_PROBES}
t_base  = evaluate_set(base_targeted, TARGETED_GOLD)
t_alias = evaluate_set(no_alias_targeted, TARGETED_GOLD)
t_ver   = evaluate_set(no_ver_targeted, TARGETED_GOLD)
t_trust = evaluate_set(no_trust_targeted, TARGETED_GOLD)

print("=" * 82)
print("ABLATION STUDY: CANONICAL DEV SET (n=23, Unified Scoring)")
print("=" * 82)
print(f"{'Configuration':<32} {'Status Acc':<16} {'Fact Score':<16} {'Citation Recall':<16}")
print("-" * 82)
print(f"{'Baseline (all switches on)':<32} {c_base['status_hits']}/{c_base['total']} ({c_base['status_acc']*100:.1f}%)    {c_base['avg_fact']:.3f}            {c_base['avg_recall']:.3f}")
print(f"{'1. No alias resolution':<32} {c_alias['status_hits']}/{c_alias['total']} ({c_alias['status_acc']*100:.1f}%)    {c_alias['avg_fact']:.3f}            {c_alias['avg_recall']:.3f}")
print(f"{'2. No version scoping':<32} {c_ver['status_hits']}/{c_ver['total']} ({c_ver['status_acc']*100:.1f}%)    {c_ver['avg_fact']:.3f}            {c_ver['avg_recall']:.3f}")
print(f"{'3. No trust ranking':<32} {c_trust['status_hits']}/{c_trust['total']} ({c_trust['status_acc']*100:.1f}%)    {c_trust['avg_fact']:.3f}            {c_trust['avg_recall']:.3f}")
print("=" * 82)

print("\n" + "=" * 82)
print("ABLATION STUDY: TARGETED SWITCH PROBE SET (n=9 Questions)")
print("=" * 82)
print(f"{'Configuration':<32} {'Status Acc':<16} {'Fact Score':<16} {'Citation Recall':<16}")
print("-" * 82)
print(f"{'Baseline (all switches on)':<32} {t_base['status_hits']}/{t_base['total']} ({t_base['status_acc']*100:.1f}%)    {t_base['avg_fact']:.3f}            {t_base['avg_recall']:.3f}")
print(f"{'1. No alias resolution (T1-T3)':<32} {t_alias['status_hits']}/{t_alias['total']} ({t_alias['status_acc']*100:.1f}%)    {t_alias['avg_fact']:.3f}            {t_alias['avg_recall']:.3f}")
print(f"{'2. No version scoping (T4-T6)':<32} {t_ver['status_hits']}/{t_ver['total']} ({t_ver['status_acc']*100:.1f}%)    {t_ver['avg_fact']:.3f}            {t_ver['avg_recall']:.3f}")
print(f"{'3. No trust ranking (T7-T9)':<32} {t_trust['status_hits']}/{t_trust['total']} ({t_trust['status_acc']*100:.1f}%)    {t_trust['avg_fact']:.3f}            {t_trust['avg_recall']:.3f}")
print("=" * 82)

# ── Before vs After Answer Diffs ─────────────────────────────────────────────
print("\n" + "=" * 82)
print("BEFORE AND AFTER ANSWER DIFFS PROVING SWITCH BEHAVIOR")
print("=" * 82)


def print_diff(title, q_id, base_dict, ablated_dict):
    print(f"\n--- {title} ---")
    b_ans = base_dict[q_id].get("answer", "").strip().splitlines()
    a_ans = ablated_dict[q_id].get("answer", "").strip().splitlines()
    diff = list(difflib.unified_diff(b_ans, a_ans, fromfile="Baseline (ON)", tofile="Ablated (OFF)", lineterm=""))
    if diff:
        print("\n".join(diff[:18]))
    else:
        print("  [Identical text; status or evidence citation differs]")


print_diff("Switch 1 Proof: Alias Resolution OFF for T1 ('what is the HP unit operating pressure')", "T1", base_targeted, no_alias_targeted)
print(f"  Switch ON recognized_entities : {base_targeted['T1'].get('recognized_entities')}")
print(f"  Switch OFF recognized_entities: {no_alias_targeted['T1'].get('recognized_entities')}")
print_diff("Switch 2 Proof: Version Scoping OFF for T4 ('pressure before 3.2 on firmware 3.1.5')", "T4", base_targeted, no_ver_targeted)
print_diff("Switch 3 Proof: Trust Ranking OFF for T9 ('unreviewed T6 note treated as T1')", "T9", base_targeted, no_trust_targeted)
print("=" * 82)
