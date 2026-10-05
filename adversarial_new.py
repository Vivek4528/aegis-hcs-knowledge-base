"""
15 NEW adversarial questions — never used during development.
Do NOT tune the system after seeing these results.
Run: python adversarial_new.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search

kb = KnowledgeBase(); kb.load()

ADVERSARIAL = [
    # Paraphrases
    ("A1",  "What is the rated working pressure of the hydraulic power pack?",             "answered",      "200 bar"),
    ("A2",  "What triggers alarm A17?",                                                    "answered",      "150 bar"),
    # Typos / alternate punctuation
    ("A3",  "What does PS04A do?",                                                         "answered",      "PS-04A"),
    ("A4",  "tell me about ps 04 a",                                                       "answered",      "PS-04A"),
    ("A5",  "what was the pressure before 3.2 on firmware 3.1.5",                          "answered",      "180 bar"),
    # Conflict probe
    ("A6",  "is the 175 bar field note correct?",                                          "answered",      "unverified"),
    # Nonexistent components / alarms
    ("A7",  "what is TB-7?",                                                               "partial",       ""),
    ("A8",  "what is KA1?",                                                                "not_found",     ""),
    ("A9",  "what does alarm A99 indicate?",                                               "not_found",     ""),
    # Logical reasoning
    ("A10", "does ECN-1058 change the setpoint?",                                          "answered",      "setpoint unchanged"),
    ("A11", "what is the pressure threshold for the A17 alarm?",                           "answered",      "150 bar"),
    # False premise (nonexistent alarm)
    ("A12", "what is the reset time for alarm A17 after pressure normalises above 200 bar?","not_found",    ""),
    # Semantic paraphrase of Q4
    ("A13", "are PS-04 and PS-04A the same sensor?",                                       "answered",      "distinct"),
    # Doc provenance
    ("A14", "which document corrected the A17 alarm text?",                                "answered",      "ECN-1058"),
    # Multi-hop
    ("A15", "what component replaced PS-04 and what signal type does it use?",             "answered",      "PS-04A"),
]

PASS, FAIL = 0, 0
rows = []
for code, query, exp_status, exp_substring in ADVERSARIAL:
    r = search(query, kb)
    got_status = r["status"]
    answer = (r.get("answer") or "").lower()

    # Status check: gap/not_found are interchangeable
    gap = {"gap", "not_found", "gap_false_premise"}
    if exp_status in gap:
        status_ok = got_status in gap
    else:
        status_ok = (got_status == exp_status) or got_status in ("answered", "partial")

    # Substring check (only for answered expected)
    sub_ok = (not exp_substring) or (exp_substring.lower() in answer)

    overall = status_ok and sub_ok
    if overall: PASS += 1
    else:       FAIL += 1

    result_tag = "[PASS]" if overall else "[FAIL]"
    rows.append((code, query, exp_status, got_status, exp_substring, sub_ok, result_tag))

print("=" * 78)
print("15 NEW ADVERSARIAL QUESTIONS (unseen during development)")
print("=" * 78)
print("ID   Status->Predicted           Sub        Result")
print("-" * 78)
for code, q, exp, got, sub, sub_ok, tag in rows:
    sub_note = "OK" if sub_ok else f"MISS:{sub[:15]}"
    print(f"{code:<4} {exp:>10}->{got:<18} {sub_note:>12}  {tag}   {q[:55]}")

print()
print(f"PASS: {PASS}/15   FAIL: {FAIL}/15")
print("=" * 78)
