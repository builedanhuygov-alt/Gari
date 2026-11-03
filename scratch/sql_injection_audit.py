import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

py_files = list(ROOT.glob("*.py"))

sql_pattern = re.compile(r'(cursor|conn)\.execute\s*\(\s*([fF]["\']|["\'].*?%|["\'].*?\.format)', re.DOTALL)

print("=" * 80)
print("Scanning for dynamic SQL query formatting in Python files...")
print("=" * 80)

found_suspicious = []
for p in py_files:
    try:
        content = p.read_text(encoding="utf-8")
        for match in re.finditer(r'(cursor|conn)\.execute\s*\(\s*(f"""|f\'\'\'|f"|f\')(.*?)\)', content, re.DOTALL):
            found_suspicious.append((p.name, match.group(0)[:150]))
        for match in re.finditer(r'(cursor|conn)\.execute\s*\(\s*("""|\'\'\'|"|\')(.*?)\.(format|%)\(', content, re.DOTALL):
            found_suspicious.append((p.name, match.group(0)[:150]))
    except Exception as e:
        pass

if not found_suspicious:
    print("No obvious dynamic SQL execution strings found via regex.")
else:
    for filename, snippet in found_suspicious:
        print(f"File: {filename}")
        print(f"Snippet:\n{snippet}\n" + "-" * 40)
