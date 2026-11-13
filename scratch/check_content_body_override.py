import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/style.css', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('.content-body {\n    flex: 1;\n    padding: 24px 28px;')
print(text[idx-50:idx+400])
