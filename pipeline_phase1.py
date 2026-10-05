"""
Phase 1 pipeline orchestrator — updated with:
  - RapidOCR (model-based) on scanned PDF + PNG files
  - Text normalization (deterministic artifact fixing)
  - Section-based chunking (section_number + section_title + page per block)
  - Automatic unresolved-reference detection
  - OCR vs manual-transcription mismatch report
"""
import io
import sys
# Force UTF-8 stdout on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import os
import json
import time
from datetime import datetime

# Make sure aegis-kb is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import FILE_MANIFEST, DATASET_ROOT, RAW_EXTRACTIONS_DIR, LOGS_DIR, KNOWN_GAPS
from schema import RawExtraction

# Import all parsers
from ingest.pdf_parser import parse_pdf
from ingest.html_parser import parse_html
from ingest.xlsx_parser import parse_xlsx
from ingest.docx_parser import parse_docx
from ingest.pptx_parser import parse_pptx
from ingest.json_parser import parse_json
from ingest.diagram_parser import parse_diagram_pdf
from ingest.ocr_parser import parse_scanned_pdf, parse_png_ocr
from ingest.normalizer import normalize_blocks, normalize_table_data, get_mapping_table
from ingest.ocr_engine import run_all_ocr, MANUAL_TRANSCRIPTIONS
from ingest.reference_detector import (
    detect_unresolved_references, write_reference_report, format_report_markdown
)


def route_parser(filepath: str, file_info: dict) -> RawExtraction:
    """Route a file to the correct parser based on its format."""
    fmt = file_info["format"]
    if fmt == "pdf":
        return parse_pdf(filepath, file_info)
    elif fmt in ("pdf_diagram",):
        return parse_diagram_pdf(filepath, file_info)
    elif fmt == "html":
        return parse_html(filepath, file_info)
    elif fmt == "xlsx":
        return parse_xlsx(filepath, file_info)
    elif fmt == "docx":
        return parse_docx(filepath, file_info)
    elif fmt == "pptx":
        return parse_pptx(filepath, file_info)
    elif fmt == "json":
        return parse_json(filepath, file_info)
    elif fmt == "scanned_pdf":
        return parse_scanned_pdf(filepath, file_info)
    elif fmt in ("png_diagram", "png_screenshot"):
        return parse_png_ocr(filepath, file_info)
    else:
        extraction = RawExtraction(
            source_file=file_info["path"],
            file_format=fmt,
            trust_tier=file_info["trust_tier"],
            trust_label=file_info["trust_label"],
        )
        extraction.failures.append(f"No parser registered for format: {fmt}")
        extraction.overall_confidence = 0.0
        return extraction


def apply_normalization(extraction: RawExtraction) -> int:
    """Apply text normalization to all blocks and tables. Returns artifact count."""
    _, block_artifacts = normalize_blocks(extraction.content_blocks)
    table_artifacts = normalize_table_data(extraction.tables)
    return block_artifacts + table_artifacts


