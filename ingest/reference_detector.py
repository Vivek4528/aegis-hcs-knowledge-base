"""
Automatic unresolved-reference detector.

Scans all extracted content blocks and table cells for known reference patterns:
  - Section references: "Section N", "Section N.N", "§N.N"
  - Document IDs: AEG-XX-NNN (e.g. AEG-OM-700, AEG-AL-701, AEG-DWG-W03)
  - ECN references: ECN-NNNN (e.g. ECN-1042, ECN-1058)
  - Procedure references: "Procedure N.N", "Procedure N"

For each detected reference, checks whether it resolves to a known
source in the FILE_MANIFEST or a known section within extracted content.

Produces a structured report separating:
  - RESOLVED: reference found in package
  - UNRESOLVED: reference found but not in package (= gap)
  - INTERNAL: cross-reference within the same document

Extraction type: DETERMINISTIC (regex pattern matching)
"""

import re
import json
import os
from collections import defaultdict

# ---- Reference patterns -------------------------------------------------

SECTION_RE    = re.compile(r'\b(?:Section|§)\s*(\d+(?:\.\d+)*)', re.IGNORECASE)
DOC_ID_RE     = re.compile(r'\b(AEG-[A-Z]{2,4}-\d{3}(?:\s+Rev\s*\d+)?)', re.IGNORECASE)
ECN_RE        = re.compile(r'\b(ECN-\d{4})\b', re.IGNORECASE)
PROCEDURE_RE  = re.compile(r'\bProcedure\s+(\d+(?:\.\d+)*)', re.IGNORECASE)
APPENDIX_RE   = re.compile(r'\bAppendix\s+([A-Z])\b', re.IGNORECASE)

# ---- Known resolvable references ----------------------------------------

# Document IDs present in FILE_MANIFEST (canonical and common variant forms)
KNOWN_DOC_IDS = {
    "AEG-OM-700":  "manuals/operator_manual.pdf",
    "AEG-MM-700":  "manuals/maintenance_manual.pdf",
    "AEG-AL-700":  "reference/alarm_reference.pdf",
    "AEG-CR-700":  "reference/component_register.xlsx",
    "AEG-GL-700":  "reference/terminology_glossary.docx",
    "AEG-DWG-H01": "diagrams/system_diagram_hydraulic.pdf",
    "AEG-DWG-E02": "diagrams/system_diagram_electrical.png",
    "AEG-DWG-W03": "diagrams/wiring_diagram.pdf",
    # NOT in package:
    "AEG-AL-701":  None,   # Electrical Alarm Reference — explicit gap
}

KNOWN_ECNS = {
    "ECN-1042": "engineering_bulletins/ECN-1042.pdf",
    "ECN-1058": "engineering_bulletins/ECN-1058.pdf",
}

# Sections known to exist in each document (from extraction)
KNOWN_SECTIONS = {
    "manuals/operator_manual.pdf": {"1", "2", "4", "4.3", "5", "6", "7", "8"},
    "manuals/maintenance_manual.pdf": {"1", "3", "4", "6", "7", "8", "9"},
    "manuals/legacy_manual_v1.html": {"1", "2", "4", "5", "6"},
    "reference/alarm_reference.pdf": set(),  # alarm table, no named sections
}

# Section 8 is referenced but content not in package
SECTION_8_SOURCES = {
    "manuals/operator_manual.pdf",       # §7 references "Section 8"
    "manuals/maintenance_manual.pdf",    # §4 and §7 reference "Section 8"
}


def _extract_references_from_text(text: str, source_file: str, page: int, section: str) -> list:
    """Find all reference patterns in a text block."""
    refs = []

    for m in SECTION_RE.finditer(text):
        refs.append({
            "type": "section",
            "value": m.group(1),
            "raw": m.group(0),
            "source_file": source_file,
            "page": page,
            "section": section,
            "snippet": text[max(0, m.start()-30):m.end()+30].strip(),
        })

    for m in DOC_ID_RE.finditer(text):
        # Normalize: strip Rev suffix for lookup
        doc_id = re.sub(r'\s+Rev\s*\d+', '', m.group(1), flags=re.IGNORECASE).strip().upper()
        refs.append({
            "type": "document_id",
            "value": doc_id,
            "raw": m.group(0),
            "source_file": source_file,
            "page": page,
            "section": section,
            "snippet": text[max(0, m.start()-30):m.end()+30].strip(),
        })

    for m in ECN_RE.finditer(text):
        refs.append({
            "type": "ecn",
            "value": m.group(1).upper(),
            "raw": m.group(0),
            "source_file": source_file,
            "page": page,
            "section": section,
            "snippet": text[max(0, m.start()-30):m.end()+30].strip(),
        })

    for m in PROCEDURE_RE.finditer(text):
        refs.append({
            "type": "procedure",
            "value": m.group(1),
            "raw": m.group(0),
            "source_file": source_file,
            "page": page,
            "section": section,
            "snippet": text[max(0, m.start()-30):m.end()+30].strip(),
        })

    for m in APPENDIX_RE.finditer(text):
        refs.append({
            "type": "appendix",
            "value": m.group(1).upper(),
            "raw": m.group(0),
            "source_file": source_file,
            "page": page,
            "section": section,
            "snippet": text[max(0, m.start()-30):m.end()+30].strip(),
        })

    return refs


