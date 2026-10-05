"""
Text normalization for extraction artifacts.

PDFs often emit garbled Unicode due to font substitution, encoding issues,
or PDF ligature tables. This module provides a deterministic mapping table
to fix known artifacts before storing content blocks.

All normalization steps are DETERMINISTIC and RULE-BASED:
  - Input: raw string from any parser
  - Output: clean UTF-8 string
  - Method: ordered string replacements from a fixed mapping table
  - Why rule-based: the artifact patterns are finite and document-specific;
    no ML needed or appropriate.

Mapping table source: empirically derived from pdfplumber output on the
Aegis dataset. Every entry documents the artifact and its correct form.
"""

# ---- Normalization mapping table ----------------------------------------
# Format: (artifact_pattern, correct_replacement, reason)
# Applied in order — earlier entries take priority.
NORMALIZATION_TABLE = [
    # --- PDF font-substitution artifacts from pdfplumber ---
    # "ù" appears for em-dash "—" in the Aegis manuals (font encoding mismatch)
    ("ù", "—",     "PDF font substitution: Latin-1 0xF9 read as em-dash"),
    # "fi" ligature rendered as arrow-like glyph in some contexts
    # (appears in ECN-1042 "PS-04 fi PS-04A" meaning "PS-04 → PS-04A")
    (" fi ", " → ", "PDF ligature: 'fi' used as arrow in ECN-1042 change description"),
    ("fi>",  "→",   "PDF ligature: 'fi>' variant arrow"),
    # (cid:NNN) sequences = unmapped code point; common PDF artifact
    # Specific known mappings first, then generic fallback
    ("(cid:127)", "•",  "PDF CID: bullet point (0x7F in font's encoding)"),
    ("(cid:160)", "\u00a0", "PDF CID: non-breaking space"),
    ("(cid:173)", "-",  "PDF CID: soft hyphen"),
    # Generic CID fallback — replace any remaining (cid:NNN) with a marker
    # so they are visible and can be reviewed, not silently dropped.
    # Handled separately in normalize() below with regex.

    # --- Unicode right-quotes sometimes appear as apostrophes ---
    ("\u2019", "'",  "Unicode right single quote → apostrophe"),
    ("\u2018", "'",  "Unicode left single quote → apostrophe"),
    ("\u201c", '"',  "Unicode left double quote → straight quote"),
    ("\u201d", '"',  "Unicode right double quote → straight quote"),

    # --- Spurious whitespace ---
    ("\r\n", "\n",  "Windows CRLF → LF"),
    ("\r",   "\n",  "Bare CR → LF"),

    # --- Nbsp in extracted text ---
    ("\u00a0", " ", "Non-breaking space → regular space"),

    # --- mdash/ndash variants ---
    ("\u2014", "—", "Unicode em-dash normalize"),
    ("\u2013", "–", "Unicode en-dash normalize"),
]

# --- Regex-based generic (cid:NNN) cleanup ---
import re
_CID_RE = re.compile(r"\(cid:\d+\)")


def normalize(text: str) -> str:
    """
    Apply the normalization table to a raw extracted string.
    Returns a clean UTF-8 string.
    """
    if not text:
        return text

    for artifact, replacement, _ in NORMALIZATION_TABLE:
        text = text.replace(artifact, replacement)

    # Replace any remaining (cid:NNN) with a visible placeholder
    text = _CID_RE.sub("[CID?]", text)

    # Collapse multiple spaces (but not newlines)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text


def normalize_blocks(blocks: list) -> tuple:
    """
    Normalize a list of ContentBlock objects in-place.
    Returns (normalized_blocks, artifact_count) where artifact_count is
    the number of blocks that had at least one artifact replaced.
    """
    artifact_count = 0
    for block in blocks:
        original = block.text
        block.text = normalize(block.text)
        if block.text != original:
            artifact_count += 1
    return blocks, artifact_count


def normalize_table_data(tables: list) -> int:
    """
    Normalize all cell values in a list of TableData objects in-place.
    Returns count of cells that had artifacts replaced.
    """
    artifact_count = 0
    for table in tables:
        new_headers = []
        for h in table.headers:
            nh = normalize(h)
            if nh != h:
                artifact_count += 1
            new_headers.append(nh)
        table.headers = new_headers

        new_rows = []
        for row in table.rows:
            new_row = []
            for cell in row:
                nc = normalize(cell)
                if nc != cell:
                    artifact_count += 1
                new_row.append(nc)
            new_rows.append(new_row)
        table.rows = new_rows

    return artifact_count


def get_mapping_table() -> list:
    """Return the normalization mapping table for documentation/reporting."""
    return [
        {"artifact": art, "replacement": rep, "reason": reason}
        for art, rep, reason in NORMALIZATION_TABLE
    ]
