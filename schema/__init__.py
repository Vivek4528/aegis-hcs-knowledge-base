"""
Schema models for Phase 1 raw extraction output.
Full claim/entity/evidence schema will be built in Phase 2.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class ExtractionMethod(Enum):
    """How a piece of content was extracted."""
    PDFPLUMBER_TEXT = "pdfplumber_text"
    PDFPLUMBER_TABLE = "pdfplumber_table"
    PYMUPDF_TEXT = "pymupdf_text"
    PYMUPDF_VECTOR = "pymupdf_vector_shapes"
    BEAUTIFULSOUP_HTML = "beautifulsoup_html"
    OPENPYXL_XLSX = "openpyxl_xlsx"
    PYTHON_DOCX = "python_docx"
    PYTHON_PPTX = "python_pptx"
    JSON_STDLIB = "json_stdlib"
    TESSERACT_OCR = "tesseract_ocr"
    VISION_MODEL_OCR = "vision_model_ocr"
    MANUAL_VISUAL_READ = "manual_visual_read"


class MethodType(Enum):
    """Whether extraction step is deterministic or model-based."""
    DETERMINISTIC = "deterministic"
    RULE_BASED = "rule_based"
    MODEL_BASED = "model_based"


@dataclass
class ContentBlock:
    """A block of extracted content from a document."""
    text: str
    block_type: str  # "paragraph", "heading", "warning", "note", "list_item", "footer"
    page: Optional[int] = None
    section: Optional[str] = None
    bbox: Optional[tuple] = None  # (x0, y0, x1, y1) if available
    confidence: float = 1.0
    
    def to_dict(self):
        return {
            "text": self.text,
            "block_type": self.block_type,
            "page": self.page,
            "section": self.section,
            "bbox": self.bbox,
            "confidence": self.confidence,
        }


@dataclass
class TableData:
    """An extracted table."""
    headers: List[str]
    rows: List[List[str]]
    page: Optional[int] = None
    section: Optional[str] = None
    has_merged_cells: bool = False
    has_multi_row_headers: bool = False
    confidence: float = 1.0
    
    def to_dict(self):
        return {
            "headers": self.headers,
            "rows": self.rows,
            "page": self.page,
            "section": self.section,
            "has_merged_cells": self.has_merged_cells,
            "has_multi_row_headers": self.has_multi_row_headers,
            "confidence": self.confidence,
        }


@dataclass
class DiagramTopology:
    """Extracted topology from a diagram (vector or raster)."""
    nodes: List[Dict[str, Any]]  # {"id": ..., "label": ..., "bbox": ...}
    edges: List[Dict[str, Any]]  # {"from": ..., "to": ..., "type": "signal"|"hydraulic"|"power"}
    annotations: List[str]
    confidence: float = 0.5  # Diagrams always start LOW confidence
    
    def to_dict(self):
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "annotations": self.annotations,
            "confidence": self.confidence,
        }


@dataclass
class ExtractionStep:
    """Documents one step of the extraction pipeline."""
    step_name: str
    method: ExtractionMethod
    method_type: MethodType
    reason: str  # Why this method/type was chosen
    
    def to_dict(self):
        return {
            "step_name": self.step_name,
            "method": self.method.value,
            "method_type": self.method_type.value,
            "reason": self.reason,
        }


@dataclass
class RawExtraction:
    """Complete raw extraction result for one file."""
    source_file: str
    file_format: str
    trust_tier: int
    trust_label: str
    
    # What was extracted
    content_blocks: List[ContentBlock] = field(default_factory=list)
    tables: List[TableData] = field(default_factory=list)
    diagrams: List[DiagramTopology] = field(default_factory=list)
    structured_data: Optional[Dict] = None  # For JSON files
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Pipeline documentation
    extraction_steps: List[ExtractionStep] = field(default_factory=list)
    
    # Quality tracking
    overall_confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "source_file": self.source_file,
            "file_format": self.file_format,
            "trust_tier": self.trust_tier,
            "trust_label": self.trust_label,
            "content_blocks": [b.to_dict() for b in self.content_blocks],
            "tables": [t.to_dict() for t in self.tables],
            "diagrams": [d.to_dict() for d in self.diagrams],
            "structured_data": self.structured_data,
            "metadata": self.metadata,
            "extraction_steps": [s.to_dict() for s in self.extraction_steps],
            "overall_confidence": self.overall_confidence,
            "warnings": self.warnings,
            "failures": self.failures,
        }
    
    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def summary(self):
        """One-line summary for the extraction report."""
        n_blocks = len(self.content_blocks)
        n_tables = len(self.tables)
        n_diagrams = len(self.diagrams)
        n_warnings = len(self.warnings)
        n_failures = len(self.failures)
        methods = ", ".join(s.method.value for s in self.extraction_steps)
        return (
            f"{self.source_file} | conf={self.overall_confidence:.2f} | "
            f"blocks={n_blocks}, tables={n_tables}, diagrams={n_diagrams} | "
            f"warnings={n_warnings}, failures={n_failures} | methods=[{methods}]"
        )
