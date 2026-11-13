import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.findall(r'@app\.(?:get|post|put|patch|delete)\([\'"]([^\'"]*chat[^\'"]*|[^\'"]*copilot[^\'"]*|[^\'"]*assistant[^\'"]*)[\'"]', text)
print(f"Chat / Copilot endpoints found: {matches}")

for m in matches:
    pos = text.find(f"'{m}'")
    if pos == -1: pos = text.find(f'"{m}"')
    if pos != -1:
        print(f"--- Endpoint {m} ---")
        print(text[pos:pos+350])
