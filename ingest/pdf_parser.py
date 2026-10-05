"""
Born-digital PDF parser using pdfplumber.

Extraction type: DETERMINISTIC — pdfplumber uses precise PDF object parsing.
Table extraction uses ruled-line detection (RULE-BASED).

Section chunking: content is chunked by heading (detected by font size or
numbered prefix), not by page boundary. Each block carries:
  - section_number (e.g. "4.3")
  - section_title  (e.g. "Starting the Hydraulic Power Unit")
  - page

Text normalization is applied after extraction via ingest.normalizer.
"""
import re
import pdfplumber
from ingest.normalizer import normalize, normalize_blocks, normalize_table_data
from schema import (
    RawExtraction, ContentBlock, TableData, ExtractionStep,
    ExtractionMethod, MethodType
)

# Heading detection: numbered section like "4.3 Starting the HPU" or "1. Overview"
_SECTION_NUM_RE = re.compile(
    r'^(\d+(?:\.\d+)*)[\.\s]+(.+)$'
)


def parse_pdf(filepath: str, file_info: dict) -> RawExtraction:
    """Parse a born-digital PDF using pdfplumber with section-based chunking."""
    extraction = RawExtraction(
        source_file=file_info["path"],
        file_format="pdf",
        trust_tier=file_info["trust_tier"],
        trust_label=file_info["trust_label"],
    )

    extraction.extraction_steps.append(ExtractionStep(
        step_name="text_extraction",
        method=ExtractionMethod.PDFPLUMBER_TEXT,
        method_type=MethodType.DETERMINISTIC,
        reason="pdfplumber parses PDF text objects directly from file structure; "
               "no OCR or ML. Deterministic: same input always gives same output."
    ))
    extraction.extraction_steps.append(ExtractionStep(
        step_name="text_normalization",
        method=ExtractionMethod.PDFPLUMBER_TEXT,  # same step, normalization pass
        method_type=MethodType.DETERMINISTIC,
        reason="Rule-based artifact replacement from NORMALIZATION_TABLE "
               "(ù→—, fi→→, (cid:N)→bullet). Deterministic mapping, no ML."
    ))

    try:
        with pdfplumber.open(filepath) as pdf:
            extraction.metadata["page_count"] = len(pdf.pages)
            extraction.metadata["pdf_info"] = pdf.metadata or {}

            current_section_num = ""
            current_section_title = ""

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    extraction.warnings.append(
                        f"Page {page_num}: No text extracted (image-only?)"
                    )
                    continue

                # Normalize raw text first
                text = normalize(text)

                # Split into lines for section detection
                lines = text.split("\n")
                current_paragraph_lines = []

                def flush_paragraph():
                    """Save accumulated lines as a content block."""
                    if not current_paragraph_lines:
                        return
                    para_text = " ".join(current_paragraph_lines).strip()
                    if not para_text:
                        return
                    block_type = _classify_block(para_text)
                    extraction.content_blocks.append(ContentBlock(
                        text=para_text,
                        block_type=block_type,
                        page=page_num,
                        section=f"{current_section_num} {current_section_title}".strip(),
                    ))
                    current_paragraph_lines.clear()

                for line in lines:
                    line = line.strip()
                    if not line:
                        flush_paragraph()
                        continue

                    # Detect section heading
                    m = _SECTION_NUM_RE.match(line)
                    if m and _looks_like_heading(line, m):
                        flush_paragraph()
                        current_section_num = m.group(1)
                        current_section_title = m.group(2).strip()
                        extraction.content_blocks.append(ContentBlock(
                            text=line,
                            block_type="heading",
                            page=page_num,
                            section=f"{current_section_num} {current_section_title}".strip(),
                        ))
                    else:
                        current_paragraph_lines.append(line)

                flush_paragraph()

                # Extract tables
                tables = page.extract_tables()
                if tables:
                    extraction.extraction_steps.append(ExtractionStep(
                        step_name=f"table_extraction_page_{page_num}",
                        method=ExtractionMethod.PDFPLUMBER_TABLE,
                        method_type=MethodType.RULE_BASED,
                        reason="Ruled-line detection heuristic to find table cells."
                    ))
                    for table_data in tables:
                        if table_data and len(table_data) > 1:
                            headers = [normalize(str(h or "")).strip() for h in table_data[0]]
                            rows = []
                            for row in table_data[1:]:
                                rows.append([normalize(str(c or "")).strip() for c in row])

                            has_merged = any(
                                "\n" in str(c) for row in table_data for c in row if c
                            )
                            extraction.tables.append(TableData(
                                headers=headers,
                                rows=rows,
                                page=page_num,
                                section=f"{current_section_num} {current_section_title}".strip(),
                                has_merged_cells=has_merged,
                                has_multi_row_headers=has_merged,
                            ))

    except Exception as e:
        extraction.failures.append(f"PDF parsing failed: {str(e)}")
        extraction.overall_confidence = 0.0

    if not extraction.failures:
        extraction.overall_confidence = 0.8 if extraction.warnings else 0.95

    return extraction


def _looks_like_heading(line: str, match) -> bool:
    """
    Heuristic: is this numbered line a section heading or just a numbered list item?
    Rule-based check — not ML.
    """
    section_num = match.group(1)
    title = match.group(2).strip()

    # Section numbers have at most 2 levels (e.g. "4.3" not "4.3.1.2")
    if section_num.count(".") > 2:
        return False
    # Must be under 120 chars
    if len(line) > 120:
        return False
    # Title shouldn't start with lowercase (probably a sentence, not a heading)
    if title and title[0].islower():
        return False
    # Shouldn't end with period (that's a sentence)
    if line.endswith(".") and len(title) > 30:
        return False
    return True


def _classify_block(text: str) -> str:
    """Classify a text block by content. Rule-based."""
    upper = text.strip().upper()
    if upper.startswith("WARNING"):
        return "warning"
    if upper.startswith("NOTE"):
        return "note"
    if upper.startswith("CAUTION"):
        return "caution"
    if text.strip().startswith(("•", "–", "-", "[CID?]")):
        return "list_item"
    if re.match(r'^\d+\s+', text.strip()):
        # Numbered step like "1 Turn the POWER selector..."
        return "ordered_list_item"
    return "paragraph"
