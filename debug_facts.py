import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search
from query.query_engine import EVALUATION_QUESTIONS
import json

kb = KnowledgeBase(); kb.load()

# Gold facts for investigation questions
GOLD = {
    2:  {"facts": ["200 bar", "3.2", "only", "180 bar", "conflict", "175 bar"],
         "q": EVALUATION_QUESTIONS[2]},
    7:  {"facts": ["10 seconds", "Shutdown Procedure 4.7", "IV-21", "pressure decay"],
         "q": EVALUATION_QUESTIONS[7]},
    8:  {"facts": ["50 bar", "above 50 bar", "not reset"],
         "q": EVALUATION_QUESTIONS[8]},
}

for qnum, data in GOLD.items():
    r = search(data["q"], kb)
    answer_lower = (r["answer"] or "").lower()
    print(f"\n{'='*70}")
    print(f"Q{qnum}: {data['q']}")
    print(f"Status : {r['status']}")
    print(f"Answer : {r['answer'][:400]}")
    print(f"\nFact check (threshold 0.8 means all 5+ facts needed):")
    for fact in data["facts"]:
        hit = fact.lower() in answer_lower
        print(f"  {'[HIT]' if hit else '[MISS]'} '{fact}'")
    hit_count = sum(1 for f in data["facts"] if f.lower() in answer_lower)
    print(f"\n  Score: {hit_count}/{len(data['facts'])} = {hit_count/len(data['facts']):.2f}")
    print(f"\nClaims used:")
    for c in r["claims_used"]:
        print(f"  [{c['claim_id']}] T{c['trust_tier']} {c['status']:12} {c['value'][:70]}")
