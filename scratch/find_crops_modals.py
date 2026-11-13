import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('frontend2/crops.html', 'r', encoding='utf-8') as f:
    for i, l in enumerate(f):
        if 'id="newTaskModal"' in l or 'id="calendarModal"' in l:
            print(f'{i+1}: {l.rstrip()}')
