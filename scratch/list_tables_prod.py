import sqlite3

conn = sqlite3.connect("database/disease_detector.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name ASC;")
tables = [r[0] for r in cur.fetchall()]
print(f"Total tables: {len(tables)}")
for i, t in enumerate(tables, 1):
    print(f"{i:2d}. {t}")

conn.close()

