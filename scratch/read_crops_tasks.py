import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/crops.html', 'r', encoding='utf-8') as f:
    text = f.read()

print('Length of frontend2/crops.html:', len(text))
import re
print('Matches for calendar/task in crops.html:')
for m in re.finditer(r'(calendar|task)', text, re.IGNORECASE):
    pos = m.start()
    print(text[max(0, pos-40):min(len(text), pos+40)].replace('\n', ' '))
