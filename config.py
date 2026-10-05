"""
Central configuration for the Aegis KB pipeline.
"""
import os

# Base paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)
DATASET_ROOT = os.path.join(WORKSPACE_ROOT, "task-data", "aegis-dataset", "aegis-dataset")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
RAW_EXTRACTIONS_DIR = os.path.join(OUTPUT_DIR, "raw_extractions")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")

# Ensure output dirs exist
for d in [OUTPUT_DIR, RAW_EXTRACTIONS_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)

# File manifest — every file in the dataset, with metadata
FILE_MANIFEST = [
    # Manuals (Trust Tier 1 — Official)
    {"path": "manuals/operator_manual.pdf",           "format": "pdf",         "trust_tier": 1, "trust_label": "official_manual",    "notes": "AEG-OM-700 Rev 4, born-digital"},
    {"path": "manuals/maintenance_manual.pdf",         "format": "pdf",         "trust_tier": 1, "trust_label": "official_manual",    "notes": "AEG-MM-700 Rev 3, born-digital"},
    {"path": "manuals/legacy_manual_v1.html",          "format": "html",        "trust_tier": 1, "trust_label": "official_manual",    "notes": "AEG-OM-700 Rev 1, SUPERSEDED by Rev 4 for sw >= 3.2"},
    
    # Engineering Bulletins (Trust Tier 2 — ECN/Bulletin)
    {"path": "engineering_bulletins/ECN-1042.pdf",     "format": "pdf",         "trust_tier": 2, "trust_label": "ecn_bulletin",       "notes": "PS-04→PS-04A, 180→200 bar, effective rev 3.2"},
    {"path": "engineering_bulletins/ECN-1058.pdf",     "format": "pdf",         "trust_tier": 2, "trust_label": "ecn_bulletin",       "notes": "A17 text correction, clarifies/references ECN-1042 (NOT supersession)"},
    
    # Reference (Trust Tier 1 for register/glossary, Tier 3 for revision history)
    {"path": "reference/alarm_reference.pdf",          "format": "pdf",         "trust_tier": 1, "trust_label": "official_manual",    "notes": "AEG-AL-700 Rev 5, alarm table with merged cells"},
    {"path": "reference/component_register.xlsx",      "format": "xlsx",        "trust_tier": 1, "trust_label": "official_manual",    "notes": "AEG-CR-700, component IDs/aliases/locations"},
    {"path": "reference/terminology_glossary.docx",    "format": "docx",        "trust_tier": 1, "trust_label": "official_manual",    "notes": "AEG-GL-700 Rev 2, INCOMPLETE (missing HP unit, PS-04)"},
    {"path": "reference/revision_history.xlsx",        "format": "xlsx",        "trust_tier": 3, "trust_label": "revision_history",   "notes": "SW revision timeline 3.0→3.3(planned)"},
    
    # Diagrams (Trust Tier 1 — Official, but extraction is LOW confidence)
    {"path": "diagrams/system_diagram_hydraulic.pdf",  "format": "pdf_diagram", "trust_tier": 1, "trust_label": "official_manual",    "notes": "AEG-DWG-H01, topology from shapes"},
    {"path": "diagrams/system_diagram_electrical.png", "format": "png_diagram", "trust_tier": 1, "trust_label": "official_manual",    "notes": "AEG-DWG-E02, raster, partial low-contrast labels"},
    {"path": "diagrams/wiring_diagram.pdf",            "format": "pdf_diagram", "trust_tier": 1, "trust_label": "official_manual",    "notes": "AEG-DWG-W03, cross-references TB-7/J-14/J-15"},
    
    # Screenshots (Trust Tier 4 — Config Export)
    {"path": "screenshots/screen_01_home.png",         "format": "png_screenshot", "trust_tier": 4, "trust_label": "config_export",   "notes": "HMI home screen, SW REV 3.2"},
    {"path": "screenshots/screen_02_alarms.png",       "format": "png_screenshot", "trust_tier": 4, "trust_label": "config_export",   "notes": "HMI alarm list screen"},
    {"path": "screenshots/screen_03_diagnostics.png",  "format": "png_screenshot", "trust_tier": 4, "trust_label": "config_export",   "notes": "HMI diagnostics, sensor tag P.S.04-A"},
    
    # Scans (Trust Tier 1 — Official, but OCR quality varies)
    {"path": "scans/scanned_appendix_calibration.pdf", "format": "scanned_pdf", "trust_tier": 1, "trust_label": "official_manual",    "notes": "Scanned, skewed, needs OCR"},
    
    # Configuration (Trust Tier 4 — Config Export)
    {"path": "configuration/configuration_export.json","format": "json",        "trust_tier": 4, "trust_label": "config_export",      "notes": "PLC-03 config dump, keys differ from manual terminology"},
    
    # Low Trust (Trust Tier 6 — Field Notes)
    {"path": "low_trust/site_survey_notes.docx",       "format": "docx",        "trust_tier": 6, "trust_label": "field_notes",        "notes": "Informal, unreviewed, contradicts manual values"},
    
    # Noise (Trust Tier 7 — Irrelevant/Noise)
    {"path": "noise/safety_data_sheet_hydraulic_fluid.pdf", "format": "pdf",    "trust_tier": 7, "trust_label": "noise",              "notes": "HydroFluid-32 MSDS, largely irrelevant to Q&A"},
    
    # Extra (Trust Tier 5 — Training Deck)
    {"path": "extra/training_slide_excerpt.pptx",      "format": "pptx",        "trust_tier": 5, "trust_label": "training_deck",      "notes": "3 slides, restates operator manual, mentions Auxiliary Reservoir"},
]

# Known document gaps — referenced but not in the package
KNOWN_GAPS = [
    {"reference": "Section 8 (manual bleed procedure)", "referenced_in": ["manuals/maintenance_manual.pdf (Section 4, Section 7)"], "description": "Manual bleed procedure for reducing pressure below 50 bar before controller reset. Referenced but not included in package."},
    {"reference": "AEG-AL-701 (Electrical Alarm Reference)", "referenced_in": ["reference/alarm_reference.pdf (page 2)"], "description": "Companion alarm reference covering alarms A01-A16 and A20-A34 (electrical, lubrication, communications). Not in package."},
]

# Trust tier labels for display
TRUST_TIER_LABELS = {
    1: "Official Manual/Reference",
    2: "ECN/Engineering Bulletin",
    3: "Revision History",
    4: "Config Export/HMI Screenshot",
    5: "Training Deck",
    6: "Field Notes (Unverified)",
    7: "Noise/Irrelevant",
}

# Tesseract path (Windows default install via choco)
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