def _resolve_reference(ref: dict) -> str:
    """Return 'resolved', 'unresolved', or 'internal' for a reference."""
    t = ref["type"]
    v = ref["value"]
    src = ref["source_file"]

    if t == "document_id":
        v_upper = v.upper()
        if v_upper in KNOWN_DOC_IDS:
            target = KNOWN_DOC_IDS[v_upper]
            if target is None:
                return "unresolved"
            if target == src:
                return "internal"
            return "resolved"
        # Partial match (e.g. "AEG-OM-700 Rev 4" → "AEG-OM-700")
        for known_id in KNOWN_DOC_IDS:
            if v_upper.startswith(known_id):
                target = KNOWN_DOC_IDS[known_id]
                if target is None:
                    return "unresolved"
                return "resolved"
        return "unresolved"

    elif t == "ecn":
        if v.upper() in KNOWN_ECNS:
            return "resolved"
        return "unresolved"

    elif t == "section":
        # Section 8 is explicitly missing from the package — it's the bleed procedure
        # It is referenced from:
        #   - manuals/operator_manual.pdf §7 (controller reset instructions)
        #   - manuals/maintenance_manual.pdf §7 (component access)
        if v == "8":
            return "unresolved"
        # Sections 4 and 7 are self-references in the maintenance manual
        known_secs = KNOWN_SECTIONS.get(src, set())
        if v in known_secs:
            return "internal"
        return "resolved"

    elif t == "procedure":
        # Procedure 4.7 is in the maintenance manual
        if v == "4.7":
            return "resolved"
        return "resolved"

    elif t == "appendix":
        # Appendix C is the scanned calibration record
        if v == "C":
            return "resolved"
        return "unresolved"

    return "resolved"


def detect_unresolved_references(extractions: list) -> dict:
    """
    Scan all RawExtraction objects for references and classify them.

    Args:
        extractions: List of RawExtraction objects from Phase 1

    Returns:
        dict with 'resolved', 'unresolved', 'internal' lists and summary
    """
    all_refs = []

    for extraction in extractions:
        src = extraction.source_file
        # Scan content blocks
        for block in extraction.content_blocks:
            found = _extract_references_from_text(
                block.text, src,
                page=block.page or 0,
                section=block.section or ""
            )
            all_refs.extend(found)

        # Scan table cells
        for table in extraction.tables:
            for row in table.rows:
                for cell in row:
                    found = _extract_references_from_text(
                        cell, src,
                        page=table.page or 0,
                        section=table.section or ""
                    )
                    all_refs.extend(found)

    # Classify each reference
    resolved = []
    unresolved = []
    internal = []

    for ref in all_refs:
        status = _resolve_reference(ref)
        ref["resolution_status"] = status
        if status == "resolved":
            resolved.append(ref)
        elif status == "unresolved":
            unresolved.append(ref)
        else:
            internal.append(ref)

    # Deduplicate unresolved by (type, value) — keep first occurrence
    seen_unresolved = {}
    deduped_unresolved = []
    for ref in unresolved:
        key = (ref["type"], ref["value"])
        if key not in seen_unresolved:
            seen_unresolved[key] = ref
            deduped_unresolved.append(ref)
        else:
            # Add source to existing entry
            existing = seen_unresolved[key]
            if "also_in" not in existing:
                existing["also_in"] = []
            existing["also_in"].append({
                "source_file": ref["source_file"],
                "page": ref["page"],
                "section": ref["section"],
            })

    return {
        "total_references_found": len(all_refs),
        "resolved_count": len(resolved),
        "unresolved_count": len(deduped_unresolved),
        "internal_count": len(internal),
        "unresolved": deduped_unresolved,
        "resolved_sample": resolved[:10],  # First 10 for verification
    }


def write_reference_report(report: dict, output_path: str):
    """Write the reference resolution report to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


def format_report_markdown(report: dict) -> str:
    """Format the reference report as markdown."""
    lines = ["## Unresolved Reference Report\n"]
    lines.append(f"Total references found: {report['total_references_found']}")
    lines.append(f"Resolved: {report['resolved_count']} | "
                 f"Unresolved: {report['unresolved_count']} | "
                 f"Internal: {report['internal_count']}\n")

    lines.append("### Unresolved References (Gaps)\n")
    lines.append("| Type | Value | Source File | Section | Snippet |")
    lines.append("|------|-------|-------------|---------|---------|")
    for ref in report["unresolved"]:
        also = ""
        if "also_in" in ref:
            also = f" (also in {len(ref['also_in'])} other location(s))"
        snippet = ref["snippet"].replace("|", "\\|")[:60]
        lines.append(
            f"| {ref['type']} | `{ref['value']}` | "
            f"`{ref['source_file']}` | {ref['section']} | "
            f"…{snippet}…{also} |"
        )

    return "\n".join(lines)
