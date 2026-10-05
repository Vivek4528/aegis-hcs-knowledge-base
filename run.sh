#!/usr/bin/env bash
# Aegis Series-7 HCS Knowledge Base — Unix run script
# Usage: ./run.sh [serve|eval|test|adversarial|ablation|all]
set -e
cd "$(dirname "$0")"

case "${1:-serve}" in
  all)
    echo "=== Installing dependencies ==="
    pip install -r requirements.txt -q
    echo "=== Phase 1: ingestion ==="
    python pipeline_phase1.py
    echo "=== Phase 2: knowledge base ==="
    python pipeline_phase2.py
    echo "=== Evaluation ==="
    python eval/evaluator.py
    echo "=== Tests ==="
    python -m pytest tests/ -v
    echo "=== Server ==="
    python api/server.py
    ;;
  eval)
    python eval/evaluator.py
    ;;
  test)
    python -m pytest tests/ -v
    ;;
  adversarial)
    python adversarial_new.py
    ;;
  ablation)
    python ablation.py
    ;;
  serve|*)
    echo "Open http://localhost:5000"
    python api/server.py
    ;;
esac
