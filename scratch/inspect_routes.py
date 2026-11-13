import sys
import re

sys.stdout.reconfigure(encoding='utf-8')
with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

routes = re.findall(r'@app\.(?:get|post|put|patch|delete)\([\'"]([^\'"]+)[\'"]', text)
print(f'Total endpoints found: {len(routes)}')
for r in routes:
    if any(k in r for k in ['plot', 'calendar', 'task', 'risk', 'notif', 'timeline', 'farm']):
        print(' -', r)
