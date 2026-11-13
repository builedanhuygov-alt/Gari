import os

suspicious_exts = ['.php', '.phtml', '.php3', '.php4', '.php5', '.phps', '.phar', '.inc', '.sh', '.bat', '.ps1', '.vbs', '.wsf']

found = []
for root, dirs, files in os.walk('.'):
    if any(skip in root for skip in ['.git', '.venv', 'node_modules', '.agents']):
        continue
    for f in files:
        _, ext = os.path.splitext(f.lower())
        if ext in suspicious_exts:
            p = os.path.join(root, f)
            found.append((p, os.path.getsize(p)))

print(f"Total script files with potentially suspicious extensions: {len(found)}")
for p, sz in found:
    print(f"  {sz:8d} B | {p}")

