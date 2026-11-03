"""
GARI AI LAB — Violation Moderation & Review System Migration (migrations_moderation.py)
Creates schema for:
- User moderation status columns (moderation_status, feature_restrictions, moderation_reason, moderation_updated_at)
- moderation_cases: Queue of flagged violations pending Host review
- moderation_audit_logs: Immutable log of administrative moderation actions
- moderation_appeals: User appeal submissions and Host review outcomes
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_moderation_migrations")

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "disease_detector.db"
BACKUP_DIR = DB_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_database() -> Optional[Path]:
    """Create a WAL-consistent pre-migration backup."""
    if not DB_PATH.exists():
        logger.info("Database file does not exist yet; skipping backup.")
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"disease_detector_pre_moderation_{timestamp}.db"
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
    """Apply moderation schema extensions idempotently."""
    backup_database()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    try:
        # 1. Add moderation columns to users if missing
        cursor.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cursor.fetchall()}

        if "moderation_status" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN moderation_status TEXT DEFAULT 'clean';")
            logger.info("Added users.moderation_status column.")

        if "feature_restrictions" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN feature_restrictions TEXT DEFAULT '';")
            logger.info("Added users.feature_restrictions column.")

        if "moderation_reason" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN moderation_reason TEXT DEFAULT NULL;")
            logger.info("Added users.moderation_reason column.")

        if "moderation_updated_at" not in existing_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN moderation_updated_at TIMESTAMP DEFAULT NULL;")
            logger.info("Added users.moderation_updated_at column.")

        # 2. Create moderation_cases table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moderation_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                user_email TEXT NOT NULL,
                violation_category TEXT NOT NULL,
                severity TEXT NOT NULL,
                detection_source TEXT NOT NULL,
                evidence_summary TEXT NOT NULL,
                evidence_reference TEXT,
                confidence_score REAL DEFAULT 1.0,
                status TEXT DEFAULT 'pending',
                decision_notes TEXT,
                reviewed_by_host_id INTEGER,
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_cases_user ON moderation_cases(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_cases_status ON moderation_cases(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_cases_severity ON moderation_cases(severity);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_cases_created ON moderation_cases(created_at);")
        logger.info("Ensured moderation_cases table and indexes exist.")

        # 3. Create moderation_audit_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moderation_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT,
                target_user_id INTEGER NOT NULL,
                target_email TEXT NOT NULL,
                actor_admin_id INTEGER NOT NULL,
                actor_email TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT NOT NULL,
                previous_status TEXT,
                resulting_status TEXT,
                details_json TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_audit_target ON moderation_audit_logs(target_user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_audit_actor ON moderation_audit_logs(actor_admin_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_audit_created ON moderation_audit_logs(created_at);")
        logger.info("Ensured moderation_audit_logs table and indexes exist.")

        # 4. Create moderation_appeals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moderation_appeals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                user_email TEXT NOT NULL,
                case_id TEXT,
                appeal_reason TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                host_response TEXT,
                reviewed_by_host_id INTEGER,
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_appeals_user ON moderation_appeals(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mod_appeals_status ON moderation_appeals(status);")
        logger.info("Ensured moderation_appeals table and indexes exist.")

        conn.commit()
        logger.info("Moderation migrations executed successfully.")

    except Exception as exc:
        conn.rollback()
        logger.exception("Moderation migration failed: %s", exc)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()
