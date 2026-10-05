import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Check OCR mismatch report
with open('output/logs/ocr_mismatch_report.json', encoding='utf-8') as f:
    ocr = json.load(f)
print("=== OCR MISMATCH REPORT ===")
for r in ocr:
    mm = r.get('mismatch', {})
    print(f"{r['file']}: conf={r['avg_confidence']}, sim={mm.get('similarity','?')}, mismatch={mm.get('mismatch_rate','?')}")
    print(f"  OCR preview: {r['ocr_text_preview'][:200]}")
    print()

# Check reference report
with open('output/logs/reference_report.json', encoding='utf-8') as f:
    refs = json.load(f)
print(f"=== REFERENCE STATS ===")
print(f"total={refs['total_references_found']}, resolved={refs['resolved_count']}, unresolved={refs['unresolved_count']}, internal={refs['internal_count']}")
print("Unresolved:")
for r in refs['unresolved']:
    also = len(r.get('also_in', []))
    print(f"  [{r['type']}] '{r['value']}' from {r['source_file']} (also_in={also})")
