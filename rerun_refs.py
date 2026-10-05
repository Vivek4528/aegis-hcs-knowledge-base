import sys, io, json, os, dataclasses
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

# Reload extractions from JSON dumps
from schema import RawExtraction, ContentBlock, TableData

raw_dir = 'output/raw_extractions'
extractions = []
for fname in sorted(os.listdir(raw_dir)):
    if not fname.endswith('.json'): continue
    with open(os.path.join(raw_dir, fname), encoding='utf-8') as f:
        data = json.load(f)

    # Reconstruct minimal extraction for reference scanning
    class MinExt:
        pass
    ext = MinExt()
    ext.source_file = data['source_file']
    ext.content_blocks = []
    for b in data['content_blocks']:
        cb = ContentBlock.__new__(ContentBlock)
        for k, v in b.items():
            setattr(cb, k, v)
        ext.content_blocks.append(cb)

    ext.tables = []
    for t in data['tables']:
        valid_fields = {f.name for f in dataclasses.fields(TableData)}
        filtered = {k: v for k, v in t.items() if k in valid_fields}
        td = TableData(**filtered)
        ext.tables.append(td)

    extractions.append(ext)

from ingest.reference_detector import detect_unresolved_references, write_reference_report
report = detect_unresolved_references(extractions)
write_reference_report(report, 'output/logs/reference_report.json')

total = report["total_references_found"]
res = report["resolved_count"]
unres = report["unresolved_count"]
intr = report["internal_count"]
print(f"total={total}, resolved={res}, unresolved={unres}, internal={intr}")
print("Unresolved:")
for r in report['unresolved']:
    also = len(r.get('also_in', []))
    val = r['value']
    src = r['source_file']
    print(f"  [{r['type']}] value={val!r} src={src} also_in={also}")
    for a in r.get('also_in', []):
        print(f"      also: {a['source_file']} sec={a['section']}")
