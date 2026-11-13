import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import gari_database

sys.stdout.reconfigure(encoding='utf-8')
with gari_database.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%invoice%' OR name LIKE '%payment%' OR name LIKE '%order%' OR name LIKE '%subscription%')")
    tables = [r[0] for r in cursor.fetchall()]
    print("Tables:", tables)
    for t in tables:
        cursor.execute(f"SELECT count(*) FROM {t}")
        cnt = cursor.fetchone()[0]
        print(f"  {t}: {cnt} rows")
