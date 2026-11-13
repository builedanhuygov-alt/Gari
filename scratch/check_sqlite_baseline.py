import sqlite3
import os

db_path = "database/disease_detector.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT sqlite_version();")
ver = cursor.fetchone()[0]

cursor.execute("PRAGMA journal_mode;")
jm = cursor.fetchone()[0]

cursor.execute("PRAGMA foreign_keys;")
fk = cursor.fetchone()[0]

cursor.execute("PRAGMA integrity_check;")
ic = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
tc = cursor.fetchone()[0]

print(f"SQLite Version: {ver}")
print(f"Journal Mode: {jm}")
print(f"Foreign Keys: {fk}")
print(f"Integrity Check: {ic}")
print(f"Table Count: {tc}")
conn.close()

