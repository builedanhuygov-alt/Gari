"""
GARI AI LAB — Database Backup & Disaster Recovery CLI Tool (tools/backup_restore.py)
Principal Engineer & SRE Utility:
- Consistent online SQLite backup via sqlite3.Connection.backup (zero locks/corruption)
- SHA256 checksum generation & validation for backup files
- Optional backup of user-uploaded images in database/uploads
- Safe test-restore verification without risking live production data
- Automated backup retention policy management
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_backup_restore")

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_DIR = ROOT_DIR / "database"
DB_PATH = DB_DIR / "disease_detector.db"
UPLOADS_DIR = DB_DIR / "uploads"
BACKUPS_DIR = DB_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def calculate_sha256(file_path: Path) -> str:
    """Computes SHA256 hex digest of a file in streaming chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_backup(include_uploads: bool = False, tag: str = "scheduled") -> Tuple[Path, Optional[Path], dict]:
    """
    Creates a transactionally consistent online backup of SQLite database.
    Optionally archives the uploads directory.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Source database file does not exist: {DB_PATH}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_db_name = f"gari_db_backup_{stamp}_{tag}.db"
    backup_db_path = BACKUPS_DIR / backup_db_name

    logger.info("Starting online database backup to: %s", backup_db_path)
    t0 = time.time()

    # 1. Transactionally safe online SQLite backup
    src = sqlite3.connect(str(DB_PATH))
    dest = sqlite3.connect(str(backup_db_path))
    try:
        src.backup(dest, pages=100, sleep=0.01)
    finally:
        dest.close()
        src.close()

    elapsed_db = time.time() - t0
    db_checksum = calculate_sha256(backup_db_path)
    db_size_bytes = backup_db_path.stat().st_size

    # Verify backup integrity immediately
    verify_conn = sqlite3.connect(str(backup_db_path))
    try:
        cur = verify_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()
        if not res or res[0].lower() != "ok":
            raise RuntimeError(f"Integrity check failed on created backup: {res}")
    finally:
        verify_conn.close()

    logger.info(
        "Database backup complete in %.2fs. Size: %.2f MB. SHA256: %s...",
        elapsed_db, db_size_bytes / (1024 * 1024), db_checksum[:16]
    )

    # 2. Optional uploads directory archive
    uploads_tar_path = None
    uploads_checksum = None
    uploads_count = 0
    if include_uploads and UPLOADS_DIR.exists():
        uploads_tar_name = f"gari_uploads_backup_{stamp}_{tag}.tar.gz"
        uploads_tar_path = BACKUPS_DIR / uploads_tar_name
        logger.info("Archiving uploads directory to: %s", uploads_tar_path)
        with tarfile.open(uploads_tar_path, "w:gz") as tar:
            for item in UPLOADS_DIR.iterdir():
                if item.is_file():
                    tar.add(item, arcname=item.name)
                    uploads_count += 1
        uploads_checksum = calculate_sha256(uploads_tar_path)
        logger.info("Uploads archive complete (%d files). SHA256: %s...", uploads_count, uploads_checksum[:16])

    # 3. Write metadata manifest
    metadata = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tag": tag,
        "database": {
            "filename": backup_db_name,
            "path": str(backup_db_path),
            "size_bytes": db_size_bytes,
            "sha256": db_checksum,
            "integrity_check": "ok"
        },
        "uploads": {
            "included": include_uploads,
            "filename": uploads_tar_path.name if uploads_tar_path else None,
            "file_count": uploads_count,
            "sha256": uploads_checksum
        }
    }

    manifest_path = BACKUPS_DIR / f"manifest_{stamp}_{tag}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info("Backup manifest written to: %s", manifest_path)
    return backup_db_path, uploads_tar_path, metadata


def verify_backup_file(backup_path: Path, expected_sha256: Optional[str] = None) -> bool:
    """Verifies SHA256 checksum and executes PRAGMA integrity_check on a backup file."""
    if not backup_path.exists():
        logger.error("Backup file does not exist: %s", backup_path)
        return False

    if expected_sha256:
        actual_sha256 = calculate_sha256(backup_path)
        if actual_sha256.lower() != expected_sha256.lower():
            logger.error("Checksum mismatch! Expected: %s, Actual: %s", expected_sha256, actual_sha256)
            return False
        logger.info("SHA256 checksum matched: %s", actual_sha256[:16])

    conn = sqlite3.connect(str(backup_path))
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        rows = cur.fetchall()
        if len(rows) == 1 and rows[0][0].lower() == "ok":
            logger.info("PRAGMA integrity_check passed: Database is structurally healthy.")
            return True
        logger.error("PRAGMA integrity_check failed: %s", rows)
        return False
    except Exception as exc:
        logger.error("Error reading database backup: %s", exc)
        return False
    finally:
        conn.close()


def restore_backup(backup_path: Path, target_db_path: Optional[Path] = None, force: bool = False) -> bool:
    """
    Safely restores a verified backup into the target database.
    If target exists, creates a pre-restore safety copy first.
    """
    target_path = target_db_path or DB_PATH
    if not verify_backup_file(backup_path):
        raise ValueError("Cannot restore from a corrupted or invalid backup file.")

    # Safety: back up current live db before overwriting
    if target_path.exists() and not force:
        pre_restore_safety = BACKUPS_DIR / f"safety_pre_restore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
        logger.info("Creating safety copy of current database at: %s", pre_restore_safety)
        src_safe = sqlite3.connect(str(target_path))
        dest_safe = sqlite3.connect(str(pre_restore_safety))
        try:
            src_safe.backup(dest_safe)
        finally:
            dest_safe.close()
            src_safe.close()

    # Perform atomic online restore into target
    logger.info("Restoring data from %s into %s ...", backup_path, target_path)
    src_res = sqlite3.connect(str(backup_path))
    dest_res = sqlite3.connect(str(target_path))
    try:
        src_res.backup(dest_res, pages=100, sleep=0.01)
    finally:
        dest_res.close()
        src_res.close()

    # Verify target after restore
    target_conn = sqlite3.connect(str(target_path))
    try:
        cur = target_conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()
        if not res or res[0].lower() != "ok":
            raise RuntimeError(f"Integrity check failed on restored database: {res}")
    finally:
        target_conn.close()
        if not res or res[0].lower() != "ok":
            raise RuntimeError(f"Integrity check failed on restored database: {res}")

    logger.info("Restore completed successfully and verified. Target database is online.")
    return True


def apply_retention(max_backups: int = 14, max_age_days: int = 30) -> int:
    """Removes backups older than max_age_days or exceeding max_backups count."""
    files = sorted(BACKUPS_DIR.glob("gari_db_backup_*.db"), key=lambda f: f.stat().st_mtime)
    deleted_count = 0
    now = time.time()

    for idx, f in enumerate(files):
        age_days = (now - f.stat().st_mtime) / 86400.0
        # Delete if too old or if count exceeds limit and this is an older file
        should_delete = (age_days > max_age_days) or (len(files) - idx > max_backups)
        if should_delete:
            logger.info("Purging aged backup: %s (age=%.1f days)", f.name, age_days)
            f.unlink(missing_ok=True)
            # Purge associated manifest if exists
            manifest = f.with_name(f.name.replace("gari_db_backup_", "manifest_").replace(".db", ".json"))
            manifest.unlink(missing_ok=True)
            deleted_count += 1

    return deleted_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gari AI Lab Database Backup & Recovery Utility")
    subparsers = parser.add_subparsers(dest="command")

    # backup
    p_backup = subparsers.add_parser("backup", help="Create a consistent online backup")
    p_backup.add_argument("--include-uploads", action="store_true", help="Also archive database/uploads")
    p_backup.add_argument("--tag", default="manual", help="Tag for this backup (e.g. pre_migration, daily)")

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify backup integrity and checksum")
    p_verify.add_argument("file", help="Path to backup .db file")
    p_verify.add_argument("--sha256", help="Expected SHA256 checksum")

    # restore
    p_restore = subparsers.add_parser("restore", help="Restore database from a backup file")
    p_restore.add_argument("file", help="Path to backup .db file to restore from")
    p_restore.add_argument("--target", help="Optional target db path (default: database/disease_detector.db)")
    p_restore.add_argument("--force", action="store_true", help="Skip pre-restore safety copy")

    # retention
    p_retention = subparsers.add_parser("retention", help="Apply backup retention policy")
    p_retention.add_argument("--max-backups", type=int, default=14)
    p_retention.add_argument("--max-age-days", type=int, default=30)

    args = parser.parse_args()

    if args.command == "backup":
        db_path, up_path, meta = create_backup(include_uploads=args.include_uploads, tag=args.tag)
        print(f"[OK] Backup created: {db_path.name} (SHA256: {meta['database']['sha256'][:16]}...)")
    elif args.command == "verify":
        ok = verify_backup_file(Path(args.file), expected_sha256=args.sha256)
        sys.exit(0 if ok else 1)
    elif args.command == "restore":
        ok = restore_backup(Path(args.file), target_db_path=Path(args.target) if args.target else None, force=args.force)
        sys.exit(0 if ok else 1)
    elif args.command == "retention":
        n = apply_retention(max_backups=args.max_backups, max_age_days=args.max_age_days)
        print(f"[OK] Pruned {n} expired backup files.")
    else:
        parser.print_help()
