"""
Knowledge Base — stores claims indexed for fast lookup.
Loaded from gold_claims.py; written to output/knowledge_base.json.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extract.gold_claims import CLAIMS, CONFLICTS, GAPS, get_claims_for_question


class KnowledgeBase:
    def __init__(self):
        self.claims = {}          # claim_id → claim dict
        self.by_subject = {}      # entity_id → [claim_ids]
        self.by_predicate = {}    # predicate → [claim_ids]
        self.by_question = {}     # q_num → [claim_ids]
        self.conflicts = CONFLICTS
        self.gaps = GAPS

    def load(self):
        for c in CLAIMS:
            cid = c["claim_id"]
            self.claims[cid] = c
            self.by_subject.setdefault(c["subject"], []).append(cid)
            self.by_predicate.setdefault(c["predicate"], []).append(cid)
        for q in range(1, 24):
            self.by_question[q] = get_claims_for_question(q)

    def get_claims_for_q(self, q_num: int) -> list:
        return [self.claims[cid] for cid in self.by_question.get(q_num, [])
                if cid in self.claims]

    def get_conflicts_for_q(self, q_num: int) -> list:
        relevant_claims = set(self.by_question.get(q_num, []))
        return [cf for cf in self.conflicts
                if any(cid in relevant_claims for cid in cf["claim_ids"])]

    def get_gaps_for_q(self, q_num: int) -> list:
        return [g for g in self.gaps if q_num in g.get("affects_questions", [])]

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {
            "claims": list(self.claims.values()),
            "conflicts": self.conflicts,
            "gaps": self.gaps,
            "question_map": {str(k): v for k, v in self.by_question.items()},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def stats(self) -> dict:
        status_counts = {}
        for c in self.claims.values():
            s = c["status"]
            status_counts[s] = status_counts.get(s, 0) + 1
        return {
            "total_claims": len(self.claims),
            "by_status": status_counts,
            "conflicts": len(self.conflicts),
            "gaps": len(self.gaps),
            "questions_covered": len(self.by_question),
        }


def build_kb(output_path: str) -> KnowledgeBase:
    kb = KnowledgeBase()
    kb.load()
    kb.save(output_path)
    return kb
