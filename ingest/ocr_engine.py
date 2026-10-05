"""
Real OCR pipeline using RapidOCR (pip-only, no system binaries required).
RapidOCR uses ONNX Runtime with pre-bundled detection + recognition models.

Extraction type: MODEL-BASED
  - Detection model (DBNet): neural network detects text regions
  - Recognition model (CRNN): neural network reads each detected region
  - Not deterministic: confidence scores and minor layout differences may vary
    across ONNX Runtime versions, but text output is stable for clean images.

Used for:
  - scans/scanned_appendix_calibration.pdf  (rendered to image first)
  - diagrams/system_diagram_electrical.png
  - screenshots/screen_01_home.png
  - screenshots/screen_02_alarms.png
  - screenshots/screen_03_diagnostics.png

Cross-check:
  Each OCR result is compared against the manual transcription baseline.
  Mismatches (normalized word-level diff) are recorded in the loss report.
"""

import os
import io
import json
from typing import Optional
from difflib import SequenceMatcher

from schema import (
    RawExtraction, ContentBlock, TableData, ExtractionStep,
    ExtractionMethod, MethodType
)


_rapid_ocr = None


def _get_engine():
    """Lazy-init RapidOCR engine (model download on first call)."""
    global _rapid_ocr
    if _rapid_ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapid_ocr = RapidOCR()
    return _rapid_ocr


def ocr_image_bytes(img_bytes: bytes) -> list:
    """
    Run RapidOCR on raw image bytes.
    Returns list of (bbox, text, confidence) tuples.
    """
    engine = _get_engine()
    result, _ = engine(img_bytes)
    if result is None:
        return []
    # result format: [[bbox_points, text, confidence], ...]
    out = []
    for item in result:
        if len(item) >= 3:
            out.append({
                "bbox": item[0],
                "text": item[1],
                "confidence": float(item[2]),
            })
        elif len(item) == 2:
            out.append({"bbox": item[0], "text": item[1], "confidence": 0.8})
    return out


def ocr_pdf_page(pdf_path: str, page_num: int = 0, dpi: int = 300) -> list:
    """Render a PDF page and run OCR on it."""
    import pymupdf
    doc = pymupdf.open(pdf_path)
    page = doc[page_num]
    mat = pymupdf.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    doc.close()
    return ocr_image_bytes(img_bytes)


def ocr_png_file(png_path: str) -> list:
    """Run OCR on a PNG file directly."""
    with open(png_path, "rb") as f:
        img_bytes = f.read()
    return ocr_image_bytes(img_bytes)


# --------------------------------------------------------------------------
# Mismatch computation
# --------------------------------------------------------------------------

def _words(text: str) -> list:
    """Tokenize to words for comparison."""
    import re
    return re.findall(r"\w+", text.lower())


def compute_mismatch_rate(ocr_text: str, reference_text: str) -> dict:
    """
    Compute word-level similarity between OCR output and manual transcription.
    Returns dict with similarity, mismatch_rate, and details.
    """
    ocr_words = _words(ocr_text)
    ref_words = _words(reference_text)

    if not ref_words:
        return {"similarity": 1.0, "mismatch_rate": 0.0, "note": "empty reference"}

    sm = SequenceMatcher(None, ocr_words, ref_words)
    similarity = sm.ratio()
    mismatch_rate = 1.0 - similarity

    return {
        "similarity": round(similarity, 4),
        "mismatch_rate": round(mismatch_rate, 4),
        "ocr_word_count": len(ocr_words),
        "reference_word_count": len(ref_words),
    }


# --------------------------------------------------------------------------
# Per-file OCR runners
# --------------------------------------------------------------------------

def run_ocr_on_file(filepath: str, file_info: dict,
                    manual_transcription: str = "") -> dict:
    """
    Run RapidOCR on a file and compare to manual transcription.
    Returns a result dict with ocr_text, confidence, mismatch, blocks.
    """
    fname = os.path.basename(filepath)
    result = {
        "file": file_info["path"],
        "ocr_text": "",
        "avg_confidence": 0.0,
        "items": [],
        "mismatch": {},
        "error": None,
    }

    try:
        if file_info["format"] == "scanned_pdf":
            items = ocr_pdf_page(filepath, page_num=0, dpi=300)
        else:
            items = ocr_png_file(filepath)

        result["items"] = items
        texts = [it["text"] for it in items]
        confs = [it["confidence"] for it in items]

        result["ocr_text"] = "\n".join(texts)
        result["avg_confidence"] = round(
            sum(confs) / len(confs) if confs else 0.0, 4
        )

        if manual_transcription:
            result["mismatch"] = compute_mismatch_rate(
                result["ocr_text"], manual_transcription
            )

    except Exception as e:
        result["error"] = str(e)

    return result


# --------------------------------------------------------------------------
# Manual transcriptions for cross-check
# --------------------------------------------------------------------------

