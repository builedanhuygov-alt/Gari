import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/style.css', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('.app-sidebar')
while idx != -1:
    idx_media = text.rfind('@media', 0, idx)
    if idx_media != -1 and idx - idx_media < 300:
        print(text[idx_media:idx+200])
        print('='*30)
    idx = text.find('.app-sidebar', idx+1)
