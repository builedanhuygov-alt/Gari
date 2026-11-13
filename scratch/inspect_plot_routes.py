import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('api_server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if '/api/plots' in line and '@app.' in line:
        print(f'=== Line {i+1}: {line.strip()} ===')
        for j in range(i, min(i + 30, len(lines))):
            print(lines[j], end='')
        print('\n' + '='*50 + '\n')
