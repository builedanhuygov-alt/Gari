"""
GARI AI LAB — Voucher & Pricing Migrations (migrations_vouchers.py)

Creates:
- vouchers table (stores SHA-256 hash of code, preview, limits, expiry, restrictions)
- voucher_redemptions table (records atomic redemptions per user with unique constraints)
- voucher_audit_log table (tamper-evident audit trail of admin and user voucher actions)
- Safe pre-migration backup in database/backups/
"""

import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_voucher_migrations")

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "disease_detector.db"
BACKUP_DIR = DB_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_database() -> Optional[Path]:
    """Create an atomic, WAL-consistent online backup before applying migrations."""
    if not DB_PATH.exists():
        logger.info("Database file does not exist yet; skipping backup.")
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"disease_detector_pre_vouchers_{timestamp}.db"
    try:
        import gari_database
        gari_database.backup_database_online(backup_file)
    except Exception:
        with sqlite3.connect(str(DB_PATH)) as src:
            with sqlite3.connect(str(backup_file)) as dst:
                src.backup(dst)
    logger.info("Created pre-migration backup at: %s", backup_file)
    return backup_file


def run_migrations():
    """Apply voucher schema migrations idempotently."""
    backup_database()

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    logger.info("Applying voucher schema tables and indexes...")

    # 1. vouchers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vouchers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code_hash TEXT UNIQUE NOT NULL,
        code_preview TEXT NOT NULL,
        plan_id TEXT NOT NULL,
        duration_days INTEGER NOT NULL DEFAULT 30,
        max_redemptions INTEGER NOT NULL DEFAULT 1,
        redemption_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active',
        restricted_to_email TEXT,
        expires_at DATETIME NOT NULL,
        created_by_user_id INTEGER NOT NULL,
        revoked_at DATETIME,
        revoked_by_user_id INTEGER,
        revoke_reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by_user_id) REFERENCES users(id),
        FOREIGN KEY (revoked_by_user_id) REFERENCES users(id)
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vouchers_code_hash ON vouchers(code_hash);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vouchers_status ON vouchers(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vouchers_expires_at ON vouchers(expires_at);")

    # 2. voucher_redemptions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voucher_redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voucher_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        plan_id TEXT NOT NULL,
        duration_days INTEGER NOT NULL,
        granted_period_start DATETIME NOT NULL,
        granted_period_end DATETIME NOT NULL,
        subscription_id INTEGER,
        ip_address TEXT,
        user_agent TEXT,
        redeemed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (voucher_id) REFERENCES vouchers(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL,
        UNIQUE (voucher_id, user_id)
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_voucher_redemptions_user ON voucher_redemptions(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_voucher_redemptions_voucher ON voucher_redemptions(voucher_id);")

    # 3. voucher_audit_log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voucher_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voucher_id INTEGER,
        actor_user_id INTEGER,
        action TEXT NOT NULL,
        details_json TEXT,
        ip_address TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (voucher_id) REFERENCES vouchers(id) ON DELETE SET NULL,
        FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_voucher_audit_voucher ON voucher_audit_log(voucher_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_voucher_audit_action ON voucher_audit_log(action);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_voucher_audit_created ON voucher_audit_log(created_at);")

    conn.commit()
    conn.close()
    logger.info("Voucher migrations applied successfully.")


if __name__ == "__main__":
    run_migrations()
