import re

with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

patterns = [
    ("Farms", r'@app\.[a-z]+\(["\']/api/farms[^"\']*["\']'),
    ("Plots", r'@app\.[a-z]+\(["\']/api/plots[^"\']*["\']'),
    ("Diagnose/Diagnoses", r'@app\.[a-z]+\(["\']/api/diagnos[^"\']*["\']'),
    ("Calendar/Tasks", r'@app\.[a-z]+\(["\']/api/(?:calendar|tasks)[^"\']*["\']'),
    ("Risk", r'@app\.[a-z]+\(["\']/api/risk[^"\']*["\']'),
    ("Notifications", r'@app\.[a-z]+\(["\']/api/notification[^"\']*["\']'),
    ("Expert", r'@app\.[a-z]+\(["\']/api/expert[^"\']*["\']'),
    ("Knowledge", r'@app\.[a-z]+\(["\']/api/knowledge[^"\']*["\']')
]

for category, pat in patterns:
    matches = re.findall(pat, text)
    print(f"[{category}] ({len(matches)}):")
    for m in matches:
        print("  ", m)
    print()
