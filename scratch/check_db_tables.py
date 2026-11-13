import sqlite3

conn = sqlite3.connect('database/disease_detector.db')
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("Total tables:", len(tables))
matched = [t for t in tables if any(k in t.lower() for k in ['diag', 'chat', 'copilot', 'convers', 'assist', 'task', 'host', 'setting', 'plant_record'])]
print("Matched tables:", matched)

for t in matched:
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
    print(f"Table {t}: {cols}")
