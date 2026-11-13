import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('_archive/legacy-react-frontend/src/types.ts', 'r', encoding='utf-8') as f:
    text = f.read()

target = """export type NavTab =
  | 'overview'
  | 'vision'
  | 'farms'
  | 'crops'
  | 'diseases'
  | 'predict'
  | 'expert'
  | 'reports'
  | 'settings';"""

replacement = """export type NavTab =
  | 'overview'
  | 'vision'
  | 'farms'
  | 'crops'
  | 'diseases'
  | 'predict'
  | 'expert'
  | 'reports'
  | 'community'
  | 'settings';"""

if target not in text:
    print("Error: target not found in types.ts")
    sys.exit(1)

text = text.replace(target, replacement, 1)

with open('_archive/legacy-react-frontend/src/types.ts', 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully updated types.ts with 'community'!")
