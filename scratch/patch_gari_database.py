from pathlib import Path

path = Path("gari_database.py")
content = path.read_text(encoding="utf-8")

old_snippet = """        # Migrate user columns if missing
        user_cols = [r[1] for r in cursor.execute("PRAGMA table_info(users)").fetchall()]
        if "is_admin" not in user_cols:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0;")
            except Exception:
                pass"""

new_snippet = """        # Migrate user columns if missing
        user_cols = [r[1] for r in cursor.execute("PRAGMA table_info(users)").fetchall()]
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
            if col not in user_cols:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type};")
                except Exception:
                    pass"""

# Normalize CRLF / LF
content = content.replace(old_snippet.replace("\r\n", "\n"), new_snippet.replace("\r\n", "\n"))
content = content.replace(old_snippet, new_snippet)
path.write_text(content, encoding="utf-8")
print("gari_database.py patched.")
