import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

with open('api_server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if '@app.get("/api/farms")' in l:
        for j in range(i, min(i+25, len(lines))):
            print(lines[j], end='')
        break
