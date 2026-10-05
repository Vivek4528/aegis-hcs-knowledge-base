import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('output/raw_extractions/manuals__operator_manual_pdf.json', encoding='utf-8') as f:
    d = json.load(f)
print('Operator manual blocks:')
for b in d['content_blocks']:
    sec = b.get('section', '')
    bt = b.get('block_type', '')
    text = b.get('text', '')[:80]
    print(f"  [{bt}] sec={sec!r} | {text}")
print()

with open('output/raw_extractions/manuals__maintenance_manual_pdf.json', encoding='utf-8') as f:
    d = json.load(f)
print('Maintenance manual blocks:')
for b in d['content_blocks']:
    sec = b.get('section', '')
    bt = b.get('block_type', '')
    text = b.get('text', '')[:80]
    print(f"  [{bt}] sec={sec!r} | {text}")
