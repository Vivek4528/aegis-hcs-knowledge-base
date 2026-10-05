import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb.knowledge_base import KnowledgeBase
from query.entity_resolver import normalize, recognize_entities, recognize_predicates
from query.retrieval_engine import search

kb = KnowledgeBase(); kb.load()
queries = [
    "Who approved engineering bulletin ECN-1058?",
    "What was the pressure limit before revision 3.2?",
]
for q in queries:
    norm_q = normalize(q)
    ents = recognize_entities(norm_q)
    preds = recognize_predicates(norm_q)
    print(f"Q: {q}")
    print(f"  entities={ents}  predicates={preds}")
    r = search(q, kb)
    status = r["status"]
    print(f"  status={status}")
    for c in r["claims_used"][:4]:
        cid, scr, sta, val = c["claim_id"], c["score"], c["status"], c["value"][:65]
        print(f"  [{cid}] score={scr} status={sta:12} {val}")
    print()
