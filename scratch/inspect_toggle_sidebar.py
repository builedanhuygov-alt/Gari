import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('backdrop.classList.toggle')
print(text[idx-50:idx+600])
