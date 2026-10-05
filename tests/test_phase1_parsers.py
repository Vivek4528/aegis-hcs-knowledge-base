"""
Unit tests for Phase 1 (v2).
Run with: python -m pytest tests/ -v

Test inventory (27 tests across 7 classes):
---
TestFileManifestCompleteness (4 tests)
  1.  test_all_files_exist               — every path in FILE_MANIFEST resolves to a real file
  2.  test_manifest_has_20_entries        — exactly 20 files declared (dataset spec)
  3.  test_trust_tiers_in_range          — all trust_tier values are 1–7
  4.  test_no_duplicate_paths            — no two manifest entries share the same path

TestParserRouting (8 tests)
  5.  test_pdf_routes_and_extracts       — pdf format → parse_pdf → blocks > 0, conf >= 0.9
  6.  test_xlsx_produces_table           — xlsx format → parse_xlsx → at least 1 table
  7.  test_json_populates_structured     — json format → parse_json → structured_data not None
  8.  test_html_extracts_blocks          — html format → parse_html → blocks > 0
  9.  test_docx_extracts_blocks          — docx format → parse_docx → blocks > 0
  10. test_pptx_extracts_blocks          — pptx format → parse_pptx → blocks > 0
  11. test_diagram_pdf_low_confidence    — pdf_diagram format → diagrams > 0, conf < 0.6
  12. test_noise_file_tagged_t7          — noise file is parsed AND trust_tier == 7

TestExtractionOutputIntegrity (4 tests)
  13. test_raw_extractions_dir_exists    — output/raw_extractions/ directory exists after run
  14. test_at_least_19_jsons_written     — ≥19 JSON files written (20 - 0 expected failures)
  15. test_all_jsons_valid               — every JSON file parses cleanly and has required keys
  16. test_t1_pdfs_have_high_confidence  — T1 official PDFs must have conf ≥ 0.9

TestTextNormalization (5 tests)
  17. test_em_dash_artifact              — "ù" → "—" replacement
  18. test_arrow_ligature_artifact       — " fi " → " → " replacement
  19. test_cid_bullet_artifact           — "(cid:127)" → "•" replacement
  20. test_generic_cid_fallback          — any (cid:NNN) not in table → "[CID?]" marker
  21. test_normalize_table_data          — normalize_table_data() cleans XLSX/table cell values

TestSectionChunking (3 tests)
  22. test_pdf_blocks_have_section       — after parse_pdf, each block has a .section attribute
  23. test_section_num_extracted         — section field contains the detected section number
  24. test_heading_block_type            — numbered headings are classified block_type="heading"

TestKnownGapsAndReferences (2 tests)
  25. test_reference_report_exists       — reference_report.json written after pipeline run
  26. test_section8_unresolved           — Section 8 appears in unresolved list with source(s)

TestOCRLabeling (1 test)
  27. test_ocr_steps_labeled_model_based — every OCR extraction step is method_type=model_based
"""
import os
import sys
import json
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import FILE_MANIFEST, DATASET_ROOT
from ingest.normalizer import normalize, normalize_table_data
from schema import TableData


# ============================================================================
class TestFileManifestCompleteness(unittest.TestCase):
    """Tests 1–4: FILE_MANIFEST integrity."""

    def test_all_files_exist(self):
        """Test 1: every path in FILE_MANIFEST resolves to a real file on disk."""
        missing = []
        for fi in FILE_MANIFEST:
            abs_path = os.path.join(DATASET_ROOT, fi["path"].replace("/", os.sep))
            if not os.path.isfile(abs_path):
                missing.append(fi["path"])
        self.assertEqual(missing, [], f"Missing files: {missing}")

    def test_manifest_has_20_entries(self):
        """Test 2: exactly 20 files declared (per dataset specification)."""
        self.assertEqual(len(FILE_MANIFEST), 20)

    def test_trust_tiers_in_range(self):
        """Test 3: all trust_tier values are integers in range 1–7."""
        for fi in FILE_MANIFEST:
            self.assertIn(fi["trust_tier"], range(1, 8),
                          f"Trust tier out of range for {fi['path']}")

    def test_no_duplicate_paths(self):
        """Test 4: no two manifest entries share the same relative path."""
        paths = [fi["path"] for fi in FILE_MANIFEST]
        self.assertEqual(len(paths), len(set(paths)), "Duplicate paths in manifest")


