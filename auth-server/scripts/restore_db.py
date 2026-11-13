"""
GARI Auth Server 1.0 — Database Restore Script
Restores database from an atomic backup with safety verification.
"""
import sqlite3
import gzip
import shutil
import sys
from pathlib import Path


def restore_database(backup_path: str, target_db_path: str) -> bool:
    src = Path(backup_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Backup file not found: {src}")

    target = Path(target_db_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    temp_restored = target.parent / f"{target.name}.restore_tmp"

    if src.suffix == ".gz":
        with gzip.open(src, 'rb') as f_in:
            with open(temp_restored, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    else:
        shutil.copy2(src, temp_restored)

    # Verify integrity before replacing target
    conn = sqlite3.connect(str(temp_restored))
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    check = cursor.fetchone()
    conn.close()

    if not check or check[0] != "ok":
        temp_restored.unlink(missing_ok=True)
        raise RuntimeError(f"Restored database integrity check failed: {check}")

    # Safely swap into target position
    temp_restored.replace(target)
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python restore_db.py <path_to_backup> <target_db_path>")
        sys.exit(1)
    b_file = sys.argv[1]
    t_file = sys.argv[2]
    try:
        restore_database(b_file, t_file)
        print(f"SUCCESS: Restored database to {t_file}")
    except Exception as e:
        print(f"ERROR: Restore failed: {e}", file=sys.stderr)
        sys.exit(1)
