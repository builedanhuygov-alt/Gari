import sqlite3
import sys
sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect("database/disease_detector.db")
c = conn.cursor()
row = c.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()
print("USERS TABLE:", row[0] if row else "None")
c.execute("PRAGMA table_info(users)")
for col in c.fetchall():
    print(" ", col)
c.execute("SELECT id, email, full_name, account_type FROM users")
for u in c.fetchall():
    print("User:", u)
