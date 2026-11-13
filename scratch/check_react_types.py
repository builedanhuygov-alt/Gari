import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('_archive/legacy-react-frontend/src/types.ts', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('export type NavTab')
print(text[idx:idx+250])
