import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/community.html', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('<!-- Scripts -->')
if idx == -1:
    idx = text.rfind('<script')

print(text[idx:])
