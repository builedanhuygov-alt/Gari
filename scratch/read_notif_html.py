import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines[340:375]):
    print(f'{i+341}: {l.rstrip()}')
