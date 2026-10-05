"""
query_engine.py — thin registry of evaluation question TEXT only.

No Q-number routing. No ID → answer mapping.
The UI chips send question TEXT directly to /api/search.
This module only provides the list of 23 evaluation questions for the chips endpoint
and for the evaluator (which iterates over them by text).

Gold answers live ONLY in eval/gold_answers.json.
Gap detection is keyed on entity + predicate, not question number.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from query.retrieval_engine import search

# ── 23 evaluation question texts ─────────────────────────────────────────────
# These are provided as chips in the UI. The chips call /api/search with the
# question text directly — no question ID is involved in the pipeline.
EVALUATION_QUESTIONS = {
    1:  "What must be true before starting the Hydraulic Power Unit?",
    2:  "What is the current normal operating pressure for the HPU, and under what conditions does that apply?",
    3:  "What does alarm A17 indicate, and what are its possible causes?",
    4:  "Is PS-04 the same component as PS-04A?",
    5:  "Which document introduced the change from PS-04 to PS-04A?",
    6:  "Which components connect directly to the HCS controller, according to the hydraulic schematic?",
    7:  "What action is required if alarm A17 persists for more than 10 seconds?",
    8:  "Under what circumstances must the controller not be reset?",
    9:  "What was the operating pressure threshold before software revision 3.2, and what changed it?",
    10: "Which alarm is associated with a pressure sensor reading below 150 bar?",
    11: "According to the component register, what is the location of the isolation valve IV-21?",
    12: "Does the training slide deck introduce any component or alarm not found in the manuals?",
    13: "What sensor ID appears on the diagnostics screenshot, and does it match a known component?",
    14: "Per the revision history, when did software revision 3.2 take effect, and what changed alongside it?",
    15: "What does sensor_ps04a_threshold_bar in the configuration export correspond to in the operator manual's terminology?",
    16: "Does the 200 bar threshold apply to all Aegis HCS units, or only some?",
    17: "Is PS-04 the same as PS-40?",
    18: "What was the pressure limit before revision 3.2?",
    19: "What is the maximum continuous operating temperature of PS-04A?",
    20: "What is the calibration interval for the electrical system diagram's voltage sensor?",
    21: "Who approved engineering bulletin ECN-1058?",
    22: "What is the mean time between failures for the isolation valve IV-21?",
    23: "Is the Aegis Series-7 HCS compatible with a 3-phase 400V supply?",
}


def answer_all(kb) -> list:
    """Answer all 23 evaluation questions via the retrieval engine."""
    results = []
    for q_id, q_text in EVALUATION_QUESTIONS.items():
        r = search(q_text, kb)
        r["question_id"] = q_id    # for evaluator tracking only
        r["question"]    = q_text
        results.append(r)
    return results
