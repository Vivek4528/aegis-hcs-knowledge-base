"""Quick adversarial test - print live retrieval results for 8 new questions."""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search

kb = KnowledgeBase()
kb.load()

QUERIES = [
    ("What is PS-99?",                                   "not_found"),
    ("What does alarm A18 mean?",                        "answered"),
    ("What happens if pressure goes above 220 bar?",     "answered"),
    ("what does ps04a do",                               "answered"),
    ("What is the max pressure allowed for a controller reset?", "answered"),
    ("Which alarm indicates an invalid pressure sensor?","answered"),
    ("What signal type does PS-04A use?",                "answered"),
    ("Who is J. Torres?",                                "partial"),
]

SEP = "=" * 70
for q, expected in QUERIES:
    r = search(q, kb)
    status_match = "PASS" if r["status"] == expected else f"FAIL (expected {expected})"
    print(SEP)
    print(f"Q: {q}")
    print(f"Entities  : {r['recognized_entities']}")
    print(f"Predicates: {r['recognized_predicates']}")
    print(f"Status    : {r['status']}  [{status_match}]")
    print(f"Answer    : {r['answer'][:200]}")
    if r['claims_used']:
        for c in r['claims_used'][:2]:
            print(f"  Claim   : [{c['claim_id']}] score={c['score']} trust=T{c['trust_tier']} {c['value'][:80]}")
    print()
