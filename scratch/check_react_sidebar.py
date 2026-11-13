import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('_archive/legacy-react-frontend/src/components/Sidebar.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find("import {")
print(text[idx:idx+400])

idx_reports = text.find("id: 'reports'")
print(text[idx_reports-50:idx_reports+400])
