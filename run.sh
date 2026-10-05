#!/usr/bin/env bash
# Aegis Series-7 HCS Knowledge Base — one-command run
# Usage: ./run.sh [serve|eval|test|all]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CMD="${1:-serve}"

case "$CMD" in
    serve)
        echo "Starting Aegis HCS Knowledge Base..."
        echo "Open http://localhost:5000 in your browser"
        python api/server.py
        ;;
    eval)
        echo "Running evaluation against gold_answers.json..."
        python eval/evaluator.py
        ;;
    test)
        echo "Running full test suite..."
        python -m pytest tests/ -v
        ;;
    all)
        echo "=== Aegis KB — Full pipeline ==="
        echo "[1/4] Installing dependencies..."
        pip install -r requirements.txt -q
        echo "[2/4] Running Phase 1 (ingest all 20 files)..."
        python pipeline_phase1.py
        echo "[3/4] Running Phase 2 (build knowledge base)..."
        python pipeline_phase2.py
        echo "[4/4] Running evaluation..."
        python eval/evaluator.py
        echo ""
        echo "[Tests] Running full test suite..."
        python -m pytest tests/ -v
        echo ""
        echo "[Server] Starting web interface..."
        python api/server.py
        ;;
    *)
        echo "Usage: ./run.sh [serve|eval|test|all]"
        exit 1
        ;;
esac
