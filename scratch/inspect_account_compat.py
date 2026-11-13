import sqlite3
import re

conn = sqlite3.connect('database/disease_detector.db')
cur = conn.cursor()

# 1. Total users
cur.execute("SELECT COUNT(*) FROM users;")
total_users = cur.fetchone()[0]

# 2. Schema columns
cur.execute("PRAGMA table_info(users);")
columns = [row[1] for row in cur.fetchall()]

# 3. Account types
cur.execute("SELECT DISTINCT account_type, COUNT(*) FROM users GROUP BY account_type;")
account_types = cur.fetchall()

# 4. Moderation statuses (if column exists)
has_moderation = "moderation_status" in columns
if has_moderation:
    cur.execute("SELECT DISTINCT moderation_status, COUNT(*) FROM users GROUP BY moderation_status;")
    moderation_stats = cur.fetchall()
else:
    moderation_stats = "Column not present"

# 5. Password hash format analysis (NO RAW HASHES PRINTED)
cur.execute("SELECT password_hash FROM users WHERE password_hash IS NOT NULL LIMIT 50;")
sample_hashes = [row[0] for row in cur.fetchall()]

hash_types = {}
for h in sample_hashes:
    if not h:
        ht = "EMPTY/NULL"
    elif h.startswith("$2b$") or h.startswith("$2a$") or h.startswith("$2y$"):
        ht = "BCRYPT"
    elif h.startswith("pbkdf2:"):
        ht = "PBKDF2"
    elif h.startswith("$argon2"):
        ht = "ARGON2"
    elif len(h) == 64 and re.match(r"^[0-9a-fA-F]+$", h):
        ht = "SHA256_HEX"
    elif len(h) == 32 and re.match(r"^[0-9a-fA-F]+$", h):
        ht = "MD5_HEX"
    elif ":" in h and len(h.split(":")[0]) == 64:
        ht = "SALTED_SHA256"
    else:
        ht = f"UNKNOWN_FORMAT_LEN_{len(h)}"
    hash_types[ht] = hash_types.get(ht, 0) + 1

# 6. Check sessions table
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cur.fetchall()]

session_count = 0
if "sessions" in tables:
    cur.execute("SELECT COUNT(*) FROM sessions;")
    session_count = cur.fetchone()[0]

print("=== GARI SQLITE ACCOUNT COMPATIBILITY AUDIT ===")
print(f"Total Users: {total_users}")
print(f"User Columns: {columns}")
print(f"Account Types: {repr(account_types).encode('ascii', 'backslashreplace').decode('ascii')}")
print(f"Moderation Stats: {repr(moderation_stats).encode('ascii', 'backslashreplace').decode('ascii')}")
print(f"Hash Types Sample: {hash_types}")
print(f"Tables in SQLite: {tables}")
print(f"Active Sessions Count: {session_count}")
