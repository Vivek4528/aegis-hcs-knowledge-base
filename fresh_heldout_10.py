"""
Fresh Held-Out Evaluation Set (10 genuinely new, unseen questions)
These questions test areas not covered by Dev Set (Q1-23), Set 1 (A1-15), Set 2 (B1-15), or Set 3 (C1-15).
Run once and reported without tuning.
"""
import io, sys, os
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search

kb = KnowledgeBase()
kb.load()

# 10 Fresh Questions:
# Q1: Specific technician who calibrated PS-04A (scanned appendix)
# Q2: Connector wired to IV-21 solenoid in wiring diagram (wiring diagram)
# Q3: Power supply voltage for PLC-03 controller (electrical schematic)
# Q4: Purpose of Auxiliary Reservoir on Line 4/5 (training slide excerpt)
# Q5: Does ECN-1058 change any alarm thresholds? (ECN-1058)
# Q6: Normal operating pressure in legacy manual v1 (legacy manual)
# Q7: Trigger pressure for unmodeled alarm A30 (in range A20-A34, not in AEG-AL-700 -> not_found)
# Q8: Baud rate of PLC-03 I/O Rack (false premise property -> gap_false_premise)
# Q9: Unknown component XV-22 (unknown ID -> not_found)
# Q10: Safety Data Sheet hydraulic fluid flash point (noise folder -> not_found / excluded)

FRESH_QUESTIONS = [
    {
        "id": "H01",
        "question": "Which technician performed the calibration on pressure sensor PS-04A?",
        "expected_status": "answered",
        "expected_facts": ["R. Okafor", "2026-01-09"],
    },
    {
        "id": "H02",
        "question": "Which connector pin is wired to the IV-21 solenoid in the instrumentation wiring diagram?",
        "expected_status": "answered",
        "expected_facts": ["J-15"],
    },
    {
        "id": "H03",
        "question": "What power supply voltage powers the PLC-03 controller according to the electrical schematic?",
        "expected_status": "answered",
        "expected_facts": ["24VDC", "PLC-03"],
    },
    {
        "id": "H04",
        "question": "What is the purpose of the Auxiliary Reservoir mentioned in the training slides?",
        "expected_status": "answered",
        "expected_facts": ["Auxiliary Reservoir", "Line 4/5", "peak demand"],
    },
    {
        "id": "H05",
        "question": "Does engineering bulletin ECN-1058 modify or supersede the pressure thresholds set in ECN-1042?",
        "expected_status": "answered",
        "expected_facts": ["does NOT supersede", "clarifies", "ECN-1042"],
    },
    {
        "id": "H06",
        "question": "What normal operating pressure is specified in the legacy manual v1?",
        "expected_status": "answered",
        "expected_facts": ["180 bar", "legacy"],
    },
    {
        "id": "H07",
        "question": "What is the low-pressure trigger threshold for alarm A30?",
        "expected_status": "not_found",
        "expected_facts": ["cannot confirm", "A30"],
    },
    {
        "id": "H08",
        "question": "What is the baud rate of the PLC-03 I/O Rack?",
        "expected_status": "gap_false_premise",
        "expected_facts": ["not found for this entity", "PLC-03"],
    },
    {
        "id": "H09",
        "question": "What is the operating state of isolation valve XV-22?",
        "expected_status": "not_found",
        "expected_facts": ["cannot confirm", "XV-22"],
    },
    {
        "id": "H10",
        "question": "What is the flash point of the hydraulic fluid in the safety data sheet?",
        "expected_status": "not_found",
        "expected_facts": ["cannot confirm"],
    },
]

print("=" * 80)
print("FRESH HELD-OUT TEST SUITE (10 UNSEEN QUESTIONS)")
print("=" * 80)

passed = 0
results = []

for q in FRESH_QUESTIONS:
    qid = q["id"]
    qtext = q["question"]
    exp_status = q["expected_status"]
    exp_facts = q["expected_facts"]
    
    res = search(qtext, kb)
    got_status = res.get("status")
    answer = (res.get("answer") or "").lower()
    
    # Check status match
    gap_types = {"gap", "gap_false_premise", "not_found"}
    if exp_status in gap_types:
        status_ok = got_status in gap_types
    else:
        status_ok = (got_status == exp_status)
        
    # Check key facts
    facts_hit = sum(1 for f in exp_facts if f.lower() in answer)
    fact_score = facts_hit / len(exp_facts) if exp_facts else 1.0
    
    overall_ok = status_ok and (fact_score >= 0.5)
    if overall_ok:
        passed += 1
        
    print(f"[{qid}] Status Exp: {exp_status:<17} Got: {got_status:<17} | Facts: {facts_hit}/{len(exp_facts)} | {'PASS' if overall_ok else 'FAIL'}")
    print(f"     Q: {qtext}")
    print(f"     Answer (first 120 chars): {res.get('answer', '')[:120].strip().replace(chr(10), ' ')}")
    if not overall_ok:
        print(f"     Missing facts: {[f for f in exp_facts if f.lower() not in answer]}")
    print()

print("=" * 80)
print(f"FRESH HELD-OUT SCORE: {passed}/{len(FRESH_QUESTIONS)} ({passed/len(FRESH_QUESTIONS)*100:.1f}%)")
print("=" * 80)
