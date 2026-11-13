import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

endpoints = re.findall(r'@app\.(get|post|patch|put|delete)\("(/api/(?:host|auth/host)[^"]*)"', text)
for method, path in endpoints:
    print(f'{method.upper():6} {path}')
