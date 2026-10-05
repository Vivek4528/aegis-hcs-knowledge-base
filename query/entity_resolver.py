"""
Entity resolver — maps free-text mentions to canonical entity IDs.
All aliases are traced to their source document (provenance on every entry).
"""
import re

# ── Alias table ───────────────────────────────────────────────────────────────
# Each alias → (canonical_id, source)
# Sorted longest-first so longer phrases match before substrings.
_RAW_ALIASES = [
    # HPU  ─ source: operator_manual §1 ("also referred to as"), component_register, glossary
    ("hydraulic power unit",  "HPU", "operator_manual §1"),
    ("hydraulic power pack",  "HPU", "legacy_manual §4, maintenance_manual §7"),
    ("hydraulic unit",        "HPU", "operator_manual §1, glossary AEG-GL-700"),
    ("hp unit",               "HPU", "operator_manual §1"),
    ("hpu",                   "HPU", "component_register"),

    # PS-04A  ─ physical label variant from screen_03
    ("p.s.04-a",              "PS-04A", "screen_03_diagnostics (physical unit label)"),
    ("pressure sensor 04a",   "PS-04A", "component_register"),
    ("pressure sensor ps-04a","PS-04A", "component_register"),
    ("ps 04a",                "PS-04A", "component_register"),
    ("ps-04a",                "PS-04A", "component_register"),
    ("ps04a",                 "PS-04A", "component_register"),
    ("p04a",                  "PS-04A", "component_register"),

    # PS-04  ─ distinct from PS-04A (different signal conditioning, pre-3.2 only)
    ("pressure sensor 04",    "PS-04", "component_register"),
    ("pressure sensor ps-04", "PS-04", "component_register"),
    ("pressure sensor ps04",  "PS-04", "component_register"),
    ("ps 04",                 "PS-04", "component_register"),
    ("ps-04",                 "PS-04", "component_register"),
    ("ps04",                  "PS-04", "component_register"),
    ("p04",                   "PS-04", "component_register"),

    # PS-40  ─ COOLANT LOOP sensor; explicitly NOT related to HPU discharge
    ("pressure sensor 40",    "PS-40", "component_register (note: coolant loop, Skid B)"),
    ("ps-40",                 "PS-40", "component_register"),
    ("ps40",                  "PS-40", "component_register"),
    ("p40",                   "PS-40", "component_register"),

    # Alarms
    ("hydraulic pressure low",          "A17", "alarm_reference"),
    ("alarm a17",                       "A17", "alarm_reference"),
    ("alarm 17",                        "A17", "alarm_reference"),
    ("a17",                             "A17", "alarm_reference"),
    ("hydraulic pressure high",         "A18", "alarm_reference"),
    ("alarm a18",                       "A18", "alarm_reference"),
    ("alarm 18",                        "A18", "alarm_reference"),
    ("a18",                             "A18", "alarm_reference"),
    ("pressure sensor signal invalid",  "A19", "alarm_reference"),
    ("alarm a19",                       "A19", "alarm_reference"),
    ("alarm 19",                        "A19", "alarm_reference"),
    ("a19",                             "A19", "alarm_reference"),

    # IV-21  ─ valve solenoid and valve driver are PART-OF, not separate entities
    ("isolation valve iv-21",           "IV-21", "component_register"),
    ("isolation valve iv21",            "IV-21", "component_register"),
    ("isolation valve",                 "IV-21", "component_register"),
    ("iv-21 solenoid",                  "IV-21", "wiring_diagram (part_of IV-21)"),
    ("iv-21 valve driver",              "IV-21", "electrical diagram (part_of IV-21)"),
    ("iv-21",                           "IV-21", "component_register"),
    ("iv21",                            "IV-21", "component_register"),

    # PLC-03
    ("hcs controller",                  "PLC-03", "component_register"),
    ("aegis controller",                "PLC-03", "component_register"),
    ("plc-03",                          "PLC-03", "component_register"),
    ("plc03",                           "PLC-03", "component_register"),
    ("controller",                      "PLC-03", "component_register"),

    # Documents
    ("engineering change notice 1042",  "ECN-1042", "engineering_bulletins/ECN-1042.pdf"),
    ("engineering change notice 1058",  "ECN-1058", "engineering_bulletins/ECN-1058.pdf"),
    ("ecn-1042",                        "ECN-1042", "engineering_bulletins/ECN-1042.pdf"),
    ("ecn-1058",                        "ECN-1058", "engineering_bulletins/ECN-1058.pdf"),
    ("ecn1042",                         "ECN-1042", "engineering_bulletins/ECN-1042.pdf"),
    ("ecn1058",                         "ECN-1058", "engineering_bulletins/ECN-1058.pdf"),

    # Wiring labels & Relays
    ("relay ka1",                       "KA1",   "diagrams/system_diagram_electrical.png (AEG-DWG-E02)"),
    ("ka-1",                            "KA1",   "diagrams/system_diagram_electrical.png (AEG-DWG-E02)"),
    ("ka1",                             "KA1",   "diagrams/system_diagram_electrical.png (AEG-DWG-E02)"),
    ("tb-7",                            "TB-7",  "diagrams/wiring_diagram.pdf (AEG-DWG-W03) and AEG-DWG-E02"),
    ("tb7",                             "TB-7",  "diagrams/wiring_diagram.pdf (AEG-DWG-W03) and AEG-DWG-E02"),
    ("j-14",                            "J-14",  "diagrams/wiring_diagram.pdf (AEG-DWG-W03)"),
    ("j14",                             "J-14",  "diagrams/wiring_diagram.pdf (AEG-DWG-W03)"),
    ("j-15",                            "IV-21", "diagrams/wiring_diagram.pdf (AEG-DWG-W03) note: J-15 = IV-21 solenoid"),
    ("j15",                             "IV-21", "diagrams/wiring_diagram.pdf (AEG-DWG-W03) note: J-15 = IV-21 solenoid"),

    # Training slides
    ("training slide",                  "training_slides", "extra/training_slide_excerpt.pptx"),
    ("training deck",                   "training_slides", "extra/training_slide_excerpt.pptx"),
    ("slide deck",                      "training_slides", "extra/training_slide_excerpt.pptx"),
    ("training_slide_excerpt.pptx",     "training_slides", "extra/training_slide_excerpt.pptx"),
]