# ============================================================================
class TestParserRouting(unittest.TestCase):
    """Tests 5–12: correct parser dispatched and output shape verified."""

    def _route(self, format_filter=None, path_substr=None):
        from pipeline_phase1 import route_parser
        fi = next(
            f for f in FILE_MANIFEST
            if (format_filter is None or f["format"] == format_filter)
            and (path_substr is None or path_substr in f["path"])
        )
        abs_path = os.path.join(DATASET_ROOT, fi["path"].replace("/", os.sep))
        return route_parser(abs_path, fi), fi

    def test_pdf_routes_and_extracts(self):
        """Test 5: pdf format → parse_pdf; content blocks extracted, conf ≥ 0.9."""
        result, _ = self._route("pdf", "operator_manual")
        self.assertGreater(len(result.content_blocks), 0)
        self.assertGreaterEqual(result.overall_confidence, 0.9)

    def test_xlsx_produces_table(self):
        """Test 6: xlsx format → parse_xlsx; at least one table object produced."""
        result, _ = self._route("xlsx")
        self.assertGreater(len(result.tables), 0, "XLSX should produce at least one table")

    def test_json_populates_structured(self):
        """Test 7: json format → parse_json; structured_data dict populated."""
        result, _ = self._route("json")
        self.assertIsNotNone(result.structured_data)
        self.assertIn("sensors", result.structured_data)

    def test_html_extracts_blocks(self):
        """Test 8: html format → parse_html; content blocks > 0."""
        result, _ = self._route("html")
        self.assertGreater(len(result.content_blocks), 0)

    def test_docx_extracts_blocks(self):
        """Test 9: docx format → parse_docx; content blocks > 0."""
        result, _ = self._route("docx")
        self.assertGreater(len(result.content_blocks), 0)

    def test_pptx_extracts_blocks(self):
        """Test 10: pptx format → parse_pptx; content blocks > 0."""
        result, _ = self._route("pptx")
        self.assertGreater(len(result.content_blocks), 0)

    def test_diagram_pdf_low_confidence(self):
        """Test 11: pdf_diagram → diagrams > 0 AND confidence < 0.6 (topology is LOW conf)."""
        result, _ = self._route("pdf_diagram", "hydraulic")
        self.assertGreater(len(result.diagrams), 0)
        for diag in result.diagrams:
            self.assertLess(diag.confidence, 0.6,
                            "Diagram topology must be LOW confidence")

    def test_noise_file_tagged_t7(self):
        """Test 12: noise file is parsed AND trust_tier == 7 (not filtered pre-parse)."""
        result, _ = self._route("pdf", "safety_data")
        self.assertEqual(result.trust_tier, 7)
        self.assertEqual(result.trust_label, "noise")
        self.assertGreater(result.overall_confidence, 0)


