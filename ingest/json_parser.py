"""
JSON parser using Python stdlib json module.
Extraction type: DETERMINISTIC — json.loads is a pure parser with no ML.

Special logic: maps configuration JSON keys to their documentation terminology
equivalents (e.g. sensor_ps04a_threshold_bar → PS-04A normal pressure setpoint).
This mapping is rule-based and documented explicitly.
"""
import json
from schema import (
    RawExtraction, ContentBlock, TableData, ExtractionStep,
    ExtractionMethod, MethodType
)


# Rule-based key-to-terminology mapping.
# Rationale: configuration_export.json uses internal firmware key names;
# documentation uses component IDs and human-readable terms.
# This map is derived by cross-referencing the JSON keys against the
# operator manual, component register, and config export metadata.
JSON_KEY_TERMINOLOGY_MAP = {
    "system":                               ("system_name", "Aegis Series-7 HCS"),
    "controller_id":                        ("component_id", "PLC-03"),
    "firmware_version":                     ("software_revision", None),
    "export_timestamp":                     ("config_export_date", None),

    "valve_iv21_required_state":            ("IV-21 startup interlock state", None),
    "estop_required_state":                 ("E-stop startup interlock state", None),
    "maintenance_panel_required_state":     ("Maintenance panel startup interlock state", None),
    "fluid_level_required_band":            ("Hydraulic fluid level startup interlock band", None),

    "sensor_ps04a_threshold_bar":           ("PS-04A normal operating pressure setpoint (bar)", None),
    "sensor_ps04a_alarm_low_bar":           ("PS-04A alarm low threshold = A17 trigger (bar)", None),
    "sensor_ps04a_alarm_high_bar":          ("PS-04A alarm high threshold = A18 trigger (bar)", None),
    "sensor_ps04a_signal_type":             ("PS-04A signal type", None),
    "sensor_ps40_zone":                     ("PS-40 zone assignment (NOT HPU discharge)", None),
    "sensor_ps40_note":                     ("PS-40 note: unrelated to HPU discharge circuit", None),

    "A17":                                  ("alarm_id", "A17 - Hydraulic Pressure Low"),
    "A18":                                  ("alarm_id", "A18 - Hydraulic Pressure High"),
    "A19":                                  ("alarm_id", "A19 - Pressure Sensor Signal Invalid"),
    "persistence_before_shutdown_seconds":  ("alarm persistence before Shutdown Procedure 4.7 (seconds)", None),
    "shutdown_procedure_ref":               ("references Shutdown Procedure section", None),

    "min_pressure_bar_required_for_reset":  ("minimum pressure for controller reset (bar)", None),
    "max_pressure_bar_allowed_for_reset":   ("maximum pressure allowed for controller reset (bar)", None),

    "sensor_ps04a_threshold_bar (rev>=3.2)":("PS-04A threshold applies from firmware", "3.2"),
    "sensor_ps04_legacy_threshold_bar":     ("PS-04 legacy threshold (pre-3.2) (bar)", None),
}


def parse_json(filepath: str, file_info: dict) -> RawExtraction:
    """Parse a JSON configuration export file."""
    extraction = RawExtraction(
        source_file=file_info["path"],
        file_format="json",
        trust_tier=file_info["trust_tier"],
        trust_label=file_info["trust_label"],
    )

    extraction.extraction_steps.append(ExtractionStep(
        step_name="json_parsing",
        method=ExtractionMethod.JSON_STDLIB,
        method_type=MethodType.DETERMINISTIC,
        reason="Python's json.loads() is a deterministic grammar-based parser. "
               "Key-to-terminology mapping is a hand-authored rule table derived "
               "by cross-referencing JSON keys against documentation; rule-based."
    ))

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        extraction.structured_data = data
        extraction.metadata["top_level_keys"] = list(data.keys())

        # Flatten the JSON into content blocks with terminology mapping
        _flatten_json(data, extraction, key_path="")

        # Also produce a table of sensor thresholds for easy reference
        sensors = data.get("sensors", {})
        if sensors:
            rows = []
            for k, v in sensors.items():
                terminology = JSON_KEY_TERMINOLOGY_MAP.get(k, (k, None))
                rows.append([k, str(v), terminology[0]])

            extraction.tables.append(TableData(
                headers=["JSON Key", "Value", "Documentation Terminology"],
                rows=rows,
                section="sensors",
            ))

        # Alarm table
        alarms = data.get("alarms", {})
        if alarms:
            rows = []
            for alarm_id, alarm_data in alarms.items():
                rows.append([
                    alarm_id,
                    alarm_data.get("description", ""),
                    str(alarm_data.get("persistence_before_shutdown_seconds", "null")),
                    alarm_data.get("shutdown_procedure_ref", ""),
                ])
            extraction.tables.append(TableData(
                headers=["Alarm ID", "Description", "Persistence (s) Before Shutdown", "Procedure Ref"],
                rows=rows,
                section="alarms",
            ))

        # Revision applicability table
        rev_app = data.get("revision_applicability", {})
        if rev_app:
            rows = []
            for k, v in rev_app.items():
                rows.append([k, json.dumps(v)])
            extraction.tables.append(TableData(
                headers=["Config Key", "Revision Applicability"],
                rows=rows,
                section="revision_applicability",
            ))

        # Flag the PS-40 note explicitly as it is a critical entity separation note
        ps40_note = sensors.get("sensor_ps40_note", "")
        if ps40_note:
            extraction.content_blocks.append(ContentBlock(
                text=f"ENTITY SEPARATION NOTE (from config): {ps40_note}",
                block_type="note",
                section="sensors",
            ))

        extraction.overall_confidence = 0.95

    except Exception as e:
        extraction.failures.append(f"JSON parsing failed: {str(e)}")
        extraction.overall_confidence = 0.0

    return extraction


def _flatten_json(obj, extraction, key_path, section=None):
    """Recursively flatten a JSON object into content blocks."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{key_path}.{k}" if key_path else k
            terminology = JSON_KEY_TERMINOLOGY_MAP.get(k, None)
            term_note = f" [terminology: {terminology[0]}]" if terminology else ""

            if isinstance(v, (dict, list)):
                _flatten_json(v, extraction, full_key, section=k)
            else:
                extraction.content_blocks.append(ContentBlock(
                    text=f"{full_key} = {v}{term_note}",
                    block_type="config_value",
                    section=section or key_path,
                ))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _flatten_json(item, extraction, f"{key_path}[{i}]", section=section)
