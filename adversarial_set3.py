"""
Adversarial Set 3 — 15 NEW questions (unseen, frozen after creation).
Includes:
- Unknown alarms A25 and A40
- Unknown components (PS-99, XV-99, J-99)
- ID typo 'PS 04 A'
- Question mixing PS-04 and PS-04A
- Version question on firmware 3.1.5
- 175 bar field note conflict question
- False-premise property queries
- Diagram entities KA1, TB-7
Run: python adversarial_set3.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search

kb = KnowledgeBase()
kb.load()

ADVERSARIAL_SET3 = [
    # 1. Unknown alarm A25
    ("C1",  "What does alarm A25 indicate?",                                                "not_found",         "cannot confirm"),
    # 2. Unknown alarm A40
    ("C2",  "What is the trigger threshold for alarm A40?",                                  "not_found",         "cannot confirm"),
    # 3. Unknown component PS-99
    ("C3",  "Where is pressure sensor PS-99 installed?",                                     "not_found",         "cannot confirm"),
    # 4. Unknown component XV-99
    ("C4",  "What is the function of shutoff valve XV-99?",                                  "not_found",         "not found"),
    # 5. Unknown terminal J-99
    ("C5",  "What connects to terminal pin J-99 on the HCS controller?",                     "not_found",         "cannot confirm"),
    # 6. ID typo 'PS 04 A'
    ("C6",  "What is the normal operating setpoint of PS 04 A?",                             "answered",          "200 bar"),
    # 7. Mixing PS-04 and PS-04A
    ("C7",  "Explain the difference between sensor PS-04 and sensor PS-04A",                 "answered",          "PS-04A"),
    # 8. Version question: firmware 3.1.5
    ("C8",  "What was the normal HPU pressure on firmware 3.1.5?",                           "answered",          "180 bar"),
    # 9. 175 bar conflict question
    ("C9",  "Is the 175 bar field note valid and verified for operational use?",             "answered",          "unverified"),
    # 10. False premise: reset time of A17
    ("C10", "What is the reset time of alarm A17 after pressure recovers?",                  "gap_false_premise", "not found for this entity"),
    # 11. False premise: max temperature of PS-04A
    ("C11", "What is the max temperature of PS-04A?",                                       "gap_false_premise", "not found for this entity"),
    # 12. KA1 diagram presence
    ("C12", "What is component KA1 and which diagram does it appear in?",                    "answered",          "AEG-DWG-E02"),
    # 13. TB-7 terminal block purpose
    ("C13", "What is the purpose of terminal block TB-7?",                                   "answered",          "transducer"),
    # 14. Unknown document ID
    ("C14", "What change was authorized by ECN-9999?",                                       "not_found",         "cannot confirm"),
    # 15. ECN-1058 correction of A17
    ("C15", "Which document corrected the A17 alarm text?",                                  "answered",          "ECN-1058"),
]

PASS_RAW, FAIL_RAW = 0, 0
PASS_STRUCT, FAIL_STRUCT = 0, 0
rows = []

# Expected structured targets for abstention items
EXPECTED_STRUCTURED = {
    "C1":  {"status": "not_found", "unknown_id": "A25"},
    "C2":  {"status": "not_found", "unknown_id": "A40"},
    "C3":  {"status": "not_found", "unknown_id": "PS-99"},
    "C4":  {"status": "not_found", "unknown_id": "XV-99"},
    "C5":  {"status": "not_found", "unknown_id": "J-99"},
    "C10": {"status": "gap_false_premise", "entity": "A17", "property": "reset time"},
    "C11": {"status": "gap_false_premise", "entity": "PS-04A", "property": "max temperature"},
    "C14": {"status": "not_found", "unknown_id": "ECN-9999"},
}

for code, query, exp_status, exp_substring in ADVERSARIAL_SET3:
    r = search(query, kb)
    got_status = r["status"]
    answer = (r.get("answer") or "").lower()

    gap = {"gap", "not_found", "gap_false_premise"}
    if exp_status in gap:
        status_ok = got_status in gap
    else:
        status_ok = (got_status == exp_status) or got_status in ("answered", "partial")

    # Raw substring score
    sub_ok = (not exp_substring) or (exp_substring.lower() in answer)
    raw_pass = status_ok and sub_ok
    if raw_pass:
        PASS_RAW += 1
    else:
        FAIL_RAW += 1

    # Corrected structured score (Item 4)
    if code in EXPECTED_STRUCTURED:
        target = EXPECTED_STRUCTURED[code]
        st_ok = (got_status == target["status"])
        if target["status"] == "not_found":
            uid_ok = (r.get("unknown_id") == target["unknown_id"])
            struct_pass = st_ok and uid_ok
        elif target["status"] == "gap_false_premise":
            ent_ok = (r.get("entity") == target["entity"])
            prop_ok = (r.get("property") == target["property"] or r.get("missing_predicate") == target["property"])
            struct_pass = st_ok and ent_ok and prop_ok
        else:
            struct_pass = st_ok
    else:
        struct_pass = raw_pass

    if struct_pass:
        PASS_STRUCT += 1
        res = "[PASS]"
    else:
        FAIL_STRUCT += 1
        res = "[FAIL]"

    sub_str = "OK" if sub_ok else f"MISS:{exp_substring}"
    rows.append((code, f"{exp_status}->{got_status}", sub_str, res, query[:55]))

print("=" * 82)
print("ADVERSARIAL SET 3 — HELD-OUT VALIDATION SET (written after fixes, optimistic)")
print("=" * 82)
print(f"{'ID':<4} {'Status->Predicted':<27} {'Sub':<10} {'Result':<8} {'Query'}")
print("-" * 82)
for code, sp, sub, res, q in rows:
    print(f"{code:<4} {sp:<27} {sub:<10} {res:<8} {q}")
print("-" * 82)
print(f"RAW SCORE (Substring matching)           : {PASS_RAW}/{len(ADVERSARIAL_SET3)} ({PASS_RAW/len(ADVERSARIAL_SET3)*100:.1f}%)")
print(f"CORRECTED SCORE (Structured abstentions) : {PASS_STRUCT}/{len(ADVERSARIAL_SET3)} ({PASS_STRUCT/len(ADVERSARIAL_SET3)*100:.1f}%)")
print("=" * 82)
