import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('frontend2/calendar.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'newTaskModal' in l and '<div' in l:
        for j in range(i, min(i+25, len(lines))):
            print(f'{j+1}: {lines[j].rstrip()}')
        break
