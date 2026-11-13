import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('btnToggleSidebar')
idx2 = text.find('btnToggleSidebar', idx+1)
print(text[idx2-50:idx2+600])
