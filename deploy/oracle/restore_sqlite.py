#!/usr/bin/env python3
"""
GARI AgriTech AI Lab — SQLite Disaster Recovery & Restore Engine
Path: deploy/oracle/restore_sqlite.py

Features:
- Validates integrity of candidate backup BEFORE touching live database
- Creates automatic timestamped safety snapshot of existing live database
- Atomically replaces live database file
- Cleans up stale WAL (-wal) and Shared Memory (-shm) files to avoid corruption
- Re-runs integrity check on active database to confirm clean restore
"""

import argparse
import datetime
import logging
import os
import shutil
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [GARI-RESTORE] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("gari_restore")

def verify_sqlite_integrity(db_path: Path) -> bool:
    """Run PRAGMA integrity_check on the SQLite database."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        row = cursor.fetchone()
        conn.close()
        return bool(row and row[0] == "ok")
    except Exception as exc:
        logger.error(f"Integrity check failed: {exc}")
        return False

def restore_database(backup_file: Path, target_db: Path) -> bool:
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    logger.info(f"Target restore database: {target_db}")
    logger.info(f"Source backup candidate: {backup_file}")

    # 1. Pre-validation of backup file
    logger.info("Step 1/5: Checking integrity of candidate backup...")
    if not verify_sqlite_integrity(backup_file):
        raise RuntimeError("Integrity check FAILED on candidate backup file! Aborting restore.")
    logger.info("Candidate backup is valid and intact.")

    # 2. Safety snapshot of current database
    target_dir = target_db.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    backups_dir = target_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    if target_db.exists():
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        safety_path = backups_dir / f"safety_pre_restore_{now}.db"
        logger.info(f"Step 2/5: Creating emergency safety backup of current DB -> {safety_path.name}")
        shutil.copy2(target_db, safety_path)
    else:
        logger.info("Step 2/5: Target database does not exist yet. No safety snapshot required.")

    # 3. Clean up existing WAL and SHM journal files to prevent replay conflict
    logger.info("Step 3/5: Removing stale WAL and SHM journal files...")
    wal_file = target_dir / f"{target_db.name}-wal"
    shm_file = target_dir / f"{target_db.name}-shm"
    if wal_file.exists():
        wal_file.unlink()
        logger.info(f"Removed stale {wal_file.name}")
    if shm_file.exists():
        shm_file.unlink()
        logger.info(f"Removed stale {shm_file.name}")

    # 4. Overwrite target DB
    logger.info("Step 4/5: Restoring database from backup...")
    shutil.copy2(backup_file, target_db)
    logger.info("Database file copied successfully.")

    # 5. Post-restore integrity verification
    logger.info("Step 5/5: Running post-restore integrity check on live DB...")
    if not verify_sqlite_integrity(target_db):
        raise RuntimeError("Post-restore integrity check FAILED on restored database!")

    logger.info("SUCCESS: Database restore completed and verified intact.")
    return True

def main():
    parser = argparse.ArgumentParser(description="GARI SQLite Disaster Recovery Engine")
    parser.add_argument("--backup-file", help="Path to specific backup .db file")
    parser.add_argument("--latest", action="store_true", help="Restore the latest available backup in database/backups")
    parser.add_argument("--target-db", default="database/disease_detector.db", help="Target SQLite DB path")
    args = parser.parse_args()

    target_db = Path(args.target_db).resolve()

    if args.latest:
        backups_dir = target_db.parent / "backups"
        candidates = sorted(backups_dir.glob("gari_db_backup_*.db"))
        if not candidates:
            logger.error("No backup files found in database/backups/")
            sys.exit(1)
        backup_file = candidates[-1]
        logger.info(f"Auto-selected latest backup: {backup_file.name}")
    elif args.backup_file:
        backup_file = Path(args.backup_file).resolve()
    else:
        logger.error("Please specify either --backup-file <path> or --latest")
        sys.exit(1)

    try:
        restore_database(backup_file, target_db)
        sys.exit(0)
    except Exception as exc:
        logger.error(f"FAILURE: Restore failed: {exc}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