def run_phase1(run_ocr: bool = True):
    """Run the full Phase 1 pipeline."""
    print("=" * 80)
    print("AEGIS KB — PHASE 1 (v2): PARSERS + NORMALIZATION + OCR + REFERENCE DETECTION")
    print(f"Started: {datetime.utcnow().isoformat()}Z")
    print("=" * 80)
    print()

    results = []
    failures = []
    total_artifacts = 0

    for file_info in FILE_MANIFEST:
        rel_path = file_info["path"]
        abs_path = os.path.join(DATASET_ROOT, rel_path.replace("/", os.sep))

        print(f"  Processing: {rel_path}")
        t0 = time.time()

        if not os.path.isfile(abs_path):
            print(f"    ERROR: File not found: {abs_path}")
            extraction = RawExtraction(
                source_file=rel_path, file_format=file_info["format"],
                trust_tier=file_info["trust_tier"], trust_label=file_info["trust_label"],
            )
            extraction.failures.append(f"File not found: {abs_path}")
            extraction.overall_confidence = 0.0
            results.append(extraction)
            failures.append(rel_path)
            continue

        try:
            extraction = route_parser(abs_path, file_info)
        except Exception as e:
            import traceback
            extraction = RawExtraction(
                source_file=rel_path, file_format=file_info["format"],
                trust_tier=file_info["trust_tier"], trust_label=file_info["trust_label"],
            )
            extraction.failures.append(
                f"Unhandled exception: {str(e)}\n{traceback.format_exc()}"
            )
            extraction.overall_confidence = 0.0

        # Apply text normalization to every extraction
        artifacts = apply_normalization(extraction)
        total_artifacts += artifacts
        if artifacts:
            extraction.metadata["normalization_artifacts_fixed"] = artifacts

        elapsed = time.time() - t0
        extraction.metadata["parse_time_seconds"] = round(elapsed, 3)
        extraction.metadata["file_notes"] = file_info.get("notes", "")

        # Write per-file JSON dump
        safe_name = rel_path.replace("/", "__").replace("\\", "__").replace(".", "_")
        out_path = os.path.join(RAW_EXTRACTIONS_DIR, f"{safe_name}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(extraction.to_json())

        status = "OK" if not extraction.failures else "FAIL"
        print(
            f"    [{status}] conf={extraction.overall_confidence:.2f} | "
            f"blocks={len(extraction.content_blocks)}, tables={len(extraction.tables)}, "
            f"diagrams={len(extraction.diagrams)} | "
            f"artifacts_fixed={artifacts} | "
            f"warnings={len(extraction.warnings)}, failures={len(extraction.failures)} "
            f"({elapsed:.2f}s)"
        )
        if extraction.failures:
            for f_msg in extraction.failures:
                print(f"      FAILURE: {f_msg[:120]}")
            failures.append(rel_path)

        results.append(extraction)

    print(f"\n  Total normalization artifacts fixed: {total_artifacts}")

    # --- Step 2: RapidOCR on scanned/PNG files ---
    print()
    print("--- Running RapidOCR on image/scan files ---")
    ocr_summary = {}
    if run_ocr:
        try:
            ocr_summary = run_all_ocr(DATASET_ROOT, LOGS_DIR)
            print(f"  OCR report written to: {ocr_summary['report_path']}")
        except Exception as e:
            print(f"  OCR step failed: {e}")
            import traceback; traceback.print_exc()
    else:
        print("  (OCR skipped — run_ocr=False)")

    # --- Step 3: Automatic reference detection ---
    print()
    print("--- Running automatic reference detector ---")
    ref_report = detect_unresolved_references(results)
    ref_report_path = os.path.join(LOGS_DIR, "reference_report.json")
    write_reference_report(ref_report, ref_report_path)
    print(f"  References found: {ref_report['total_references_found']}")
    print(f"  Resolved: {ref_report['resolved_count']}")
    print(f"  Unresolved (gaps): {ref_report['unresolved_count']}")
    print(f"  Internal: {ref_report['internal_count']}")
    print(f"  Report: {ref_report_path}")

    # --- Write normalization table documentation ---
    norm_table_path = os.path.join(LOGS_DIR, "normalization_mapping_table.json")
    with open(norm_table_path, "w", encoding="utf-8") as f:
        json.dump(get_mapping_table(), f, indent=2, ensure_ascii=False)

    # --- Build full report ---
    summary = build_summary_report(results, failures, ref_report, ocr_summary)
    report_path = os.path.join(LOGS_DIR, "phase1_extraction_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(summary)

    # Machine-readable summary JSON
    summary_data = [
        {
            "file": r.source_file,
            "format": r.file_format,
            "trust_tier": r.trust_tier,
            "trust_label": r.trust_label,
            "parsers": [s.method.value for s in r.extraction_steps],
            "method_types": [s.method_type.value for s in r.extraction_steps],
            "content_blocks": len(r.content_blocks),
            "tables": len(r.tables),
            "diagrams": len(r.diagrams),
            "has_structured_data": r.structured_data is not None,
            "overall_confidence": r.overall_confidence,
            "normalization_artifacts_fixed": r.metadata.get("normalization_artifacts_fixed", 0),
            "warnings": r.warnings,
            "failures": r.failures,
            "file_notes": r.metadata.get("file_notes", ""),
        }
        for r in results
    ]
    with open(os.path.join(LOGS_DIR, "phase1_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    print()
    print("=" * 80)
    print(f"PHASE 1 COMPLETE: {len(results)} files, {len(failures)} failures, "
          f"{total_artifacts} normalization artifacts fixed")
    print(f"  Reports: {LOGS_DIR}")
    print("=" * 80)

    print()
    print(summary)
    return results


def build_summary_report(results, failures, ref_report, ocr_summary):
    """Build the per-file extraction summary markdown report."""
    lines = []
    lines.append("# Phase 1 Extraction Report (v2) — Aegis KB\n")
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z\n")
    lines.append(
        f"Files: {len(results)} | Failures: {len(failures)} | "
        f"Unresolved refs: {ref_report.get('unresolved_count', '?')}\n"
    )

    # Per-file table
    lines.append("## Per-File Extraction Summary\n")
    lines.append(
        "| File | Format | Trust | Parser(s) | Blocks | Tables | Diag | Conf | "
        "Artifacts Fixed | Warnings | Failures |"
    )
    lines.append(
        "|------|--------|-------|-----------|--------|--------|------|------|"
        "----------------|----------|----------|"
    )
    for r in results:
        parsers = ", ".join(s.method.value for s in r.extraction_steps[:2]) or "none"
        lines.append(
            f"| `{r.source_file}` | {r.file_format} | T{r.trust_tier} | {parsers} | "
            f"{len(r.content_blocks)} | {len(r.tables)} | {len(r.diagrams)} | "
            f"{r.overall_confidence:.2f} | "
            f"{r.metadata.get('normalization_artifacts_fixed', 0)} | "
            f"{len(r.warnings)} | {len(r.failures)} |"
        )

    lines.append("")

    # OCR mismatch report
    lines.append("## OCR vs Manual Transcription Mismatch Report\n")
    ocr_results = ocr_summary.get("results", [])
    if ocr_results:
        lines.append("| File | OCR Avg Conf | Similarity | Mismatch Rate | Words (OCR) | Words (Ref) |")
        lines.append("|------|-------------|------------|---------------|-------------|-------------|")
        for res in ocr_results:
            mm = res.get("mismatch", {})
            lines.append(
                f"| `{res['file']}` | {res['avg_confidence']:.3f} | "
                f"{mm.get('similarity', 'N/A')} | {mm.get('mismatch_rate', 'N/A')} | "
                f"{mm.get('ocr_word_count', '?')} | {mm.get('reference_word_count', '?')} |"
            )
        lines.append("")
        # Overall mismatch rate
        rates = [r["mismatch"].get("mismatch_rate", 0)
                 for r in ocr_results if r.get("mismatch")]
        if rates:
            avg_mm = sum(rates) / len(rates)
            lines.append(f"**Average mismatch rate across all OCR files: {avg_mm:.4f}**\n")
    else:
        lines.append("_OCR not run or no results._\n")

    # Reference resolution
    lines.append("## Automatic Reference Resolution\n")
    lines.append(
        f"Total references detected: {ref_report.get('total_references_found', 0)} | "
        f"Resolved: {ref_report.get('resolved_count', 0)} | "
        f"**Unresolved (gaps): {ref_report.get('unresolved_count', 0)}** | "
        f"Internal: {ref_report.get('internal_count', 0)}\n"
    )
    unresolved = ref_report.get("unresolved", [])
    if unresolved:
        lines.append("### Unresolved References (Gaps)\n")
        lines.append("| Type | Value | Source File | Also Referenced From | Snippet |")
        lines.append("|------|-------|-------------|----------------------|---------|")
        for ref in unresolved:
            also = ""
            if "also_in" in ref:
                srcs = ", ".join(a["source_file"] for a in ref["also_in"][:2])
                also = f"{srcs}"
            snippet = ref["snippet"].replace("|", "\\|")[:50]
            lines.append(
                f"| {ref['type']} | `{ref['value']}` | "
                f"`{ref['source_file']}` | {also} | …{snippet}… |"
            )
        lines.append("")

    # Detailed per-file breakdown
    lines.append("## Detailed Per-File Breakdown\n")
    for r in results:
        lines.append(f"### `{r.source_file}`")
        lines.append(f"- **Format:** {r.file_format} | **Trust:** T{r.trust_tier} — {r.trust_label}")
        for step in r.extraction_steps[:3]:
            lines.append(
                f"- **Parser:** `{step.method.value}` ({step.method_type.value})"
            )
        lines.append(
            f"- **Extracted:** {len(r.content_blocks)} blocks, "
            f"{len(r.tables)} tables, {len(r.diagrams)} diagrams"
        )
        lines.append(f"- **Conf:** {r.overall_confidence:.2f} | "
                     f"**Artifacts fixed:** {r.metadata.get('normalization_artifacts_fixed', 0)}")
        for w in r.warnings:
            lines.append(f"- WARNING: {w}")
        for f_msg in r.failures:
            lines.append(f"- FAILURE: {f_msg[:200]}")
        lines.append(f"- **Notes:** {r.metadata.get('file_notes', 'none')}")
        lines.append("")

    # Method classification
    lines.append("## Extraction Method Classification\n")
    lines.append("| Method | Type | Reason |")
    lines.append("|--------|------|--------|")
    seen = set()
    for r in results:
        for step in r.extraction_steps:
            key = (step.method.value, step.method_type.value)
            if key not in seen:
                seen.add(key)
                lines.append(
                    f"| `{step.method.value}` | **{step.method_type.value}** | "
                    f"{step.reason[:100]}... |"
                )

    # Q20 note
    lines.append("")
    lines.append("## Q20 Investigation: Voltage Sensor in Electrical Diagram\n")
    lines.append(
        "**Finding:** The electrical schematic (AEG-DWG-E02 / system_diagram_electrical.png) "
        "contains NO component labeled 'voltage sensor'. "
        "Components present: MAIN DISCONNECT Q1, CONTROL XFMR T1 (480:120V), "
        "PLC-03 24VDC POWER SUPPLY, PLC-03 I/O RACK, E-STOP SAFETY RELAY KA1, "
        "SENSOR LOOP POWER 24VDC (feeds pressure transducer loop), IV-21 VALVE DRIVER.\n"
    )
    lines.append(
        "The only calibration record in the package is Appendix C (scanned_appendix_calibration.pdf) "
        "which covers PS-04A (pressure sensor), not any voltage sensor. "
        "**Q20 must be answered: 'not found in sources — no voltage sensor exists in "
        "the electrical diagram or any calibration record in this package.'**\n"
    )

    # Known gaps
    lines.append("## Known Gaps (Referenced But Not In Package)\n")
    for gap in KNOWN_GAPS:
        lines.append(f"- **{gap['reference']}**")
        lines.append(f"  - Referenced in: {', '.join(gap['referenced_in'])}")
        lines.append(f"  - Description: {gap['description']}")
    lines.append("")

    if failures:
        lines.append("## Failed Extractions\n")
        for f in failures:
            lines.append(f"- `{f}`")

    return "\n".join(lines)


if __name__ == "__main__":
    run_phase1(run_ocr=True)
