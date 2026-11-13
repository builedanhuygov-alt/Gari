import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    text = f.read()

print(f"Total characters in predict.html: {len(text)}")
lines = text.splitlines()
print(f"Total lines: {len(lines)}")

import re
matches = [i for i, l in enumerate(lines) if any(k in l.lower() for k in ['recommend', 'action', 'task', 'khuyến nghị', 'kết quả'])]
print(f"Matching lines count: {len(matches)}")
for idx in matches[:25]:
    print(f"Line {idx+1}: {lines[idx].strip()[:90]}")
