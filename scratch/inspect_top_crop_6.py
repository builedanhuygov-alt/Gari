import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('gari_inference_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(1820, min(1860, len(lines))):
    print(f'{i+1}: {lines[i].rstrip()}')
