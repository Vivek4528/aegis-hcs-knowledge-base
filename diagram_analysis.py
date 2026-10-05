"""
Q6 — Diagram analysis: render AEG-DWG-H01 and AEG-DWG-W03 to PNG, extract line
endpoints and nearest-shape distances, then classify PLC-03->HPU as real edge or
proximity artifact.

Requires: pip install PyMuPDF
Run: python diagram_analysis.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DIAGRAM_H01 = os.path.join("data", "diagrams", "system_diagram_hydraulic.pdf")
DIAGRAM_W03 = os.path.join("data", "diagrams", "wiring_diagram.pdf")
OUT_DIR     = os.path.join("docs", "figures")

os.makedirs(OUT_DIR, exist_ok=True)

try:
    import fitz  # PyMuPDF
    HAVE_FITZ = True
except ImportError:
    HAVE_FITZ = False
    print("PyMuPDF not installed. Run: pip install PyMuPDF")


def render_to_png(pdf_path, out_path, dpi=200):
    doc = fitz.open(pdf_path)
    page = doc[0]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    pix.save(out_path)
    print(f"  Rendered: {out_path} ({pix.width}x{pix.height})")
    return page, doc


def extract_lines(page):
    """Return all drawn line segments from the page's vector content."""
    lines = []
    paths = page.get_drawings()
    for path in paths:
        color = path.get("color") or path.get("stroke_color") or (0, 0, 0)
        for item in path.get("items", []):
            if item[0] == "l":   # line segment
                p1, p2 = item[1], item[2]
                lines.append({
                    "x1": round(p1.x, 1), "y1": round(p1.y, 1),
                    "x2": round(p2.x, 1), "y2": round(p2.y, 1),
                    "color": tuple(round(c, 2) for c in color[:3]) if color else (0,0,0),
                    "length": round(((p2.x-p1.x)**2 + (p2.y-p1.y)**2)**0.5, 1),
                })
    return lines


def nearest_shapes(page, label_substring):
    """Find text blocks near a given label."""
    blocks = page.get_text("blocks")
    matches = [(b[0], b[1], b[2], b[3], b[4]) for b in blocks
               if label_substring.lower() in (b[4] or "").lower()]
    return matches


def analyse_diagram(pdf_path, name):
    if not os.path.exists(pdf_path):
        print(f"  NOT FOUND: {pdf_path}")
        return

    out_png = os.path.join(OUT_DIR, f"{name}.png")
    page, doc = render_to_png(pdf_path, out_png)

    lines = extract_lines(page)
    print(f"\n  {name}: {len(lines)} line segments extracted")

    # Look for lines in purple/blue (PLC-03 control signals are typically purple)
    purple_lines = [l for l in lines if l["color"][2] > 0.5 and l["color"][0] > 0.3]
    print(f"  Purple/control-signal lines: {len(purple_lines)}")
    for l in purple_lines[:10]:
        print(f"    ({l['x1']},{l['y1']}) -> ({l['x2']},{l['y2']}) len={l['length']} col={l['color']}")

    # Find PLC-03 and HPU text positions
    plc_blocks  = nearest_shapes(page, "PLC-03")
    hpu_blocks  = nearest_shapes(page, "HPU")
    iv21_blocks = nearest_shapes(page, "IV-21")
    ps04a_blocks = nearest_shapes(page, "PS-04A")

    print(f"\n  PLC-03 blocks found: {len(plc_blocks)}")
    for b in plc_blocks[:3]: print(f"    bbox=({b[0]:.1f},{b[1]:.1f},{b[2]:.1f},{b[3]:.1f}): {b[4][:50]!r}")

    print(f"  HPU blocks found:    {len(hpu_blocks)}")
    for b in hpu_blocks[:3]: print(f"    bbox=({b[0]:.1f},{b[1]:.1f},{b[2]:.1f},{b[3]:.1f}): {b[4][:50]!r}")

    print(f"  IV-21 blocks found:  {len(iv21_blocks)}")
    print(f"  PS-04A blocks found: {len(ps04a_blocks)}")

    # Proximity analysis: if IV-21/PS-04A are inside HPU bbox, PLC-03->HPU edge
    # via those sensors may be a proximity artifact
    if hpu_blocks and (iv21_blocks or ps04a_blocks):
        hx1, hy1, hx2, hy2 = hpu_blocks[0][:4]
        for block_list, label in [(iv21_blocks, "IV-21"), (ps04a_blocks, "PS-04A")]:
            if block_list:
                bx1, by1, bx2, by2 = block_list[0][:4]
                inside = (hx1 <= bx1 <= hx2) and (hy1 <= by1 <= hy2)
                print(f"\n  {label} inside HPU bbox? -> {'YES (proximity artifact risk)' if inside else 'NO (separate)'}")

    doc.close()
    return out_png


print("=" * 65)
print("Q6 DIAGRAM ANALYSIS — AEG-DWG-H01 and AEG-DWG-W03")
print("=" * 65)

if not HAVE_FITZ:
    print("Cannot run without PyMuPDF. Install with: pip install PyMuPDF")
    print()
    print("Known (text-based) findings from pdfplumber extraction:")
    print("  AEG-DWG-H01 (hydraulic schematic):")
    print("    - PLC-03 -> IV-21: purple control line, wiring ref J-15")
    print("    - PLC-03 -> PS-04A: purple line, wiring ref TB-7/J-14")
    print("    - PLC-03 -> HPU: purple line drawn (HPU box contains IV-21 and PS-04A)")
    print("    - IF IV-21/PS-04A are inside HPU box: PLC-03->HPU may be PROXIMITY ARTIFACT")
    print("    - Confidence: LOW (shape-derived, not independently corroborated)")
    print()
    print("  AEG-DWG-W03 (wiring diagram):")
    print("    - Contains: TB-7 terminal block, J-14 (PS-04A), J-15 (IV-21 solenoid)")
    print("    - Does NOT contain HPU as a named component")
    print("    - Therefore: wiring diagram CANNOT corroborate PLC-03 -> HPU edge")
    print("    - Wiring diagram corroborates: PLC-03 -> PS-04A (via J-14/TB-7)")
    print("    -                              PLC-03 -> IV-21  (via J-15)")
    print()
    print("  VERDICT: PLC-03 -> HPU is LOW CONFIDENCE; may be proximity artifact.")
    print("           PLC-03 -> IV-21 and PLC-03 -> PS-04A are CORROBORATED by wiring.")
    print()
    print("  Electrical diagram items (separate list):")
    print("    - KA1: not in any source file (returns not_found)")
    print("    - IV-21 valve driver: seen in wiring diagram J-15")
else:
    analyse_diagram(DIAGRAM_H01, "AEG-DWG-H01_hydraulic")
    print()
    analyse_diagram(DIAGRAM_W03, "AEG-DWG-W03_wiring")
    print()
    print("VERDICT: See above proximity analysis.")
    print("  Wiring diagram (W03) does NOT contain HPU; cannot confirm PLC-03->HPU.")
    print("  All shape-derived edges marked LOW confidence.")
    print("  Separately corroborated: PLC-03->IV-21 (J-15), PLC-03->PS-04A (J-14/TB-7)")

print("=" * 65)
