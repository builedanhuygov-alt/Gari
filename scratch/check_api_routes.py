import re

with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

host_routes = re.findall(r'@app\.[a-z]+\([\'"]/api/host[^\'"]*[\'"]', text)
org_routes = re.findall(r'@app\.[a-z]+\([\'"]/api/organization[^\'"]*[\'"]', text)

print(f"Host routes ({len(host_routes)}):", host_routes)
print(f"Org routes ({len(org_routes)}):", org_routes)
