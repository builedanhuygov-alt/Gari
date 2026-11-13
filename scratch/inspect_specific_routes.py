import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('api_server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def print_section(keyword, max_lines=40):
    for i, line in enumerate(lines):
        if keyword in line and ('@app.' in line or 'def ' in line):
            print(f'=== Line {i+1}: {line.strip()} ===')
            for j in range(i, min(i + max_lines, len(lines))):
                print(lines[j], end='')
            print('\n' + '='*50 + '\n')

print_section('/api/notifications')
print_section('/api/risk/monitoring')
