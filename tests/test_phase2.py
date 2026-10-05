"""Phase 2 tests — KB load, provenance, and coverage via retrieval engine."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search
from query.query_engine import EVALUATION_QUESTIONS, answer_all

KB = KnowledgeBase()
KB.load()

GAP_TYPES = {"gap", "gap_false_premise", "not_found"}


def _search(q_id):
    return search(EVALUATION_QUESTIONS[q_id], KB)


class TestKBLoad(unittest.TestCase):

    def test_claim_count(self):
        """KB must have at least 30 claims."""
        self.assertGreaterEqual(len(KB.claims), 30)

    def test_conflict_count(self):
        """Must have at least 2 documented conflicts."""
        self.assertGreaterEqual(len(KB.conflicts), 2)

    def test_gap_count(self):
        """Must have at least 5 documented gaps."""
        self.assertGreaterEqual(len(KB.gaps), 5)

    def test_all_23_questions_mapped(self):
        """Every question 1-23 must have at least one claim mapping (even if gap)."""
        for q in range(1, 24):
            claims = KB.get_claims_for_q(q)
            self.assertGreater(len(claims), 0, f"Q{q} has no claims mapped")


class TestClaimProvenance(unittest.TestCase):

    def test_active_claims_have_evidence(self):
        """Every non-gap claim must have at least one evidence entry."""
        for cid, claim in KB.claims.items():
            if claim["status"] in ("gap",):
                continue
            self.assertGreater(len(claim.get("evidence", [])), 0,
                               f"Claim {cid} ({claim['status']}) has no evidence")

    def test_evidence_has_source_file(self):
        """Every evidence entry must have a source_file."""
        for cid, claim in KB.claims.items():
            for ev in claim.get("evidence", []):
                self.assertIn("source_file", ev)
                self.assertTrue(ev["source_file"])

    def test_trust_tiers_valid(self):
        """Every claim trust_tier must be 1-7."""
        for cid, claim in KB.claims.items():
            self.assertIn(claim.get("trust_tier", 1), range(1, 8))

    def test_conflict_claims_exist(self):
        """Every claim_id in a conflict record must exist in the KB."""
        for cf in KB.conflicts:
            for cid in cf["claim_ids"]:
                self.assertIn(cid, KB.claims,
                              f"Conflict {cf['conflict_id']} references missing {cid}")


class TestQuestionCoverage(unittest.TestCase):

    def test_gap_questions_return_gap(self):
        """Q19-Q23 must return a gap-type status via retrieval engine."""
        for q in [19, 20, 21, 22, 23]:
            result = _search(q)
            self.assertIn(result["status"], GAP_TYPES,
                          f"Q{q} should be gap but got '{result['status']}'")

    def test_answered_questions_have_evidence(self):
        """Q1-Q18 must return answered status with at least one evidence entry."""
        for q in [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18]:
            result = _search(q)
            self.assertEqual(result["status"], "answered",
                             f"Q{q} expected 'answered', got '{result['status']}'")
            self.assertGreater(len(result["evidence"]), 0,
                               f"Q{q} answered but no evidence")

    def test_all_answers_have_answer_text(self):
        """Every question must produce a non-empty answer string via answer_all()."""
        answers = answer_all(KB)
        self.assertEqual(len(answers), 23)
        for a in answers:
            self.assertTrue((a.get("answer") or "").strip(),
                            f"Q{a.get('question_id')} produced empty answer")

    def test_q2_mentions_version_scope(self):
        """Q2 answer must mention version scope (3.2), 200 bar, and 180 bar."""
        result = _search(2)
        self.assertIn("3.2", result["answer"])
        self.assertIn("200", result["answer"])
        self.assertIn("180", result["answer"])


class TestConflictsGaps(unittest.TestCase):

    def test_conf001_pressure_conflict_present(self):
        """CONF-001 must exist and reference the 175-bar field-note claim."""
        conf = next((c for c in KB.conflicts if c["conflict_id"] == "CONF-001"), None)
        self.assertIsNotNone(conf, "CONF-001 not found")
        self.assertIn("CLM-030", conf["claim_ids"])

    def test_175bar_claim_is_low_trust(self):
        """The 175-bar field note must be trust_tier=6 and status=conflict."""
        claim = KB.claims.get("CLM-030")
        self.assertIsNotNone(claim)
        self.assertEqual(claim["trust_tier"], 6)
        self.assertEqual(claim["status"], "conflict")

    def test_section8_gap_recorded(self):
        """Section 8 bleed procedure must appear in the gaps list."""
        refs = [g["reference"] for g in KB.gaps]
        self.assertTrue(any("Section 8" in r for r in refs),
                        f"Section 8 gap not found. Gaps: {refs}")

    def test_q20_false_premise_flagged(self):
        """Q20 must return gap_false_premise and mention voltage/false premise."""
        result = _search(20)
        self.assertEqual(result["status"], "gap_false_premise")
        answer_lower = result["answer"].lower()
        self.assertIn("voltage", answer_lower)
        self.assertIn("false premise", answer_lower)


if __name__ == "__main__":
    unittest.main(verbosity=2)
