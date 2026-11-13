import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/calendar.html', 'r', encoding='utf-8') as f:
    text = f.read()

print('Length of frontend2/calendar.html:', len(text))
print('\nFirst 80 lines:\n')
lines = text.splitlines()
for l in lines[:80]:
    print(l)
