import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")
from kb.knowledge_base import KnowledgeBase
from query.entity_resolver import normalize, recognize_entities, recognize_predicates

kb = KnowledgeBase()
kb.load()

queries = {
    19: "What is the maximum continuous operating temperature of PS-04A?",
    21: "Who approved engineering bulletin ECN-1058?",
    22: "What is the mean time between failures for the isolation valve IV-21?",
}

W_ENTITY = 10; W_PRED = 6; W_TEXT = 1; MIN_SCORE = 2; TRUST_CUTOFF = 7

for qid, q in queries.items():
    norm_q = normalize(q)
    entities = recognize_entities(norm_q)
    predicates = recognize_predicates(norm_q)
    qwords = set(w for w in norm_q.split() if len(w) > 2)
    print(f"\nQ{qid}: {q[:60]}")
    print(f"  entities={entities}  predicates={predicates}")
    scored = []
    for cid, c in kb.claims.items():
        if c.get("trust_tier", 1) >= TRUST_CUTOFF: continue
        score = 0
        subj = c["subject"]
        if entities:
            if subj in entities: score += W_ENTITY
            elif any(subj.lower() in e.lower() or e.lower() in subj.lower() for e in entities): score += W_ENTITY // 2
        if predicates and c["predicate"] in predicates: score += W_PRED
        val_words = set(c.get("value","").lower().split())
        score += min(len(qwords & val_words), 5) * W_TEXT
        if c["status"] not in ("gap",): score += 2
        if c.get("is_observed"): score -= 3
        if score >= MIN_SCORE: scored.append((score, cid, c))
    scored.sort(reverse=True)
    for s, cid, c in scored[:6]:
        print(f"    score={s:3d}  status={c['status']:<12} subj={c['subject']:<12} {cid}  val={c['value'][:50]}")
