import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('database/disease_detector.db')
c = conn.cursor()

for tbl in ['expert_cases', 'notifications', 'users', 'host_api_config', 'host_audit_logs']:
    c.execute(f"PRAGMA table_info({tbl})")
    cols = c.fetchall()
    print(f"\n=== {tbl} ===")
    for col in cols:
        print(f"  {col[1]}: {col[2]} (default: {col[4]})")
