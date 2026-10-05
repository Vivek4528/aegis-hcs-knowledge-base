import re

# Pattern: catch "199.4bar", "0.1bar", "2OObar" etc.
# O-for-0 only in numeric context
RAW_PATTERN = re.compile(r'([0-9O]{1,5}(?:\.[0-9O]{1,3})?)(?:bar|Bar|BAR)', re.ASCII)

def fix_ocr_numeric(text):
    def replacer(m):
        num_str = m.group(1).replace('O', '0')  # O-for-0 in numeric context only
        try:
            val = float(num_str)
            return f'{val:g} bar'  # adds space: '199.4 bar', '200 bar'
        except ValueError:
            return m.group(0)
    return RAW_PATTERN.sub(replacer, text)

# HCS / HCs normalisation
def fix_hcs(text):
    return re.sub(r'HCs\b', 'HCS', text)

def fix_ocr(text):
    return fix_hcs(fix_ocr_numeric(text))

if __name__ == '__main__':
    tests = [
        ('199.4bar', '199.4 bar'),
        ('0.1bar', '0.1 bar'),
        ('2OObar', '200 bar'),
        ('180Bar', '180 bar'),
        ('HCs controller', 'HCS controller'),
    ]
    all_pass = True
    for inp, expected in tests:
        got = fix_ocr(inp)
        ok = got == expected
        print(f'{"PASS" if ok else "FAIL"}: fix_ocr({inp!r}) -> {got!r}  (expected {expected!r})')
        if not ok: all_pass = False
    print()
    print('All pass:', all_pass)

    # Confirm values from scan OCR
    scan_values = ['200', '180', '99.6', '199.4', '2026-01-09']
    print('Values to confirm in scanned_appendix_calibration output:')
    for v in scan_values: print(' ', v)
