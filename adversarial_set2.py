"""
Adversarial Set 2 — 15 NEW questions (unseen during development).
Do NOT tune the system after seeing these results.
Run: python adversarial_set2.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search

kb = KnowledgeBase(); kb.load()

SET2 = [
    # Paraphrases / synonym
    ("B1",  "What is the normal working pressure of the HPU?",                          "answered", "200 bar"),
    ("B2",  "What alarm fires if hydraulic pressure drops below 150 bar?",              "answered", "A17"),
    # Typos / alternate punctuation
    ("B3",  "What does PS04A measure?",                                                 "answered", "PS-04A"),
    ("B4",  "tell me about ps 04 a sensor",                                             "answered", "PS-04A"),
    ("B5",  "what was the pressure before 3.2 on firmware 3.1.5?",                      "answered", "180 bar"),
    # Conflict probe
    ("B6",  "is the 175 bar field note correct?",                                       "answered", "unverified"),
    # Unknown components
    ("B7",  "what is TB-7?",                                                            "partial",  ""),
    ("B8",  "what is KA1?",                                                             "not_found",""),
    # Does ECN-1058 change setpoint?
    ("B9",  "does ECN-1058 change the setpoint?",                                       "answered", "unchanged"),
    # False premise (nonexistent alarm A99)
    ("B10", "what does alarm A99 indicate?",                                            "not_found",""),
    # False premise (no voltage sensor)
    ("B11", "what is the calibration interval of the voltage sensor?",                  "not_found",""),
    # Semantic paraphrase of Q11
    ("B12", "where is isolation valve IV-21 installed?",                                "answered", "Hydraulic Module"),
    # Version-scoped
    ("B13", "what pressure applies to units still on firmware 3.1?",                   "answered", "180 bar"),
    # Alias resolution
    ("B14", "what is the hydraulic power pack operating pressure?",                     "answered", "200 bar"),
    # Multi-hop: PS-04A signal + alarm
    ("B15", "what signal type does PS-04A use and what alarm is it associated with?",   "answered", "PS-04A"),
]

GAP = {"gap", "not_found", "gap_false_premise"}

def status_ok(got, exp):
    if exp in GAP: return got in GAP
    return got in ("answered", "partial") or got == exp

PASS, FAIL = 0, 0
rows = []
for code, query, exp_status, exp_sub in SET2:
    r = search(query, kb)
    got = r["status"]
    answer = (r.get("answer") or "").lower()
    s_ok = status_ok(got, exp_status)
    sub_ok = (not exp_sub) or (exp_sub.lower() in answer)
    ok = s_ok and sub_ok
    if ok: PASS += 1
    else:  FAIL += 1
    rows.append((code, query, exp_status, got, exp_sub, sub_ok, "[PASS]" if ok else "[FAIL]"))

print("=" * 78)
print("ADVERSARIAL SET 2 — 15 unseen questions (not tuned after seeing results)")
print("=" * 78)
print(f"{'ID':<4} {'Expected':<12} {'Got':<20} {'Sub':<12} Result")
print("-" * 78)
for code, q, exp, got, sub, sub_ok, tag in rows:
    sub_note = "OK" if sub_ok else f"MISS:{sub[:12]}"
    print(f"{code:<4} {exp:<12} {got:<20} {sub_note:<12} {tag}  {q[:50]}")
print()
print(f"PASS: {PASS}/15   FAIL: {FAIL}/15")
print("=" * 78)