# ============================================================================
class TestExtractionOutputIntegrity(unittest.TestCase):
    """Tests 13–16: written JSON dump files are valid and complete."""

    @property
    def raw_dir(self):
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "output", "raw_extractions"
        )

    def test_raw_extractions_dir_exists(self):
        """Test 13: output/raw_extractions/ directory exists after pipeline run."""
        self.assertTrue(os.path.isdir(self.raw_dir))

    def test_at_least_19_jsons_written(self):
        """Test 14: ≥19 JSON dumps written (all 20 files, 0 expected hard failures)."""
        files = [f for f in os.listdir(self.raw_dir) if f.endswith(".json")]
        self.assertGreaterEqual(len(files), 19)

    def test_all_jsons_valid(self):
        """Test 15: every JSON dump parses cleanly and has required schema keys."""
        files = [f for f in os.listdir(self.raw_dir) if f.endswith(".json")]
        for fname in files:
            fpath = os.path.join(self.raw_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            for key in ("source_file", "overall_confidence", "content_blocks",
                        "tables", "extraction_steps"):
                self.assertIn(key, data, f"Missing key '{key}' in {fname}")

    def test_t1_pdfs_have_high_confidence(self):
        """Test 16: T1 born-digital PDFs must have overall_confidence ≥ 0.9."""
        files = [f for f in os.listdir(self.raw_dir) if f.endswith(".json")]
        for fname in files:
            with open(os.path.join(self.raw_dir, fname), encoding="utf-8") as f:
                data = json.load(f)
            if data["trust_tier"] == 1 and data["file_format"] == "pdf":
                self.assertGreaterEqual(
                    data["overall_confidence"], 0.9,
                    f"T1 PDF {data['source_file']} has low conf: {data['overall_confidence']}"
                )


# ============================================================================
class TestTextNormalization(unittest.TestCase):
    """Tests 17–21: encoding artifact detection and replacement."""

    def test_em_dash_artifact(self):
        """Test 17: 'ù' (Latin-1 font substitution) is replaced with em-dash '—'."""
        raw = "Normal operating pressure is 180 bar ù see ECN-1042"
        result = normalize(raw)
        self.assertNotIn("ù", result)
        self.assertIn("—", result)

    def test_arrow_ligature_artifact(self):
        """Test 18: ' fi ' (PDF fi-ligature used as arrow) is replaced with ' → '."""
        raw = "PS-04 fi PS-04A sensor replacement"
        result = normalize(raw)
        self.assertNotIn(" fi ", result)
        self.assertIn("→", result)

    def test_cid_bullet_artifact(self):
        """Test 19: '(cid:127)' (unmapped bullet code point) is replaced with '•'."""
        raw = "(cid:127) Hydraulic fluid level is within the normal band."
        result = normalize(raw)
        self.assertNotIn("(cid:127)", result)
        self.assertIn("•", result)

    def test_generic_cid_fallback(self):
        """Test 20: any (cid:NNN) not in specific table is replaced with '[CID?]' marker."""
        raw = "Some text with (cid:999) unknown code point"
        result = normalize(raw)
        self.assertNotIn("(cid:999)", result)
        self.assertIn("[CID?]", result)

    def test_normalize_table_data(self):
        """Test 21: normalize_table_data() cleans artifacts in XLSX/table cell values."""
        table = TableData(
            headers=["Component", "Status ù Note"],
            rows=[["PS-04 fi PS-04A", "Active (cid:127) check OK"]],
        )
        count = normalize_table_data([table])
        self.assertGreater(count, 0, "Expected at least one artifact fixed in table")
        self.assertNotIn("ù", table.headers[1])
        self.assertNotIn(" fi ", table.rows[0][0])
        self.assertNotIn("(cid:127)", table.rows[0][1])


# ============================================================================
class TestSectionChunking(unittest.TestCase):
    """Tests 22–24: section-based chunking in PDF parser."""

    def _parse_operator_manual(self):
        from pipeline_phase1 import route_parser
        fi = next(f for f in FILE_MANIFEST if "operator_manual" in f["path"])
        abs_path = os.path.join(DATASET_ROOT, fi["path"].replace("/", os.sep))
        return route_parser(abs_path, fi)

    def test_pdf_blocks_have_section(self):
        """Test 22: after parse_pdf, every non-empty block has a .section attribute."""
        result = self._parse_operator_manual()
        for block in result.content_blocks:
            # section may be empty string for preamble content, but attribute must exist
            self.assertIsNotNone(block.section,
                                 f"Block missing .section: '{block.text[:40]}'")

    def test_section_num_extracted(self):
        """Test 23: at least one block's .section starts with a digit (e.g. '1 Overview')."""
        result = self._parse_operator_manual()
        numbered = [b for b in result.content_blocks
                    if b.section and b.section[:1].isdigit()]
        self.assertGreater(len(numbered), 0,
                           "Expected at least one block with numbered section")

    def test_heading_block_type(self):
        """Test 24: numbered section lines are classified block_type='heading'."""
        result = self._parse_operator_manual()
        headings = [b for b in result.content_blocks if b.block_type == "heading"]
        self.assertGreater(len(headings), 0,
                           "Expected at least one 'heading' block from operator manual")


# ============================================================================
class TestKnownGapsAndReferences(unittest.TestCase):
    """Tests 25–26: automatic reference detection and gap reporting."""

    @property
    def logs_dir(self):
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "output", "logs"
        )

    def test_reference_report_exists(self):
        """Test 25: reference_report.json is written after pipeline run."""
        report_path = os.path.join(self.logs_dir, "reference_report.json")
        self.assertTrue(os.path.isfile(report_path),
                        "reference_report.json not found — run pipeline_phase1.py first")

    def test_section8_unresolved(self):
        """Test 26: Section 8 appears as unresolved in the reference report."""
        report_path = os.path.join(self.logs_dir, "reference_report.json")
        if not os.path.isfile(report_path):
            self.skipTest("reference_report.json not found")
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
        unresolved_values = [r["value"] for r in report.get("unresolved", [])]
        self.assertIn("8", unresolved_values,
                      f"Section 8 not in unresolved list. Got: {unresolved_values}")


# ============================================================================
class TestOCRLabeling(unittest.TestCase):
    """Test 27: OCR extraction steps must be labeled model_based, not deterministic."""

    def test_ocr_steps_labeled_model_based(self):
        """Test 27: png_screenshot and scanned_pdf parsers emit model_based steps only."""
        from pipeline_phase1 import route_parser
        ocr_formats = ("png_screenshot", "png_diagram", "scanned_pdf")
        for fi in FILE_MANIFEST:
            if fi["format"] not in ocr_formats:
                continue
            abs_path = os.path.join(DATASET_ROOT, fi["path"].replace("/", os.sep))
            result = route_parser(abs_path, fi)
            for step in result.extraction_steps:
                self.assertEqual(
                    step.method_type.value, "model_based",
                    f"OCR step in {fi['path']} is labeled '{step.method_type.value}' "
                    f"but must be 'model_based'. Step: {step.step_name}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
