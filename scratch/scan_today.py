import os
import sys
import datetime
import hashlib

def scan():
    today = datetime.datetime(2026, 11, 11, 0, 0, 0)
    touched = []
    for root, dirs, files in os.walk('.'):
        if any(skip in root for skip in ['.git', '.venv', 'node_modules', '.agents']):
            continue
        for f in files:
            p = os.path.join(root, f)
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p))
                ctime = datetime.datetime.fromtimestamp(os.path.getctime(p))
                if mtime >= today or ctime >= today:
                    sz = os.path.getsize(p)
                    touched.append((mtime, ctime, sz, p))
            except Exception as e:
                pass

    touched.sort(key=lambda x: x[0], reverse=True)
    print(f"Total files touched on 2026-11-11: {len(touched)}")
    for mtime, ctime, sz, p in touched:
        print(f"MTIME: {mtime.strftime('%Y-%m-%d %H:%M:%S')} | CTIME: {ctime.strftime('%Y-%m-%d %H:%M:%S')} | {sz:8d} B | {p}")

if __name__ == '__main__':
    scan()

