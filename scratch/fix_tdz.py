with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Add activeUser and activeOrgId near top
top_target = "let currentViewMode = 'attention'; // 'original', 'attention', 'overlay', 'split';"
top_replacement = """let currentViewMode = 'attention'; // 'original', 'attention', 'overlay', 'split';
        let activeUser = null;
        let activeOrgId = null;"""

if top_target in text:
    text = text.replace(top_target, top_replacement, 1)

# Remove the second declaration
duplicate_target = """        let activeUser = null;
        let activeOrgId = null;"""

# Find where it was duplicated and remove it
idx = text.find("// GARI AI LAB — UNIFIED AUTH & RBAC STATE MACHINE (Sprint 6 Overhaul)")
if idx != -1:
    next_decl = text.find("let activeUser = null;", idx)
    if next_decl != -1 and next_decl - idx < 200:
        end_decl = text.find("function initAuthUI()", next_decl)
        text = text[:next_decl] + text[end_decl:]

with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("SUCCESS: Fixed variable hoisting/TDZ in predict.html")
