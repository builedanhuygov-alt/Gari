import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

with open('api_server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'def get_current_user(' in l or 'def get_current_user_optional(' in l:
        for j in range(i, min(i+35, len(lines))):
            print(lines[j], end='')
        print('\n' + '='*40 + '\n')
