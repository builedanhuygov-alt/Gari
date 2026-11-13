import sqlite3

conn = sqlite3.connect('database/disease_detector.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cur.fetchall()]
print(f"Total SQLite Tables: {len(tables)}\n")

for t in tables:
    cur.execute(f"PRAGMA table_info({t})")
    cols = [f"{c[1]} ({c[2]})" for c in cur.fetchall()]
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    cnt = cur.fetchone()[0]
    print(f"[{t}] - {cnt} rows")
    print("  Columns:", ", ".join(cols[:8]) + ("..." if len(cols) > 8 else ""))
