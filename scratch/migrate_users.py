import sqlite3
from pathlib import Path

db_path = Path("database/disease_detector.db")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cols = [r[1] for r in cursor.execute("PRAGMA table_info(users)").fetchall()]
for col, col_type in [
    ("is_admin", "BOOLEAN DEFAULT 0"),
    ("is_host_admin", "BOOLEAN DEFAULT 0"),
    ("is_expert", "BOOLEAN DEFAULT 0"),
    ("is_active", "BOOLEAN DEFAULT 1"),
    ("province", "TEXT"),
    ("address", "TEXT"),
    ("avatar_url", "TEXT"),
    ("bio", "TEXT")
]:
    if col not in cols:
        print(f"Adding column {col} to users")
        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type};")

conn.commit()
conn.close()
print("Migration script completed successfully.")
