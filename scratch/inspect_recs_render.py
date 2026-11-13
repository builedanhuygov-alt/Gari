import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(2555, min(2615, len(lines))):
    print(f"{i+1}: {lines[i].rstrip()}")