MANUAL_TRANSCRIPTIONS = {
    "scanned_appendix_calibration.pdf": (
        "APPENDIX C SENSOR CALIBRATION RECORD "
        "Aegis Series-7 HCS scanned from field service binder uncontrolled copy "
        "Sensor Tag PS-04A Location HPU discharge line "
        "Calibration Date 2026-01-09 Technician R Okafor "
        "Calibration Points Point Reference Reading Result "
        "Zero 0 percent 0 bar 0.1 bar PASS "
        "Mid 50 percent 100 bar 99.6 bar PASS "
        "Span 100 percent 200 bar 199.4 bar PASS "
        "Note this calibration record supersedes the field data sheet used prior to the "
        "PS-04 to PS-04A sensor change see ECN-1042 Span reference target is 200 bar "
        "consistent with the software revision 3.2 operating pressure setpoint "
        "Prior sensor PS-04 span reference target was 180 bar for historical "
        "comparison only Do not use the 180 bar figure to evaluate PS-04A "
        "No calibration interval is specified for PS-04A on this form recalibration "
        "frequency should be confirmed against the applicable maintenance schedule "
        "which is not included in this binder "
        "Signature Date Page 1 of 1 scanned copy quality varies"
    ),
    "screen_01_home.png": (
        "AEGIS SERIES-7 HCS HOME SW REV 3.2 "
        "HPU DISCHARGE PRESSURE 200 bar STATUS RUNNING NORMAL "
        "STARTUP INTERLOCKS "
        "IV-21 Isolation Valve OPEN "
        "Emergency Stop RESET "
        "Maintenance Panel CLOSED "
        "Hydraulic Fluid Level NORMAL "
        "ACTIVE COMPONENT SUMMARY "
        "HP unit PLC-03 controlled RUNNING "
        "PS-04A discharge pressure sensor OK "
        "IV-21 isolation valve OPEN "
        "Touch ALARMS for active historical alarm list "
        "Touch DIAGNOSTICS for sensor-level detail"
    ),
    "screen_02_alarms.png": (
        "AEGIS SERIES-7 HCS ALARM LIST SW REV 3.2 "
        "# TAG DESCRIPTION STATE TIME "
        "1 A17 Hydraulic Pressure Low CLEARED 08:14:02 "
        "2 A19 Pressure Sensor Signal Invalid CLEARED 03-11 22:40 "
        "3 A17 Hydraulic Pressure Low ACTIVE 08:14:57 "
        "4 A18 Hydraulic Pressure High INACTIVE -- "
        "Alarm A17 active for 00:00:14 Shutdown Procedure 4.7 threshold 00:00:10"
    ),
    "screen_03_diagnostics.png": (
        "AEGIS SERIES-7 HCS DIAGNOSTICS SW REV 3.2 "
        "SENSOR DIAGNOSTICS "
        "Tag P.S.04-A "
        "Signal Type 4-20 mA "
        "Raw Reading 14.8 mA "
        "Scaled Value 200.3 bar "
        "Calibration Status WITHIN TOLERANCE "
        "Last Calibrated 2026-01-09 "
        "Firmware Rev 3.2.1 "
        "Note this screen displays the sensor tag as printed on the physical unit label"
    ),
    "system_diagram_electrical.png": (
        "Aegis Series-7 HCS Electrical Schematic AEG-DWG-E02 "
        "Power distribution and interlock wiring "
        "MAIN DISCONNECT Q1 "
        "CONTROL XFMR T1 480:120V "
        "PLC-03 24VDC POWER SUPPLY "
        "PLC-03 I/O RACK "
        "E-STOP SAFETY RELAY KA1 "
        "SENSOR LOOP POWER 24VDC "
        "IV-21 VALVE DRIVER "
        "feeds pressure transducer loop see wiring diagram AEG-DWG-W03 "
        "TB-7 REF PRESSURE XDCR LOOP"
    ),
}


def run_all_ocr(dataset_root: str, output_dir: str) -> dict:
    """
    Run RapidOCR on all image/scan files and produce a mismatch report.
    Returns summary dict.
    """
    import sys
    targets = [
        fi for fi in __import__("config").FILE_MANIFEST
        if fi["format"] in ("scanned_pdf", "png_diagram", "png_screenshot")
    ]

    results = []
    for fi in targets:
        filepath = os.path.join(dataset_root, fi["path"].replace("/", os.sep))
        fname = os.path.basename(filepath)
        manual_ref = MANUAL_TRANSCRIPTIONS.get(fname, "")

        print(f"  OCR: {fi['path']}", flush=True)
        res = run_ocr_on_file(filepath, fi, manual_ref)

        conf = res["avg_confidence"]
        mm = res["mismatch"].get("mismatch_rate", "N/A")
        sim = res["mismatch"].get("similarity", "N/A")
        err = res.get("error", "")
        print(f"    avg_conf={conf:.3f}  mismatch={mm}  similarity={sim}"
              + (f"  ERROR: {err}" if err else ""), flush=True)

        results.append(res)

    # Write report
    report_path = os.path.join(output_dir, "ocr_mismatch_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        # Strip raw bbox arrays (too large) for the summary report
        slim = []
        for r in results:
            slim.append({
                "file": r["file"],
                "avg_confidence": r["avg_confidence"],
                "ocr_word_count": len(_words(r["ocr_text"])),
                "mismatch": r["mismatch"],
                "error": r.get("error"),
                "ocr_text_preview": r["ocr_text"][:500],
            })
        json.dump(slim, f, indent=2, ensure_ascii=False)

    return {"results": results, "report_path": report_path}
