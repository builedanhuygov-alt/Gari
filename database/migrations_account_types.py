"""
GARI AI LAB — Single Active Account Type Migration (migrations_account_types.py)

Updates the database to enforce a single active account type per authenticated UID:
- Canonical types: 'farmer', 'cooperative', 'expert', 'enterprise'
- Creates audit trail table `user_account_type_audit`
- Normalizes existing Vietnamese/legacy account_type strings to canonical slugs
- Atomic WAL-consistent online backup prior to execution
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_account_type_migrations")

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "disease_detector.db"
BACKUP_DIR = DB_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Mapping from legacy Vietnamese / alternate strings to canonical slugs
CANONICAL_MAPPING = {
    "farmer": "farmer",
    "nông hộ": "farmer",
    "nong ho": "farmer",
    "nông hộ cá thể": "farmer",
    "cooperative": "cooperative",
    "hợp tác xã": "cooperative",
    "hop tac xa": "cooperative",
    "trang trại": "cooperative",
    "expert": "expert",
    "chuyên gia": "expert",
    "chuyên gia bvtv": "expert",
    "đơn vị dịch vụ nông nghiệp": "expert",
    "don vi dich vu nong nghiep": "expert",
    "agronomist": "expert",
    "enterprise": "enterprise",
    "doanh nghiệp": "enterprise",
    "doanh nghiep": "enterprise",
    "tập đoàn": "enterprise",
    "platform admin": "expert",  # Admins retain is_admin=1; account_type mapped to expert
    "admin": "expert",
}


def backup_database() -> Optional[Path]:
    """Create a WAL-consistent pre-migration backup."""
    if not DB_PATH.exists():
        logger.info("Database file does not exist yet; skipping backup.")
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"disease_detector_pre_account_type_{timestamp}.db"
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
    """Apply single active account type migration."""
    backup_database()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    logger.info("Ensuring audit table user_account_type_audit exists...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_account_type_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        previous_type TEXT,
        new_type TEXT NOT NULL,
        reason TEXT,
        changed_by_user_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_acc_type_audit_user ON user_account_type_audit(user_id);
    """)

    # Normalize existing users' account_type
    logger.info("Normalizing existing users' account_type to canonical values...")
    cursor.execute("SELECT id, email, account_type FROM users")
    rows = cursor.fetchall()
    updated_count = 0

    for uid, email, raw_type in rows:
        normalized = None
        if raw_type:
            cleaned = raw_type.strip().lower()
            normalized = CANONICAL_MAPPING.get(cleaned)

        if not normalized:
            normalized = "farmer"  # Default fallback

        if normalized != raw_type:
            cursor.execute("UPDATE users SET account_type = ? WHERE id = ?", (normalized, uid))
            # Record migration in audit log
            cursor.execute("""
                INSERT INTO user_account_type_audit (user_id, previous_type, new_type, reason, changed_by_user_id)
                VALUES (?, ?, ?, 'System migration to canonical single account type', 1)
            """, (uid, raw_type, normalized))
            updated_count += 1

    conn.commit()
    conn.close()
    logger.info("Migration complete! Normalized %d user account types.", updated_count)


if __name__ == "__main__":
    run_migrations()
