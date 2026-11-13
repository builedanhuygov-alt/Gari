import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/style.css', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('@media (max-width: 1024px) {\n    .app-sidebar {')
if idx == -1:
    idx = text.find('.app-sidebar {\n        position: fixed;\n        left: 0;')
print(text[max(0, idx-100):min(len(text), idx+1500)])
