import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('api_server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if '/api/farms/{farm_id}' in l:
        for j in range(i, min(i+35, len(lines))):
            print(f'{j+1}: {lines[j].rstrip()}')
        print('='*50)
