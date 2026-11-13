import sqlite3
import os

uri = 'file:database/disease_detector.db?mode=ro'
conn = sqlite3.connect(uri, uri=True)
cur = conn.cursor()

print("Integrity check:", cur.execute("PRAGMA integrity_check;").fetchall())
print("Quick check:", cur.execute("PRAGMA quick_check;").fetchall())
print("Journal mode:", cur.execute("PRAGMA journal_mode;").fetchall())

query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
tables = [r[0] for r in cur.execute(query).fetchall()]
print(f"Total tables: {len(tables)}")

counts = {}
for t in tables:
    try:
        cnt = cur.execute(f"SELECT count(*) FROM {t};").fetchone()[0]
        counts[t] = cnt
    except Exception as e:
        counts[t] = f"ERROR: {e}"

for k in sorted(counts.keys()):
    if counts[k] != 0 or any(x in k for x in ['user', 'diag', 'farm', 'plot', 'org', 'task', 'case', 'log']):
        print(f"  {k}: {counts[k]}")

conn.close()

db_size = os.path.getsize('database/disease_detector.db')
wal_size = os.path.getsize('database/disease_detector.db-wal') if os.path.exists('database/disease_detector.db-wal') else 0
shm_size = os.path.getsize('database/disease_detector.db-shm') if os.path.exists('database/disease_detector.db-shm') else 0
print(f"DB File Size: {db_size / (1024*1024):.2f} MB")
print(f"WAL File Size: {wal_size / 1024:.2f} KB")
print(f"SHM File Size: {shm_size / 1024:.2f} KB")

