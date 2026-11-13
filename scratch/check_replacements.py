import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('gari_inference_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Area 1 (Auto Standard):")
for i in range(1570, 1585):
    print(f'{i+1}: {lines[i].rstrip()}')

print("\nArea 2 (Manual):")
for i in range(1820, 1835):
    print(f'{i+1}: {lines[i].rstrip()}')
