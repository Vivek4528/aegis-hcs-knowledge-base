@echo off
REM Aegis Series-7 HCS Knowledge Base — one-command run
REM Usage: run.bat [serve|eval|test|all]

cd /d "%~dp0"

IF "%1"=="" GOTO serve
IF "%1"=="serve" GOTO serve
IF "%1"=="eval" GOTO eval
IF "%1"=="test" GOTO test
IF "%1"=="all" GOTO all

:all
echo === Aegis KB — Full pipeline ===
echo [1/4] Installing dependencies...
pip install -r requirements.txt -q
echo [2/4] Running Phase 1 (ingest all 20 files)...
python pipeline_phase1.py
echo [3/4] Running Phase 2 (build knowledge base)...
python pipeline_phase2.py
echo [4/4] Running evaluation...
python eval\evaluator.py
echo.
echo [Tests] Running full test suite...
python -m pytest tests\ -v
echo.
echo [Server] Starting web interface...
python api\server.py
GOTO end

:serve
echo Starting Aegis HCS Knowledge Base...
echo Open http://localhost:5000 in your browser
python api\server.py
GOTO end

:eval
echo Running evaluation against gold_answers.json...
python eval\evaluator.py
GOTO end

:test
echo Running full test suite...
python -m pytest tests\ -v
GOTO end

:end
