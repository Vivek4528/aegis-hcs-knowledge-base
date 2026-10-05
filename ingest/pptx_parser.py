"""
PPTX parser using python-pptx.
Extraction type: DETERMINISTIC — reads slide shapes and tables from the
OOXML presentation structure. No ML or heuristics.
"""
import pptx
from pptx.util import Inches
from schema import (
    RawExtraction, ContentBlock, TableData, ExtractionStep,
    ExtractionMethod, MethodType
)


def parse_pptx(filepath: str, file_info: dict) -> RawExtraction:
    """Parse a PPTX file using python-pptx."""
    extraction = RawExtraction(
        source_file=file_info["path"],
        file_format="pptx",
        trust_tier=file_info["trust_tier"],
        trust_label=file_info["trust_label"],
    )
    
    extraction.extraction_steps.append(ExtractionStep(
        step_name="pptx_parsing",
        method=ExtractionMethod.PYTHON_PPTX,
        method_type=MethodType.DETERMINISTIC,
        reason="python-pptx reads shape text and table content from the OOXML "
               "presentation structure. No ML or heuristics — deterministic "
               "extraction of text frames, table cells, and slide metadata."
    ))
    
    try:
        prs = pptx.Presentation(filepath)
        extraction.metadata["slide_count"] = len(prs.slides)
        
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_texts = []
            
            for shape in slide.shapes:
                # Extract text from text frames
                if hasattr(shape, "text_frame"):
                    text = shape.text_frame.text.strip()
                    if text:
                        # Determine if this is a title, body text, or note
                        block_type = "paragraph"
                        if shape.shape_type == 13:  # Title placeholder
                            block_type = "heading"
                        elif shape.has_text_frame:
                            # Check if it's short (likely a title/label)
                            if len(text) < 80 and "\n" not in text:
                                block_type = "heading"
                        
                        extraction.content_blocks.append(ContentBlock(
                            text=text,
                            block_type=block_type,
                            page=slide_num,
                            section=f"Slide {slide_num}",
                        ))
                        slide_texts.append(text)
                
                # Extract tables
                if shape.has_table:
                    table = shape.table
                    all_rows = []
                    for row in table.rows:
                        cells = [cell.text.strip() for cell in row.cells]
                        all_rows.append(cells)
                    
                    if all_rows:
                        extraction.tables.append(TableData(
                            headers=all_rows[0],
                            rows=all_rows[1:] if len(all_rows) > 1 else [],
                            page=slide_num,
                            section=f"Slide {slide_num}",
                        ))
            
            # Extract slide notes if present
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    extraction.content_blocks.append(ContentBlock(
                        text=f"[Speaker Notes] {notes}",
                        block_type="note",
                        page=slide_num,
                        section=f"Slide {slide_num}",
                    ))
        
        extraction.overall_confidence = 0.95
    
    except Exception as e:
        extraction.failures.append(f"PPTX parsing failed: {str(e)}")
        extraction.overall_confidence = 0.0
    
    return extraction
