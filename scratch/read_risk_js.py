import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/risk.html', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.splitlines()
print(f'Total lines in risk.html: {len(lines)}')
for i, l in enumerate(lines[-140:]):
    print(f'{len(lines)-140+i+1}: {l}')
