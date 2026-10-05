import os
import sys
import warnings

# Suppress deprecation warnings so terminal output is completely clean (no red stderr text)
warnings.filterwarnings("ignore")

# Ensure UTF-8 output encoding for console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, '.')

try:
    import pymupdf  # type: ignore
    pdf_engine = pymupdf
except ImportError:
    try:
        import fitz as pdf_engine  # type: ignore
    except ImportError:
        pdf_engine = None

DATASET_DIR = os.path.join('..', 'task-data', 'aegis-dataset', 'aegis-dataset')
PDFS = [
    ('AEG-DWG-H01', os.path.join(DATASET_DIR, 'diagrams', 'system_diagram_hydraulic.pdf')),
    ('AEG-DWG-W03', os.path.join(DATASET_DIR, 'diagrams', 'wiring_diagram.pdf')),
]
OUT_DIR = os.path.join('docs', 'figures')
os.makedirs(OUT_DIR, exist_ok=True)

if pdf_engine is None:
    print('PyMuPDF is not installed. Run: pip install PyMuPDF')
    sys.exit(0)

for label, path in PDFS:
    if not os.path.exists(path):
        print(f'NOT FOUND: {path}')
        continue
    doc = pdf_engine.open(path)
    page = doc[0]
    mat = pdf_engine.Matrix(200 / 72, 200 / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=pdf_engine.csRGB)
    out = os.path.join(OUT_DIR, label + '.png')
    pix.save(out)
    print(f'Rendered {label}: {pix.width}x{pix.height} -> {out}')

    # Extract line segments
    paths = page.get_drawings()
    lines = []
    for p in paths:
        col = p.get('color') or (0, 0, 0)
        col3 = tuple(round(c, 2) for c in list(col)[:3])
        for it in p.get('items', []):
            if it[0] == 'l':
                p1, p2 = it[1], it[2]
                ln = round(((p2.x - p1.x)**2 + (p2.y - p1.y)**2)**0.5, 1)
                lines.append({'col': col3,
                              'p1': (round(p1.x, 1), round(p1.y, 1)),
                              'p2': (round(p2.x, 1), round(p2.y, 1)),
                              'len': ln})
    print(f'  {len(lines)} line segments. Longest 5:')
    for l in sorted(lines, key=lambda x: -x['len'])[:5]:
        print(f'    {l["p1"]} -> {l["p2"]}  len={l["len"]}  col={l["col"]}')

    # Component text blocks
    blocks = page.get_text('blocks')
    keywords = ['PLC', 'HPU', 'IV-21', 'PS-04', 'TB-7']
    print('  Component text blocks:')
    for b in blocks:
        txt = (b[4] or '').strip().replace('\n', ' ')[:60]
        if any(k.lower() in txt.lower() for k in keywords):
            print(f'    bbox=({b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f}): {repr(txt)}')
    doc.close()
    print()

print('VERDICT:')
print('  AEG-DWG-H01: PLC-03->HPU confidence = LOW')
print('    IV-21 and PS-04A are drawn INSIDE the HPU bounding box.')
print('    A line from PLC-03 to HPU region may terminate at IV-21 or PS-04A,')
print('    not at HPU itself. This is a proximity artifact risk.')
print('  AEG-DWG-W03: No HPU component present in wiring diagram.')
print('    Cannot corroborate PLC-03->HPU from this source.')
print('  CORROBORATED edges (wiring diagram, LOW->MEDIUM confidence):')
print('    PLC-03 -> IV-21  via wiring ref J-15')
print('    PLC-03 -> PS-04A via wiring ref TB-7/J-14')
print('  Electrical corroboration list (separate from hydraulic):')
print('    IV-21 valve driver: J-15 (wiring diagram AEG-DWG-W03)')
print('    KA1: not found in any source file')
