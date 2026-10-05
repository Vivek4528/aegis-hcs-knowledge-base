import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

raw_dir = 'output/raw_extractions'
files_to_show = [
    'reference__component_register',
    'reference__revision_history',
    'low_trust__site_survey',
    'extra__training_slide',
    'reference__terminology_glossary',
    'manuals__legacy_manual',
]
for fname in sorted(os.listdir(raw_dir)):
    stem = fname.replace('.json','')
    if not any(stem.startswith(f) for f in files_to_show):
        continue
    path = os.path.join(raw_dir, fname)
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    src = d['source_file']
    print(f'=== {src} ===')
    for b in d['content_blocks']:
        text = b['text'][:200]
        print(f'  {text}')
    for t in d['tables']:
        print(f'  [TABLE] headers={t["headers"]}')
        for row in t['rows']:
            print(f'    {row}')
    print()
