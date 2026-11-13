import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

idx = 0
while True:
    idx = text.find('initFloatingChat', idx)
    if idx == -1:
        break
    print(f'Match at {idx}:')
    print(text[max(0, idx-100):min(len(text), idx+200)])
    print('---')
    idx += len('initFloatingChat')
