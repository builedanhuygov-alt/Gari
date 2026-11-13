import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find("'community'")
while idx != -1:
    print(text[max(0, idx-50):min(len(text), idx+150)])
    print('---')
    idx = text.find("'community'", idx+1)
