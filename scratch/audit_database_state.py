import sys
import sqlite3

sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('database/disease_detector.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in c.fetchall()]
print(f"Total tables ({len(tables)}):")
for t in tables:
    try:
        c.execute(f'SELECT COUNT(*) FROM "{t}"')
        cnt = c.fetchone()[0]
        print(f" - {t}: {cnt} rows")
    except Exception as e:
        print(f" - {t}: Error {e}")
