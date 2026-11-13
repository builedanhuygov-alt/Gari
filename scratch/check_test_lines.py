import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('scratch/test_frontend_playwright.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(35, min(75, len(lines))):
    print(f'{i+1}: {lines[i].rstrip()}')
