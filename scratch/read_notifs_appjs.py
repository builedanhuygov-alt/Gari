import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.splitlines()
print(f'Total lines in app.js: {len(lines)}')
for i, l in enumerate(lines):
    if 'notification' in l.lower() or 'notif' in l.lower():
        print(f'{i+1}: {l[:100]}')
