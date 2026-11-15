import os
import sys
import sqlite3
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# 1. Update SQLite
SQLITE_PATH = ROOT_DIR / "database" / "disease_detector.db"
print(f"[*] Migrating SQLite database at {SQLITE_PATH}...")

conn_sqlite = sqlite3.connect(str(SQLITE_PATH))
cur_sqlite = conn_sqlite.cursor()

# Columns to add to 'farms':
# altitude_m (REAL), terrain (TEXT), water_source (TEXT), planting_date (TEXT), tree_age_years (REAL), growth_stage (TEXT)
farm_cols_to_add = [
    ("altitude_m", "REAL DEFAULT 0.0"),
    ("terrain", "TEXT DEFAULT 'Bằng phẳng'"),
    ("water_source", "TEXT DEFAULT 'Nước ngầm / Giếng khoan'"),
    ("planting_date", "TEXT"),
    ("tree_age_years", "REAL DEFAULT 1.0"),
    ("growth_stage", "TEXT DEFAULT 'Kiến thiết cơ bản'")
]

cur_sqlite.execute("PRAGMA table_info(farms)")
existing_farm_cols = {row[1] for row in cur_sqlite.fetchall()}

for col_name, col_def in farm_cols_to_add:
    if col_name not in existing_farm_cols:
        print(f"  + Adding {col_name} to farms...")
        cur_sqlite.execute(f"ALTER TABLE farms ADD COLUMN {col_name} {col_def}")
    else:
        print(f"  = farms.{col_name} already exists.")

# Columns to add to 'cultivation_tasks':
# time_window (TEXT), growth_stage (TEXT), rationale (TEXT), conditions (TEXT), source (TEXT), schedule_origin (TEXT)
task_cols_to_add = [
    ("time_window", "TEXT DEFAULT 'Buổi sáng sớm'"),
    ("growth_stage", "TEXT"),
    ("rationale", "TEXT"),
    ("conditions", "TEXT"),
    ("source", "TEXT DEFAULT 'Khuyến nông Quốc gia & GAP Việt Nam'"),
    ("schedule_origin", "TEXT DEFAULT 'stage_based'")
]

cur_sqlite.execute("PRAGMA table_info(cultivation_tasks)")
existing_task_cols = {row[1] for row in cur_sqlite.fetchall()}

for col_name, col_def in task_cols_to_add:
    if col_name not in existing_task_cols:
        print(f"  + Adding {col_name} to cultivation_tasks...")
        cur_sqlite.execute(f"ALTER TABLE cultivation_tasks ADD COLUMN {col_name} {col_def}")
    else:
        print(f"  = cultivation_tasks.{col_name} already exists.")

conn_sqlite.commit()
conn_sqlite.close()
print("[+] SQLite migration complete.")

# 2. Update Neon PostgreSQL if DATABASE_URL is configured
database_url = os.environ.get("DATABASE_URL")
if not database_url and (ROOT_DIR / ".env.local").exists():
    with open(ROOT_DIR / ".env.local", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                database_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if database_url:
    print(f"[*] Migrating Neon PostgreSQL...")
    try:
        import psycopg2
        conn_pg = psycopg2.connect(database_url, connect_timeout=10)
        conn_pg.autocommit = True
        cur_pg = conn_pg.cursor()
        
        # Check if farms table exists in PG
        cur_pg.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'farms');")
        farms_exist = cur_pg.fetchone()[0]
        if farms_exist:
            for col_name, col_def in farm_cols_to_add:
                # PostgreSQL safe column addition
                pg_type = col_def.replace("REAL", "DOUBLE PRECISION").replace("TEXT", "VARCHAR(255)")
                cur_pg.execute(f"ALTER TABLE farms ADD COLUMN IF NOT EXISTS {col_name} {col_def};")
                print(f"  + PG: farms.{col_name} checked/added.")
        
        # Check if cultivation_tasks table exists in PG
        cur_pg.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cultivation_tasks');")
        tasks_exist = cur_pg.fetchone()[0]
        if tasks_exist:
            for col_name, col_def in task_cols_to_add:
                cur_pg.execute(f"ALTER TABLE cultivation_tasks ADD COLUMN IF NOT EXISTS {col_name} {col_def};")
                print(f"  + PG: cultivation_tasks.{col_name} checked/added.")

        conn_pg.close()
        print("[+] Neon PostgreSQL migration complete.")
    except Exception as exc:
        print(f"[-] PG migration notice (non-fatal): {exc}")
else:
    print("[*] No DATABASE_URL found for PG migration.")
