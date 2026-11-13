"""
GARI AI LAB — Verified Pre-Cutover Database Backup Script
File: database/create_pre_cutover_backup.py
Creates an online WAL-consistent atomic backup before production data cleanup.
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_database

DB_PATH = ROOT_DIR / "database" / "disease_detector.db"
BACKUP_DIR = ROOT_DIR / "database" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def main():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"disease_detector_pre_cutover_{timestamp}.db"
    print(f"[*] Creating WAL-consistent atomic backup of {DB_PATH.name}...")
    
    gari_database.backup_database_online(backup_file)

    if not backup_file.exists():
        raise RuntimeError(f"Backup failed! File not found: {backup_file}")
    
    size_mb = backup_file.stat().st_size / (1024 * 1024)
    print(f"[+] Backup verified successfully:")
    print(f"    Path: {backup_file}")
    print(f"    Size: {size_mb:.2f} MB")

    # Verify backup integrity using SQLite PRAGMA quick_check
    with sqlite3.connect(str(backup_file)) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA quick_check")
        check_result = cursor.fetchone()[0]
        if check_result != "ok":
            raise RuntimeError(f"Backup integrity verification failed: {check_result}")
        print(f"    Integrity Check: {check_result} (100% Valid SQLite database)")


if __name__ == "__main__":
    main()
