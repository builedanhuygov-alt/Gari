import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('frontend2/host.html', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('async function loadApiControls()')
print(text[idx:idx+900])
