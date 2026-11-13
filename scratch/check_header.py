import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('_archive/legacy-react-frontend/src/components/Header.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('Record<NavTab')
print(text[idx-50:idx+600])
