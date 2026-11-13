import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('export function initFloatingChat() {')
end = text.find('export function ensureLegalFooter()')
print(f'Length of initFloatingChat: {end - start}')
with open('scratch/floating_chat_orig.js', 'w', encoding='utf-8') as f:
    f.write(text[start:end])
print('Saved scratch/floating_chat_orig.js')
