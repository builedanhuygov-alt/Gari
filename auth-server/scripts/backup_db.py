"""
GARI Auth Server 1.0 — Database Backup Script
Utilizes SQLite's native online backup API for lock-free point-in-time backups.
"""
import sqlite3
import shutil
import gzip
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def backup_database(db_path: str, backup_dir: str, compress: bool = True) -> str:
    source_path = Path(db_path).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source database file not found: {source_path}")

    dest_dir = Path(backup_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    raw_backup_path = dest_dir / f"gari_auth_backup_{timestamp}.db"

    # SQLite online backup API
    src_conn = sqlite3.connect(str(source_path))
    dest_conn = sqlite3.connect(str(raw_backup_path))

    with dest_conn:
        src_conn.backup(dest_conn, pages=100)

    dest_conn.close()
    src_conn.close()

    # Verify integrity of backup
    check_conn = sqlite3.connect(str(raw_backup_path))
    cursor = check_conn.cursor()
    cursor.execute("PRAGMA integrity_check;")
    result = cursor.fetchone()
    check_conn.close()

    if not result or result[0] != "ok":
        raw_backup_path.unlink(missing_ok=True)
        raise RuntimeError(f"Backup integrity check failed: {result}")

    if compress:
        compressed_path = dest_dir / f"gari_auth_backup_{timestamp}.db.gz"
        with open(raw_backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb', compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)
        raw_backup_path.unlink()
        return str(compressed_path)

    return str(raw_backup_path)


if __name__ == "__main__":
    db_file = os.getenv("AUTH_DB_PATH", "./data/gari_auth.db")
    backup_folder = os.getenv("AUTH_BACKUP_DIR", "./data/backups")
    try:
        out = backup_database(db_file, backup_folder)
        print(f"SUCCESS: Database backup created at {out}")
    except Exception as e:
        print(f"ERROR: Backup failed: {e}", file=sys.stderr)
        sys.exit(1)
