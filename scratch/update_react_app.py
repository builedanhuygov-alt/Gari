import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('_archive/legacy-react-frontend/src/App.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add import
target_import = "import { SettingsView } from './components/SettingsView';"
replacement_import = """import { SettingsView } from './components/SettingsView';
import { CommunityView } from './components/CommunityView';"""

if target_import not in text:
    print("Error: target_import not found")
    sys.exit(1)
text = text.replace(target_import, replacement_import, 1)

# 2. Add view rendering
target_render = "{activeTab === 'reports' && <BusinessView farms={farms} />}"
replacement_render = """{activeTab === 'reports' && <BusinessView farms={farms} />}

            {activeTab === 'community' && <CommunityView />}"""

if target_render not in text:
    print("Error: target_render not found")
    sys.exit(1)
text = text.replace(target_render, replacement_render, 1)

with open('_archive/legacy-react-frontend/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully updated App.tsx with CommunityView!")
