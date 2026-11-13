import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/style.css', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('.app-shell {')
print(text[idx-50:idx+400])