# Build sorted lookup (longest phrase first to prevent substring match errors)
ALIAS_TABLE = sorted(_RAW_ALIASES, key=lambda x: -len(x[0]))

# Predicate → keywords that suggest the user is asking about this predicate
PREDICATE_KEYWORDS = {
    "component_description": [
        "what is", "tell me about", "describe", "function of", "role of",
        "purpose of", "terminal block", "relay",
    ],
    "startup_interlock_condition": [
        "before start", "prior to start", "must be true", "startup condition",
        "interlock", "start the", "starting the", "prerequisite",
        "what must", "requirements before", "before starting", "before you can",
    ],
    "normal_operating_pressure": [
        "normal pressure", "operating pressure", "discharge pressure",
        "normal operating", "running pressure", "200 bar", "setpoint",
        "what pressure", "pressure setpoint", "threshold bar",
        "pressure reading", "pressure should be",
        "pressure limit", "pressure threshold", "pressure before",
        "before revision", "prior to revision", "pre-3.2", "pre 3.2",
        "before 3.2", "what was the pressure",
    ],
    "alarm_trigger_pressure_low": [
        "below 150", "150 bar", "pressure low alarm",
        "low pressure threshold", "fires below",
    ],
    "alarm_trigger_pressure_high": [
        "above 220", "220 bar", "high pressure alarm", "overpressure",
        "pressure too high", "fires above",
    ],
    "alarm_description": [
        "alarm", "indicate", "what does alarm", "mean", "cause",
        "trigger", "what is alarm", "fires when", "activates when",
        "what happens when alarm",
    ],
    "alarm_persistence_before_shutdown": [
        "persist", "10 second", "more than 10", "persists for",
        "shutdown procedure", "procedure 4.7", "what if alarm persists",
    ],
    "alarm_shutdown_procedure_ref": [
        "shutdown procedure", "procedure 4.7", "4.7", "after alarm", "response to alarm",
    ],
    "controller_reset_max_pressure": [
        "reset", "controller reset", "not reset", "reset condition",
        "max pressure", "reset allowed", "reset the controller",
        "when can", "when can i reset",
    ],
    "component_location": [
        "location", "where is", "located", "where", "where can i find",
    ],
    "sensor_replaced_by": [
        "same as", "different", "vs", "versus", "replace",
        "replaced by", "same component", "distinction between",
        "is ps-04 the same", "what is the difference",
    ],
    "document_supersedes": [
        "introduced", "which document", "what document", "introduced the change",
        "changed by", "who changed", "what ecn", "which ecn",
        "which document introduced", "changed from", "ps-04 to ps-04a",
    ],
    "document_clarifies": [
        "ecn-1058", "clarify", "correction", "corrects", "does not supersede",
    ],
    "component_alias": [
        "also called", "alias", "another name", "known as",
        "same thing as", "what does", "do", "function of",
    ],
    "document_approver": [
        "who approved", "approver", "approved by", "signed off", "authorised",
        "authorized", "who signed",
    ],
    "calibration_date": [
        "calibration", "calibrated", "last calibration", "calibration date",
        "calibration interval", "how often calibrated",
    ],
    "control_signal_to": [
        "connect", "connected", "directly to", "wired to",
        "which component", "components connect", "what connects",
    ],
    "applies_from_revision": [
        "revision", "software revision", "when did", "effective",
        "firmware", "what revision", "sw rev", "release date",
    ],
    "observed_pressure": [
        "observed", "measured", "reading", "live reading", "screenshot",
    ],
    "training_slide_content": [
        "training slide", "slide deck", "training deck",
        "introduce", "introduces", "not found in the manuals",
        "new component", "new alarm", "does the training",
    ],
}


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, remove punctuation except - and .."""
    t = text.lower()
    t = re.sub(r"[^\w\s.\-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def recognize_entities(norm_query: str) -> list:
    """
    Return list of canonical entity IDs found in the normalized query.
    Uses longest-match on alias table.
    """
    found = []
    consumed = set()  # character positions already matched
    for alias, entity, _ in ALIAS_TABLE:
        start = 0
        while True:
            pos = norm_query.find(alias, start)
            if pos == -1:
                break
            span = set(range(pos, pos + len(alias)))
            if not span & consumed:
                if entity not in found:
                    found.append(entity)
                consumed |= span
            start = pos + 1
    return found


def recognize_predicates(norm_query: str) -> list:
    """
    Return list of predicate names suggested by the query text.
    """
    found = []
    for pred, keywords in PREDICATE_KEYWORDS.items():
        for kw in keywords:
            if kw in norm_query:
                if pred not in found:
                    found.append(pred)
                break
    return found


def get_alias_source(alias: str) -> str:
    """Return provenance string for a known alias."""
    norm = alias.lower().strip()
    for a, _, source in _RAW_ALIASES:
        if a == norm:
            return source
    return "unknown"


def check_unknown_ids(norm_query: str, known_entities: set) -> dict:
    """
    Rule on entity existence:
    Examines candidate IDs (alarm, component, terminal, document) in query.
    If a candidate ID has NO entity in the knowledge base, returns a not_found response
    with 'cannot confirm', listing checked files and missing documents.
    """
    # 1. Alarm IDs: e.g. A25, A99, A40, alarm 25, alarm a99
    alarm_matches = re.findall(r'\b(?:alarm\s+)?a-?(\d{1,3})\b', norm_query)
    for num in alarm_matches:
        canon_id = f"A{int(num)}"
        if canon_id not in known_entities:
            return {
                "status": "not_found",
                "unknown_id": canon_id,
                "id_type": "alarm",
                "answer": (
                    f"cannot confirm alarm {canon_id}: AEG-AL-700 covers A17, A18, A19. "
                    "AEG-AL-701 covers A01-A16 and A20-A34, which is not in the documentation package."
                ),
            }

    # 2. Sensor / Component IDs: e.g. PS-99, IV-99, PLC-99, KA-99, TB-99, XV-99
    comp_matches = re.findall(r'\b(ps|iv|plc|ka|tb|xv|hv|fv|v|cv|pump)-?(\d{1,3}[a-z]?)\b', norm_query)
    for prefix, num in comp_matches:
        prefix_upper = prefix.upper()
        cand = f"{prefix_upper}-{num.upper()}"
        cand_alt = f"{prefix_upper}{num.upper()}"
        matched = False
        for alias, ent, _ in ALIAS_TABLE:
            if cand.lower() == alias or cand_alt.lower() == alias:
                matched = True
                break
        if not matched and cand not in known_entities and cand_alt not in known_entities:
            return {
                "status": "not_found",
                "unknown_id": cand,
                "id_type": "component",
                "answer": (
                    f"cannot confirm component {cand}: not found in documentation package. "
                    "Component register (AEG-CR-700) covers "
                    "HPU, PS-04, PS-04A, PS-40, IV-21, PLC-03, KA1, TB-7. "
                    f"{cand} does not appear in any documentation in this package."
                ),
            }

    # 3. Terminal IDs: e.g. J-99
    term_matches = re.findall(r'\bj-?(\d{1,3})\b', norm_query)
    for num in term_matches:
        cand = f"J-{num}"
        cand_alt = f"J{num}"
        matched = False
        for alias, ent, _ in ALIAS_TABLE:
            if cand.lower() == alias or cand_alt.lower() == alias:
                matched = True
                break
        if not matched and cand not in known_entities and cand_alt not in known_entities:
            return {
                "status": "not_found",
                "unknown_id": cand,
                "id_type": "terminal",
                "answer": (
                    f"cannot confirm terminal/wiring reference {cand}: not found in diagrams. "
                    "Wiring diagram AEG-DWG-W03 covers "
                    "terminals J-14 (PS-04A) and J-15 (IV-21) on terminal block TB-7. "
                    f"{cand} does not appear in any diagram in this package."
                ),
            }

    # 4. Document IDs: e.g. ECN-9999
    doc_matches = re.findall(r'\b(ecn|aeg-[a-z]+)-?(\d{2,4})\b', norm_query)
    for prefix, num in doc_matches:
        cand = f"{prefix.upper()}-{num}"
        if cand not in known_entities:
            return {
                "status": "not_found",
                "unknown_id": cand,
                "id_type": "document",
                "answer": (
                    f"cannot confirm document {cand}: File manifest covers ECN-1042 and ECN-1058. "
                    f"{cand} was not found in the package."
                ),
            }

    return None


PROPERTY_PATTERNS = [
    ("reset time", "reset_time"),
    ("reset duration", "reset_time"),
    ("max temperature", "max_temperature"),
    ("operating temperature", "operating_temperature"),
    ("temperature", "temperature"),
    ("operating voltage", "operating_voltage"),
    ("voltage", "voltage"),
    ("flow rate", "flow_rate"),
    ("baud rate", "baud_rate"),
    ("weight", "weight"),
    ("dimensions", "dimensions"),
]


def check_false_premise_properties(entities: list, norm_query: str, kb) -> dict:
    """
    If a question asks for a property that no claim has for an existing entity,
    return 'not found for this entity' and list the predicates that do exist.
    Implemented via entity+predicate lookup.
    """
    if not entities:
        return None

    for ent in entities:
        existing_predicates = {
            c["predicate"] for c in kb.claims.values()
            if c["subject"] == ent and c["status"] in ("active", "version_scoped", "gap", "conflict", "observed")
        }
        if not existing_predicates:
            continue

        for phrase, prop_name in PROPERTY_PATTERNS:
            if phrase in norm_query:
                if prop_name not in existing_predicates:
                    pred_list = ", ".join(sorted(existing_predicates))
                    return {
                        "status": "gap_false_premise",
                        "entity": ent,
                        "property": phrase,
                        "answer": (
                            f"Property '{phrase}' is not found for this entity ({ent}). "
                            f"Documented properties for {ent} are: {pred_list}."
                        ),
                    }
    return None
