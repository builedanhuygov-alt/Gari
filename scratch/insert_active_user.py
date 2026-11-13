with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = "let currentViewMode = 'attention'; // 'original', 'attention', 'overlay', 'split'"
replacement = """let currentViewMode = 'attention'; // 'original', 'attention', 'overlay', 'split'
        let activeUser = null;
        let activeOrgId = null;"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: Declared activeUser and activeOrgId")
else:
    print("Target not found")
