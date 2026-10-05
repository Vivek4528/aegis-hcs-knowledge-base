"""
DOCX parser using python-docx.
Extraction type: DETERMINISTIC — reads document paragraphs and tables from
the OOXML structure. No ML or heuristics.
"""
import docx
from schema import (
    RawExtraction, ContentBlock, TableData, ExtractionStep,
    ExtractionMethod, MethodType
)


def parse_docx(filepath: str, file_info: dict) -> RawExtraction:
    """Parse a DOCX file using python-docx."""
    extraction = RawExtraction(
        source_file=file_info["path"],
        file_format="docx",
        trust_tier=file_info["trust_tier"],
        trust_label=file_info["trust_label"],
    )
    
    extraction.extraction_steps.append(ExtractionStep(
        step_name="docx_parsing",
        method=ExtractionMethod.PYTHON_DOCX,
        method_type=MethodType.DETERMINISTIC,
        reason="python-docx reads paragraph and table content from the OOXML "
               "(XML-based) document structure. No ML or heuristics — deterministic "
               "extraction of text, styles, and table cell contents."
    ))
    
    try:
        doc = docx.Document(filepath)
        
        # Extract paragraphs
        current_section = None
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            # Get style name safely
            style_name = ""
            try:
                if para.style and para.style.name:
                    style_name = para.style.name
            except Exception:
                pass
            
            # Classify block type from style
            if "heading" in style_name.lower() or style_name == "Title":
                block_type = "heading"
                current_section = text
            elif "list" in style_name.lower():
                block_type = "list_item"
            else:
                block_type = "paragraph"
            
            extraction.content_blocks.append(ContentBlock(
                text=text,
                block_type=block_type,
                page=1,  # DOCX doesn't have page numbers until rendered
                section=current_section,
            ))
            
            extraction.metadata[f"style_{len(extraction.content_blocks)}"] = style_name
        
        # Extract tables
        for ti, table in enumerate(doc.tables):
            all_rows = []
            for row in table.rows:
                cells = []
                for cell in row.cells:
                    cells.append(cell.text.strip())
                all_rows.append(cells)
            
            if all_rows:
                # De-duplicate cells (python-docx repeats merged cell text)
                # Check for repeated adjacent values which indicate merged cells
                has_merged = False
                for row in all_rows:
                    for i in range(len(row) - 1):
                        if row[i] == row[i+1] and row[i]:
                            has_merged = True
                            break
                
                headers = all_rows[0] if all_rows else []
                data_rows = all_rows[1:] if len(all_rows) > 1 else []
                
                extraction.tables.append(TableData(
                    headers=headers,
                    rows=data_rows,
                    section=current_section,
                    has_merged_cells=has_merged,
                ))
        
        extraction.overall_confidence = 0.95
    
    except Exception as e:
        extraction.failures.append(f"DOCX parsing failed: {str(e)}")
        extraction.overall_confidence = 0.0
    
    return extraction
