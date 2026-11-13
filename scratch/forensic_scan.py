import os
import sys
import datetime
import hashlib

def scan_files():
    cutoff = datetime.datetime.now() - datetime.timedelta(days=2)
    results = []
    for root, dirs, files in os.walk('.'):
        if any(skip in root for skip in ['.git', '.venv', 'node_modules', '.agents']):
            continue
        for f in files:
            p = os.path.join(root, f)
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p))
                if mtime > cutoff:
                    sz = os.path.getsize(p)
                    results.append((mtime, sz, p))
            except Exception as e:
                pass

    results.sort(key=lambda x: x[0], reverse=True)
    print(f"Total files modified in last 48 hours: {len(results)}")
    for mtime, sz, p in results:
        print(f"{mtime.strftime('%Y-%m-%d %H:%M:%S')} | {sz:10d} bytes | {p}")

if __name__ == '__main__':
    scan_files()

