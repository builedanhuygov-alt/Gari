import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/calendar.html', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.splitlines()
print(f'Total lines: {len(lines)}')
for i, l in enumerate(lines[-150:]):
    print(f'{len(lines)-150+i+1}: {l}')
