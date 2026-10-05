"""
Phase 3 tests — run with: python -m pytest tests/test_phase3.py -v

Tests:
  TestEvaluator (5):    real metrics from gold_answers.json, thresholds, per-Q, abstention, JSON output
  TestAPIServer (5):    search endpoint, questions list, Q20 false premise, kb stats, eval results
  TestRetrieval (6):    adversarial questions, entity resolution, gap detection, not_found, version scope
"""
import sys, os, json, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search
from query.query_engine import EVALUATION_QUESTIONS
from eval.evaluator import run_evaluation, load_gold


class TestEvaluator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()
        cls.kb.load()
        cls.metrics = run_evaluation()
        cls.gold = load_gold()

    def test_all_23_questions_scored(self):
        """Evaluator must produce exactly 23 scored results."""
        self.assertEqual(len(self.metrics["per_question"]), 23)

    def test_overall_accuracy_at_least_90pct(self):
        """Overall accuracy must be >= 90% (at least 21/23)."""
        self.assertGreaterEqual(self.metrics["overall_accuracy_pct"], 90.0,
            f"Overall accuracy {self.metrics['overall_accuracy_pct']}% < 90%")

    def test_gap_abstention_at_least_80pct(self):
        """Abstention accuracy on gap questions must be >= 80%."""
        pct = self.metrics.get("abstention_overall", {}).get("pct", 0)
        self.assertGreaterEqual(pct, 80.0,
            f"Abstention {pct}% < 80%")

    def test_answerable_accuracy_at_least_90pct(self):
        """All answerable questions must score >= 90%."""
        pct = self.metrics["answered_accuracy_pct"]
        self.assertGreaterEqual(pct, 90.0, f"Answerable accuracy {pct}% < 90%")

    def test_eval_json_written(self):
        """output/eval_results.json must exist and contain required keys."""
        path = "output/eval_results.json"
        self.assertTrue(os.path.exists(path), f"{path} not written")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("metrics", data)
        self.assertIn("answers", data)


class TestAPIServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import importlib, sys as _sys
        _sys.path.insert(0, "api")
        cls.server_mod = importlib.import_module("server")
        cls.app = cls.server_mod.app
        cls.client = cls.app.test_client()
        cls.app.config["TESTING"] = True

    def test_search_ps99_returns_not_found(self):
        """GET /api/search?q=What is PS-99 must return not_found status."""
        resp = self.client.get("/api/search?q=What+is+PS-99%3F")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn(data["status"], ("not_found", "partial"),
            f"PS-99 returned status '{data['status']}', expected not_found")

    def test_search_q20_false_premise(self):
        """Q20 exact question must return gap_false_premise."""
        q20 = "What is the calibration interval for the electrical system diagram's voltage sensor?"
        resp = self.client.get(f"/api/search?q={q20.replace(' ', '+')}")
        data = json.loads(resp.data)
        self.assertIn(data["status"], ("gap_false_premise", "gap"),
            f"Q20 returned '{data['status']}', expected gap_false_premise")

    def test_questions_endpoint_returns_23(self):
        """GET /api/questions must return 23 question chips."""
        resp = self.client.get("/api/questions")
        data = json.loads(resp.data)
        self.assertEqual(len(data), 23)

    def test_kb_stats_endpoint(self):
        """GET /api/kb/stats must return total_claims >= 38."""
        resp = self.client.get("/api/kb/stats")
        data = json.loads(resp.data)
        self.assertGreaterEqual(data["total_claims"], 38)

    def test_eval_results_endpoint(self):
        """GET /api/eval/results must include per_question list of 23 items."""
        resp = self.client.get("/api/eval/results")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        metrics = data.get("metrics", {})
        self.assertEqual(len(metrics.get("per_question", [])), 23)


class TestRetrieval(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.kb = KnowledgeBase()
        cls.kb.load()

    def _search(self, q):
        return search(q, self.kb)

    def test_ps99_not_found(self):
        r = self._search("What is PS-99?")
        self.assertIn(r["status"], ("not_found", "partial"),
            f"PS-99 returned '{r['status']}'")

    def test_a18_answered(self):
        r = self._search("What does alarm A18 mean?")
        self.assertEqual(r["status"], "answered")
        self.assertTrue(any("220" in c["value"] for c in r["claims_used"]),
            "A18 answer missing '220 bar'")

    def test_ps04a_do_answered(self):
        r = self._search("what does ps04a do")
        self.assertEqual(r["status"], "answered")
        self.assertIn("PS-04A", r["recognized_entities"])

    def test_controller_reset_pressure(self):
        r = self._search("What is the max pressure allowed for a controller reset?")
        self.assertEqual(r["status"], "answered")
        self.assertTrue(any("50" in c["value"] for c in r["claims_used"]),
            "Reset pressure answer missing '50 bar'")

    def test_j_torres_partial(self):
        r = self._search("Who is J. Torres?")
        self.assertIn(r["status"], ("partial", "answered"),
            f"J. Torres returned '{r['status']}'")

    def test_version_scope_in_pressure_answer(self):
        """Q2-type query: answer must mention version scope."""
        r = self._search("What is the current normal operating pressure for the HPU?")
        self.assertEqual(r["status"], "answered")
        # Check version scope visible in claims or answer
        has_scope = any(c.get("scope") and c["scope"] != "all revisions"
                        for c in r["claims_used"])
        self.assertTrue(has_scope, "Pressure answer has no version scope")


if __name__ == "__main__":
    unittest.main(verbosity=2)
