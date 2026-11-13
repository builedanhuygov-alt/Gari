#!/usr/bin/env python3
"""
GARI AgriTech AI Lab — SQLite Automated Online Backup Engine
Path: deploy/oracle/backup_sqlite.py

Features:
- Online WAL-safe snapshot using Python sqlite3.Connection.backup() API
- Guaranteed point-in-time consistency without locking out live API writers
- SQLite internal integrity check (PRAGMA integrity_check) before saving
- SHA256 checksum calculation and metadata manifest generation
- Retention Policy:
  * Daily: Keep last 7 days
  * Weekly: Keep last 4 weeks (Sundays)
  * Monthly: Keep last 3 months (1st of month)
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [GARI-BACKUP] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("gari_backup")

def calculate_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()

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
        logger.error(f"Integrity check failed with error: {exc}")
        return False

def perform_online_backup(src_db: Path, backup_dir: Path) -> Path:
    """Execute WAL-safe online backup to timestamped file."""
    if not src_db.exists():
        raise FileNotFoundError(f"Source database not found: {src_db}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    backup_filename = f"gari_db_backup_{timestamp_str}.db"
    dest_path = backup_dir / backup_filename

    logger.info(f"Initiating online WAL-safe backup: {src_db} -> {dest_path}")
    
    # Connect to live DB with short timeout
    src_conn = sqlite3.connect(f"file:{src_db}?mode=ro", uri=True, timeout=10.0)
    dest_conn = sqlite3.connect(str(dest_path))

    try:
        # SQLite backup API performs consistent copy page by page
        src_conn.backup(dest_conn, pages=250, sleep=0.01)
        dest_conn.commit()
    finally:
        dest_conn.close()
        src_conn.close()

    # Verify backup integrity
    logger.info("Verifying integrity of backup snapshot...")
    if not verify_sqlite_integrity(dest_path):
        dest_path.unlink(missing_ok=True)
        raise RuntimeError("Integrity check FAILED on new backup. Backup discarded.")

    # Calculate checksum and file size
    size_bytes = dest_path.stat().st_size
    sha256_hash = calculate_sha256(dest_path)
    size_mb = round(size_bytes / (1024 * 1024), 2)
    logger.info(f"Backup verified OK: {backup_filename} ({size_mb} MB, SHA256: {sha256_hash[:16]}...)")

    # Write manifest
    manifest_path = dest_path.with_suffix(".json")
    manifest = {
        "backup_file": backup_filename,
        "created_at_utc": now.isoformat(),
        "size_bytes": size_bytes,
        "size_mb": size_mb,
        "sha256": sha256_hash,
        "integrity": "passed",
        "day_of_week": now.strftime("%A"),
        "day_of_month": now.day
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return dest_path

def apply_retention_policy(backup_dir: Path, daily_keep: int = 7, weekly_keep: int = 4, monthly_keep: int = 3):
    """Prune old backups according to GARI retention policy."""
    backups = sorted(backup_dir.glob("gari_db_backup_*.db"))
    if not backups:
        return

    logger.info(f"Applying retention policy (Keep: {daily_keep} daily, {weekly_keep} weekly, {monthly_keep} monthly)...")
    
    kept_files = set()
    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Keep last N daily
    for b in backups[-daily_keep:]:
        kept_files.add(b)

    # 2. Check each backup for weekly (Sundays) and monthly (1st of month) qualifications
    weekly_candidates = []
    monthly_candidates = []

    for b in backups:
        manifest_file = b.with_suffix(".json")
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("day_of_week") == "Sunday":
                    weekly_candidates.append(b)
                if meta.get("day_of_month") == 1:
                    monthly_candidates.append(b)
            except Exception:
                pass

    for b in weekly_candidates[-weekly_keep:]:
        kept_files.add(b)
    for b in monthly_candidates[-monthly_keep:]:
        kept_files.add(b)

    # Prune expired
    pruned_count = 0
    for b in backups:
        if b not in kept_files:
            logger.info(f"Pruning expired backup: {b.name}")
            b.unlink(missing_ok=True)
            b.with_suffix(".json").unlink(missing_ok=True)
            pruned_count += 1

    logger.info(f"Retention complete. Kept {len(kept_files)} backups, pruned {pruned_count}.")

def main():
    parser = argparse.ArgumentParser(description="GARI SQLite Automated Online Backup Engine")
    parser.add_argument("--db-path", default="database/disease_detector.db", help="Path to live SQLite DB")
    parser.add_argument("--backup-dir", default="database/backups", help="Target backup directory")
    parser.add_argument("--daily", type=int, default=7, help="Days of daily backups to keep")
    parser.add_argument("--weekly", type=int, default=4, help="Weeks of weekly backups to keep")
    parser.add_argument("--monthly", type=int, default=3, help="Months of monthly backups to keep")
    args = parser.parse_args()

    src_db = Path(args.db_path).resolve()
    backup_dir = Path(args.backup_dir).resolve()

    try:
        new_backup = perform_online_backup(src_db, backup_dir)
        apply_retention_policy(backup_dir, daily_keep=args.daily, weekly_keep=args.weekly, monthly_keep=args.monthly)
        logger.info(f"SUCCESS: Database backup completed: {new_backup.name}")
        sys.exit(0)
    except Exception as exc:
        logger.error(f"FAILURE: Backup failed: {exc}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

