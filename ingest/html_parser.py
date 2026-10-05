"""
HTML parser using BeautifulSoup.
Extraction type: DETERMINISTIC — HTML parsing is purely structural with no ML.
"""
from bs4 import BeautifulSoup
from ingest.normalizer import normalize
from schema import (
    RawExtraction, ContentBlock, TableData, ExtractionStep,
    ExtractionMethod, MethodType
)


def parse_html(filepath: str, file_info: dict) -> RawExtraction:
    """Parse an HTML file using BeautifulSoup."""
    extraction = RawExtraction(
        source_file=file_info["path"],
        file_format="html",
        trust_tier=file_info["trust_tier"],
        trust_label=file_info["trust_label"],
    )
    
    extraction.extraction_steps.append(ExtractionStep(
        step_name="html_parsing",
        method=ExtractionMethod.BEAUTIFULSOUP_HTML,
        method_type=MethodType.DETERMINISTIC,
        reason="BeautifulSoup parses the HTML DOM tree deterministically. "
               "No ML or heuristics — pure structural parsing of markup."
    ))
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extract metadata from head
        title = soup.find("title")
        if title:
            extraction.metadata["title"] = title.get_text()
        
        # Extract banner/notice divs (important for supersession info)
        for banner in soup.find_all("div", class_="banner"):
            extraction.content_blocks.append(ContentBlock(
                text=banner.get_text(strip=True),
                block_type="notice",
                page=1,
            ))
        
        # Extract headings and their following content
        current_section = None
        for element in soup.find("body").children if soup.find("body") else []:
            if hasattr(element, 'name'):
                if element.name in ("h1", "h2", "h3"):
                    current_section = element.get_text(strip=True)
                    extraction.content_blocks.append(ContentBlock(
                        text=current_section,
                        block_type="heading",
                        page=1,
                        section=current_section,
                    ))
                elif element.name == "p":
                    text = element.get_text(strip=True)
                    if text:
                        # Check for special classes
                        block_type = "paragraph"
                        if "meta" in (element.get("class") or []):
                            block_type = "metadata"
                        elif "warn" in (element.get("class") or []):
                            block_type = "warning"
                        
                        extraction.content_blocks.append(ContentBlock(
                            text=text,
                            block_type=block_type,
                            page=1,
                            section=current_section,
                        ))
                elif element.name == "div" and "warn" in (element.get("class") or []):
                    extraction.content_blocks.append(ContentBlock(
                        text=element.get_text(strip=True),
                        block_type="warning",
                        page=1,
                        section=current_section,
                    ))
                elif element.name == "ul":
                    for li in element.find_all("li"):
                        extraction.content_blocks.append(ContentBlock(
                            text=li.get_text(strip=True),
                            block_type="list_item",
                            page=1,
                            section=current_section,
                        ))
                elif element.name == "ol":
                    for i, li in enumerate(element.find_all("li"), 1):
                        extraction.content_blocks.append(ContentBlock(
                            text=f"{i}. {li.get_text(strip=True)}",
                            block_type="ordered_list_item",
                            page=1,
                            section=current_section,
                        ))
                elif element.name == "table":
                    _extract_html_table(element, extraction, current_section)
                elif element.name == "hr":
                    pass  # Ignore horizontal rules
        
        # Extract footnotes from <p class="meta"> at the end
        for meta_p in soup.find_all("p", class_="meta"):
            text = meta_p.get_text(strip=True)
            if text and not any(b.text == text for b in extraction.content_blocks):
                extraction.content_blocks.append(ContentBlock(
                    text=text,
                    block_type="footnote",
                    page=1,
                ))
        
        extraction.overall_confidence = 0.95
    
    except Exception as e:
        extraction.failures.append(f"HTML parsing failed: {str(e)}")
        extraction.overall_confidence = 0.0
    
    return extraction


def _extract_html_table(table_element, extraction, section):
    """Extract a table from an HTML <table> element."""
    rows_data = []
    for tr in table_element.find_all("tr"):
        cells = []
        for cell in tr.find_all(["th", "td"]):
            cells.append(cell.get_text(strip=True))
        if cells:
            rows_data.append(cells)
    
    if rows_data and len(rows_data) > 1:
        extraction.tables.append(TableData(
            headers=rows_data[0],
            rows=rows_data[1:],
            page=1,
            section=section,
        ))
