"""Fix retrieval_engine.py: replace problem lines 376-380."""
content = open('query/retrieval_engine.py', encoding='utf-8').read()
lines = content.split('\n')

# Find and replace the problematic lines (0-indexed: 375-379)
for i, line in enumerate(lines):
    if "lines.append(" in line and i < 385:
        # Replace lines i through i+4
        lines[i]   = "            lines.append("
        lines[i+1] = "                f\"- {h['source_file']}{tier_note}\""
        lines[i+2] = "                + \"\\n  snippet: \" + h['snippet'][:100]"
        lines[i+3] = "                + \"\\n  (claim: \" + h['claim_value'] + \")\""
        lines[i+4] = "            )"
        break

fixed = '\n'.join(lines)
open('query/retrieval_engine.py', 'w', encoding='utf-8').write(fixed)
print("Fixed.")

# Verify it compiles
import py_compile
try:
    py_compile.compile('query/retrieval_engine.py', doraise=True)
    print("Syntax OK")
except py_compile.PyCompileError as e:
    print(f"STILL BROKEN: {e}")
