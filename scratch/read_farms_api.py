import sys
sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('@app.get("/api/farms"')
print(text[idx:idx+2500])
