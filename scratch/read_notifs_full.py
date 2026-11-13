import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines[640:710]):
    print(f'{i+641}: {l.rstrip()}')
