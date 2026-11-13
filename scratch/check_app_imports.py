import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('_archive/legacy-react-frontend/src/App.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find("import { SettingsView } from './components/SettingsView';")
print(text[idx-50:idx+200])

idx_render = text.find("{activeTab === 'settings' && (")
print(text[idx_render-50:idx_render+300])
