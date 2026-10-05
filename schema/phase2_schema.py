"""
Phase 2 schema: Claim, Entity, Evidence, ConflictRecord, GapRecord.
These are the data structures that Phase 2 will populate.

Design rationale is documented in-line on every field.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ── Enumerations ────────────────────────────────────────────────────────────

class ClaimStatus(str, Enum):
    ACTIVE     = "active"         # Currently valid for supported SW revisions
    SUPERSEDED = "superseded"     # Replaced by another claim (cite superseded_by)
    LEGACY     = "version_scoped" # True for a specific SW/HW version range only
    OBSERVED   = "observed"       # Live reading from screenshot; NOT a spec
    CONFLICT   = "conflict"       # Contradicted by another source; needs resolution
    GAP        = "gap"            # Referenced but not answerable from available sources


class ClaimPredicate(str, Enum):
    # ── Pressure predicates (kept SEPARATE per design decision) ──────────────
    NORMAL_OPERATING_PRESSURE   = "normal_operating_pressure"
    # ^ Specified setpoint for normal running. Changes with SW rev.
    # 180 bar pre-3.2, 200 bar rev 3.2+.

    ALARM_TRIGGER_LOW           = "alarm_trigger_pressure_low"
    # ^ Threshold at which A17 fires. Does NOT change with ECN-1042.

    ALARM_TRIGGER_HIGH          = "alarm_trigger_pressure_high"
    # ^ Threshold at which A18 fires. Unchanged.

    OBSERVED_PRESSURE           = "observed_pressure"
    # ^ Live reading from HMI screenshot. NEVER treated as spec.
    # Sources: screen_01_home (200 bar), screen_03_diagnostics (200.3 bar).

    CALIBRATION_SPAN_REFERENCE  = "calibration_span_reference"
    # ^ Reference pressure used during PS-04A calibration (200 bar).
    # Different semantic from normal_operating_pressure despite same numeric value.

    CONTROLLER_RESET_MAX_PRESSURE = "controller_reset_max_pressure"
    # ^ Maximum system pressure at which controller reset is permitted (50 bar).

    # ── Topology predicates ──────────────────────────────────────────────────
    CONNECTS_TO                 = "connects_to"
    # ^ Generic connection; use with edge_color and edge_type sub-fields.

    CONTROL_SIGNAL_TO           = "control_signal_to"
    # ^ PURPLE edge (signal/control) only — counts for Q6 "direct connections".

    HYDRAULIC_FLUID_PATH        = "hydraulic_fluid_path"
    # ^ GREY edge in hydraulic diagram — does NOT count for Q6.

    # ── Alarm predicates ─────────────────────────────────────────────────────
    ALARM_DESCRIPTION           = "alarm_description"
    ALARM_PERSISTENCE_SECONDS   = "alarm_persistence_before_shutdown"
    ALARM_SHUTDOWN_PROCEDURE    = "alarm_shutdown_procedure_ref"

    # ── Component predicates ─────────────────────────────────────────────────
    COMPONENT_ALIAS             = "component_alias"
    COMPONENT_LOCATION          = "component_location"
    COMPONENT_SIGNAL_TYPE       = "component_signal_type"
    SENSOR_REPLACED_BY          = "sensor_replaced_by"

    # ── Document predicates ──────────────────────────────────────────────────
    DOCUMENT_SUPERSEDES         = "document_supersedes"
    DOCUMENT_CLARIFIES          = "document_clarifies"
    # ^ ECN-1058 CLARIFIES ECN-1042 (not supersedes).

    # ── Revision predicates ──────────────────────────────────────────────────
    APPLIES_FROM_REVISION       = "applies_from_revision"
    APPLIES_TO_REVISION         = "applies_to_revision"

    # ── Calibration predicates ───────────────────────────────────────────────
    CALIBRATION_DATE            = "calibration_date"
    CALIBRATION_INTERVAL        = "calibration_interval"
    CALIBRATION_STATUS          = "calibration_status"
    CALIBRATION_TECHNICIAN      = "calibration_technician"

    # ── Interlock predicates ─────────────────────────────────────────────────
    STARTUP_INTERLOCK           = "startup_interlock_condition"


class ConfidenceLevel(str, Enum):
    HIGH   = "high"    # >= 0.90 — T1 born-digital PDF, JSON config
    MEDIUM = "medium"  # 0.70–0.89 — OCR output, T2/T3 sources
    LOW    = "low"     # < 0.70 — diagram topology (rule-based shapes), T6 field notes


class SourceTrust(int, Enum):
    T1_OFFICIAL_MANUAL  = 1
    T2_ECN_BULLETIN     = 2
    T3_REVISION_HISTORY = 3
    T4_CONFIG_EXPORT    = 4
    T5_TRAINING_DECK    = 5
    T6_FIELD_NOTES      = 6
    T7_NOISE            = 7


# ── Evidence ─────────────────────────────────────────────────────────────────

@dataclass
class Evidence:
    """Pointer from a Claim back to its extraction source."""
    source_file:    str               # Relative path in FILE_MANIFEST
    section:        str = ""          # Section heading (e.g. "4.3 Starting the HPU")
    page:           Optional[int] = None
    block_text:     str = ""          # The exact block text the claim was extracted from
    table_row:      Optional[list] = None  # If from a table row
    trust_tier:     int = 1
    extraction_method: str = ""       # e.g. "pdfplumber_text", "vision_model_ocr"
    extraction_confidence: float = 1.0


# ── Claim ─────────────────────────────────────────────────────────────────────

@dataclass
class Claim:
    """
    A single extracted fact about the Aegis Series-7 HCS.

    Design decisions:
    - predicate uses ClaimPredicate enum to prevent free-text mixing of semantically
      distinct concepts (e.g. normal_operating_pressure vs alarm_trigger_pressure).
    - status is PER-CLAIM (not per-document). A legacy manual block may have some
      claims that are still active (e.g. HPU description) and some that are superseded
      (e.g. 180 bar setpoint). Labeling at claim level enables fine-grained queries.
    - version_scope captures SW/HW revision applicability explicitly.
    - is_observed_value=True means the value comes from a screenshot and must NEVER
      be promoted to a specification claim (e.g. "200 bar" from screen_01_home is
      observed, not a setpoint).
    """
    claim_id:       str               # Unique ID e.g. "CLM-0042"
    subject:        str               # Entity ID (e.g. "PS-04A", "HPU", "A17")
    predicate:      ClaimPredicate
    value:          str               # Human-readable value
    value_numeric:  Optional[float] = None  # Parsed numeric if applicable
    value_unit:     Optional[str]   = None  # e.g. "bar", "seconds", "mA"

    status:         ClaimStatus     = ClaimStatus.ACTIVE
    version_scope:  Optional[str]   = None  # e.g. "sw_rev >= 3.2" or "sw_rev < 3.2"
    is_legacy:      bool            = False # True if from superseded document section
    is_observed_value: bool         = False # True if from HMI screenshot (not spec)

    evidence:       list[Evidence]  = field(default_factory=list)
    confidence:     ConfidenceLevel = ConfidenceLevel.HIGH
    trust_tier:     SourceTrust     = SourceTrust.T1_OFFICIAL_MANUAL

    superseded_by:  Optional[str]   = None  # Claim ID that supersedes this one
    clarified_by:   Optional[str]   = None  # Claim ID that clarifies this one
    conflicts_with: list[str]       = field(default_factory=list)  # Claim IDs

    notes:          str = ""


# ── Entity ───────────────────────────────────────────────────────────────────

@dataclass
class Entity:
    """
    A canonical entity with all known aliases.

    Entity resolution decisions (hard-coded at schema definition time):
    - HPU = "Hydraulic Unit" = "HP unit" = "Hydraulic Power Pack"
      (from operator_manual §1; all four appear in the corpus)
    - PS-04A != PS-04 (different sensor; PS-04 was replaced by ECN-1042)
    - PS-04A != PS-40 (different circuit; config JSON explicit note)
    - P.S.04-A = PS-04A (display variant on physical label; screen_03 note)
    - PLC-03 has no aliases
    - IV-21 has no aliases
    """
    entity_id:   str             # Canonical ID (e.g. "HPU", "PS-04A")
    entity_type: str             # "component" | "document" | "alarm" | "procedure"
    aliases:     list[str] = field(default_factory=list)
    description: str = ""
    location:    Optional[str] = None  # Physical location if known
    claims:      list[str] = field(default_factory=list)  # Claim IDs


ENTITY_REGISTRY: dict[str, Entity] = {
    "HPU": Entity(
        entity_id="HPU",
        entity_type="component",
        aliases=["Hydraulic Unit", "HP unit", "Hydraulic Power Pack"],
        description="Hydraulic Power Unit — generates and regulates hydraulic pressure",
        location="Main skid",
    ),
    "PS-04A": Entity(
        entity_id="PS-04A",
        entity_type="component",
        aliases=["P.S.04-A"],   # display variant on physical unit label
        description="HPU discharge pressure transducer (4-20 mA). Replaced PS-04 per ECN-1042.",
        location="HPU discharge line",
    ),
    "PS-04": Entity(
        entity_id="PS-04",
        entity_type="component",
        aliases=[],
        description="Legacy HPU discharge pressure sensor — REPLACED by PS-04A per ECN-1042. "
                    "Span reference was 180 bar. Do not conflate with PS-04A.",
    ),
    "PS-40": Entity(
        entity_id="PS-40",
        entity_type="component",
        aliases=[],
        description="Pressure sensor on a DIFFERENT circuit (coolant loop, Skid B). "
                    "NOT related to HPU discharge. Per config JSON note: "
                    "'unrelated to HPU discharge circuit; do not map to sensor_ps04a_* keys'.",
        location="Skid B coolant loop (per config JSON)",
    ),
    "PLC-03": Entity(
        entity_id="PLC-03",
        entity_type="component",
        aliases=[],
        description="Programmable logic controller — runs HPU control loop. "
                    "Firmware rev 3.2.1 (per screen_03_diagnostics).",
    ),
    "IV-21": Entity(
        entity_id="IV-21",
        entity_type="component",
        aliases=["IV-21 isolation valve", "IV-21 solenoid"],
        description="Isolation valve in hydraulic circuit. Controlled by PLC-03.",
    ),
    "A17": Entity(
        entity_id="A17",
        entity_type="alarm",
        aliases=["Hydraulic Pressure Low"],
        description="Alarm A17: fires when PS-04A reads below alarm_trigger_pressure_low. "
                    "After 10 seconds persistence, triggers Shutdown Procedure 4.7. "
                    "A17 description text was corrected by ECN-1058 to remove hardcoded sensor name.",
    ),
    "A18": Entity(
        entity_id="A18",
        entity_type="alarm",
        aliases=["Hydraulic Pressure High"],
        description="Alarm A18: fires when PS-04A reads above alarm_trigger_pressure_high.",
    ),
    "A19": Entity(
        entity_id="A19",
        entity_type="alarm",
        aliases=["Pressure Sensor Signal Invalid"],
        description="Alarm A19: fires when PS-04A 4-20 mA signal is out of range.",
    ),
    "ECN-1042": Entity(
        entity_id="ECN-1042",
        entity_type="document",
        aliases=[],
        description="Engineering Change Notice: replaced PS-04 with PS-04A, "
                    "changed normal_operating_pressure from 180 to 200 bar at SW rev 3.2. "
                    "SUPERSEDES the 180 bar setpoint claim from legacy documents.",
    ),
    "ECN-1058": Entity(
        entity_id="ECN-1058",
        entity_type="document",
        aliases=[],
        description="Engineering Change Notice: corrected A17 alarm text to remove hardcoded "
                    "sensor name (now reads 'hydraulic pressure sensor' not 'PS-04'). "
                    "CLARIFIES ECN-1042 — does NOT supersede it. "
                    "Leaves pressure setpoint unchanged.",
    ),
}


# ── Conflict record ───────────────────────────────────────────────────────────

@dataclass
class ConflictRecord:
    """
    A documented contradiction between two or more claims.
    The resolver must record ALL conflicts, not silently pick one.
    """
    conflict_id:     str
    subject:         str           # Entity ID the conflict is about
    predicate:       ClaimPredicate
    claims:          list[str]     # Conflicting claim IDs
    description:     str           # Human-readable explanation
    resolution:      str           # How it should be resolved (cite trust tier rule)
    authoritative:   Optional[str] = None  # The winning claim ID, if determinable


KNOWN_CONFLICTS = [
    ConflictRecord(
        conflict_id="CONF-001",
        subject="HPU",
        predicate=ClaimPredicate.NORMAL_OPERATING_PRESSURE,
        claims=["CLM-legacy-180bar", "CLM-ecn1042-200bar", "CLM-survey-175bar"],
        description=(
            "Three sources give different HPU discharge pressure values: "
            "legacy_manual_v1.html says 180 bar; "
            "operator_manual.pdf + ECN-1042 + config JSON say 200 bar (SW rev ≥ 3.2); "
            "site_survey_notes.docx (T6, unreviewed) says 175 bar."
        ),
        resolution=(
            "Trust-tier rule: T1 + T4 (200 bar) wins over T1-superseded (180 bar) and T6 (175 bar). "
            "180 bar is version_scoped to sw_rev < 3.2. "
            "175 bar from field notes is flagged as unverified conflict — not adopted."
        ),
        authoritative="CLM-ecn1042-200bar",
    ),
    ConflictRecord(
        conflict_id="CONF-002",
        subject="A17",
        predicate=ClaimPredicate.ALARM_DESCRIPTION,
        claims=["CLM-alarm-ref-a17-old-text", "CLM-ecn1058-a17-new-text"],
        description=(
            "alarm_reference.pdf original A17 text names 'PS-04' sensor. "
            "ECN-1058 corrects this to 'hydraulic pressure sensor' (generic). "
            "This is a documentation-only correction; no hardware change."
        ),
        resolution=(
            "ECN-1058 text takes precedence for the alarm description. "
            "The old text is version_scoped to before ECN-1058 was issued. "
            "Modeled as clarifies, NOT supersedes — ECN-1058 is explicit on this."
        ),
        authoritative="CLM-ecn1058-a17-new-text",
    ),
]


# ── Gap record ────────────────────────────────────────────────────────────────

@dataclass
class GapRecord:
    """A reference that was detected but whose content is not in the package."""
    gap_id:         str
    reference:      str      # What was referenced
    referenced_in:  list[str]  # Source files where reference appears
    section:        str      # Section in source file where referenced
    gap_type:       str      # "missing_document" | "missing_section" | "missing_data"
    description:    str
    affects_questions: list[str] = field(default_factory=list)  # Q-numbers affected


KNOWN_GAPS = [
    GapRecord(
        gap_id="GAP-001",
        reference="Section 8",
        referenced_in=[
            "manuals/operator_manual.pdf",     # §7 Controller Reset
            "manuals/maintenance_manual.pdf",  # §7 Component Access
        ],
        section="7 Controller Reset / 7 Component Access",
        gap_type="missing_section",
        description=(
            "Manual bleed procedure for reducing hydraulic pressure below 50 bar "
            "before controller reset or panel access. "
            "Operator manual §7: 'Bleed pressure below 50 bar first, using the manual "
            "bleed procedure in Section 8, before performing a controller reset.' "
            "Maintenance manual §7: 'pressure has been bled per Section 8.'"
        ),
        affects_questions=["Q11", "Q14"],
    ),
    GapRecord(
        gap_id="GAP-002",
        reference="AEG-AL-701",
        referenced_in=["reference/alarm_reference.pdf"],
        section="3 Pressure sensor run Shutdown Proc. 4.7",
        gap_type="missing_document",
        description=(
            "Companion electrical alarm reference covering alarms A01–A16 and A20–A34 "
            "(electrical, lubrication, communications). Not included in this package. "
            "AEG-AL-700 (the file present) covers only alarms A17–A19."
        ),
        affects_questions=["Q7", "Q8"],
    ),
    GapRecord(
        gap_id="GAP-003",
        reference="Calibration interval for PS-04A",
        referenced_in=["scans/scanned_appendix_calibration.pdf"],
        section="Calibration Points",
        gap_type="missing_data",
        description=(
            "Scanned calibration record explicitly states: "
            "'No calibration interval is specified for PS-04A on this form; "
            "recalibration frequency should be confirmed against the applicable "
            "maintenance schedule, which is not included in this binder.' "
            "The maintenance schedule is not in the package."
        ),
        affects_questions=["Q20"],
    ),
    GapRecord(
        gap_id="GAP-004",
        reference="Voltage sensor calibration interval",
        referenced_in=[],
        section="Q20 premise",
        gap_type="missing_data",
        description=(
            "Q20 asks about the calibration interval of 'the electrical diagram's voltage "
            "sensor'. No voltage sensor is present in AEG-DWG-E02 or any other source. "
            "The question may have a false premise. "
            "Voltage-related hits in corpus: Q1 (480V disconnect), T1 (480:120V transformer), "
            "Sensor Loop Power 24VDC — all power distribution components, not measurement sensors. "
            "No VT (voltage transducer) appears in AEG-CR-700 (component register)."
        ),
        affects_questions=["Q20"],
    ),
]
