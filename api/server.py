"""Flask API server — Aegis HCS Knowledge Base."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, send_from_directory, abort, request
from flask_cors import CORS
from kb.knowledge_base import KnowledgeBase
from query.retrieval_engine import search
from query.query_engine import EVALUATION_QUESTIONS, answer_all

app = Flask(__name__, static_folder="../ui", static_url_path="")
CORS(app)

KB = KnowledgeBase()
KB.load()

# ── Static UI ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

# ── Free-text search (live pipeline — no caching) ───────────────────────────
@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing query parameter 'q'"}), 400
    version = request.args.get("version", None)
    result = search(q, KB, version_hint=version)
    return jsonify(result)

# ── 23 evaluation question chips ─────────────────────────────────────────────
@app.route("/api/questions")
def list_questions():
    return jsonify([
        {"id": q_id, "question": q_text}
        for q_id, q_text in EVALUATION_QUESTIONS.items()
    ])

# ── KB metadata ──────────────────────────────────────────────────────────────
@app.route("/api/kb/stats")
def kb_stats():
    return jsonify(KB.stats())

@app.route("/api/kb/conflicts")
def all_conflicts():
    return jsonify(KB.conflicts)

@app.route("/api/kb/gaps")
def all_gaps():
    return jsonify(KB.gaps)

# ── Evaluation results (read from file — not self-graded inline) ─────────────
@app.route("/api/eval/results")
def eval_results():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "eval_results.json")
    if not os.path.exists(path):
        return jsonify({"error": "Run eval/evaluator.py first to generate results"}), 404
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

# NOTE: /api/question/<q_num> removed.
# UI chips send question text directly to /api/search — no q_num routing.

if __name__ == "__main__":
    print("=" * 60)
    print(" Aegis HCS Knowledge Base — Query Interface")
    print(" Open http://localhost:5000")
    print("=" * 60)
    app.run(debug=False, port=5000, host="0.0.0.0")
