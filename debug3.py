import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search
from query.entity_resolver import normalize, recognize_entities, recognize_predicates

kb = KnowledgeBase(); kb.load()
q = "According to the component register, what is the location of the isolation valve IV-21?"
norm_q = normalize(q)
ents = recognize_entities(norm_q)
preds = recognize_predicates(norm_q)
print(f"entities={ents}  predicates={preds}")
r = search(q, kb)
print(f"status={r['status']}")
for c in r["claims_used"]:
    print(f"  [{c['claim_id']}] score={c['score']} status={c['status']:12} pred={c.get('predicate','?')[:25]} {c['value'][:60]}")
