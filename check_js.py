content = open('ui/index.html', encoding='utf-8').read()
start = content.index('<script>')
end = content.rindex('</script>')
js = content[start+8:end]
opens = js.count('{')
closes = js.count('}')
print(f'Open braces: {opens}')
print(f'Close braces: {closes}')
print(f'Balance: {opens - closes}')
lines = js.split('\n')
depth = 0
for i, line in enumerate(lines):
    for ch in line:
        if ch == '{': depth += 1
        elif ch == '}': depth -= 1
    if depth < 0:
        print(f'Line {i+1}: WENT NEGATIVE: {line[:80]}')
        break
print(f'Final depth: {depth}')
# Print lines around any problem area if depth != 0
if depth != 0:
    print("Last 20 JS lines:")
    for i, l in enumerate(lines[-20:], len(lines)-20):
        print(f"  {i}: {l[:100]}")
