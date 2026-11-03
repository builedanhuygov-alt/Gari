"""
GARI AI LAB — Sprint 2 Organization Engine Migration (migrations_sprint2.py)

Idempotent migration for the B2B customer & organization engine.

Adds:
- organizations lifecycle/profile columns (organization_type, primary_crops, region,
  farming_scale, scale_consent, business contact, status_reason, archived_at/by,
  suspended_at)
- organization_invitations (hash-only tokens, expiry, revoke, manual delivery)
- organization_audit_log (actor, organization, action, timestamp, reason)
- organization_onboarding (resumable B2B onboarding state)
- indexes for tenant isolation and audit queries

Safety:
- Never deletes rows or historical usage.
- Existing organization statuses are preserved; legacy names are normalized at the
  application layer via gari_b2b.ORG_STATUS_ALIASES.
- Can be re-run any number of times.

Usage:
    python database/migrations_sprint2.py
    python database/migrations_sprint2.py --db-path path/to/custom.db
"""

import argparse
import logging
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_sprint2_migrations")

DEFAULT_DB_PATH = ROOT / "database" / "disease_detector.db"
BACKUP_DIR = ROOT / "database" / "backups"

ORG_COLUMNS = [
    ("organization_type", "TEXT"),
    ("primary_crops", "TEXT"),
    ("region", "TEXT"),
    ("farming_scale", "TEXT"),
    ("scale_consent", "INTEGER DEFAULT 0"),
    ("business_contact_name", "TEXT"),
    ("business_contact_title", "TEXT"),
    ("business_contact_email", "TEXT"),
    ("business_contact_phone", "TEXT"),
    ("status_reason", "TEXT"),
    ("archived_at", "DATETIME"),
    ("archived_by", "INTEGER"),
    ("suspended_at", "DATETIME"),
]


def _table_columns(cursor: sqlite3.Cursor, table: str):
    return [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]


def _table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    row = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return bool(row)


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> bool:
    if column in _table_columns(cursor, table):
        return False
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    return True


def backup_database(db_path: Path):
    if not db_path.exists():
        logger.info("Database does not exist yet; skipping backup.")
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"{db_path.stem}_pre_sprint2_{stamp}.db"
    shutil.copy2(db_path, backup_file)
    logger.info("Backup created: %s", backup_file)
    return backup_file


def apply_sprint2_migration(db_path: Path) -> dict:
    """Apply all Sprint 2 schema changes idempotently and return a summary."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    added_columns = []

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()

        # 1. Organizations profile/lifecycle columns
        if not _table_exists(cursor, "organizations"):
            raise RuntimeError(
                "Bảng 'organizations' chưa tồn tại. Hãy chạy gari_b2b.init_b2b_database() "
                "hoặc database/migrations_v2.py trước."
            )
        for column, definition in ORG_COLUMNS:
            if _ensure_column(cursor, "organizations", column, definition):
                added_columns.append(column)
        logger.info("organizations columns added: %s", added_columns or "none (already up to date)")

        # 2. Invitations table (only token hashes are stored)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS organization_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            token_hash TEXT UNIQUE NOT NULL,
            token_prefix TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            delivery_mode TEXT NOT NULL DEFAULT 'manual',
            delivery_status TEXT NOT NULL DEFAULT 'pending_manual_delivery',
            invited_by_user_id INTEGER,
            accepted_by_user_id INTEGER,
            expires_at DATETIME NOT NULL,
            accepted_at DATETIME,
            revoked_at DATETIME,
            revoked_by_user_id INTEGER,
            revoke_reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
            FOREIGN KEY (invited_by_user_id) REFERENCES users (id),
            FOREIGN KEY (accepted_by_user_id) REFERENCES users (id)
        );
        """)

        # 3. Organization audit trail
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS organization_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            actor_user_id INTEGER,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id INTEGER,
            reason TEXT,
            metadata_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
            FOREIGN KEY (actor_user_id) REFERENCES users (id)
        );
        """)

        # 4. Resumable onboarding
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS organization_onboarding (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER UNIQUE NOT NULL,
            current_step INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'in_progress',
            profile_completed INTEGER NOT NULL DEFAULT 0,
            role_confirmed INTEGER NOT NULL DEFAULT 0,
            needs_json TEXT,
            commercial_intent TEXT NOT NULL DEFAULT 'none',
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        );
        """)

        # 5. Indexes
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_org_members_user ON organization_members(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_org_members_org ON organization_members(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);",
            "CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_usage_metering_org ON usage_metering(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_usage_metering_user ON usage_metering(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_usage_metering_created ON usage_metering(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_org_invitations_org ON organization_invitations(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_org_invitations_email ON organization_invitations(email);",
            "CREATE INDEX IF NOT EXISTS idx_org_invitations_hash ON organization_invitations(token_hash);",
            "CREATE INDEX IF NOT EXISTS idx_org_audit_org ON organization_audit_log(organization_id, created_at);",
            "CREATE INDEX IF NOT EXISTS idx_org_onboarding_org ON organization_onboarding(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_org_status ON organizations(status);",
        ]:
            cursor.execute(stmt)

        # 6. Existing organizations without onboarding state get a resumable row.
        if _table_exists(cursor, "organization_onboarding"):
            cursor.execute("""
                INSERT OR IGNORE INTO organization_onboarding
                    (organization_id, current_step, status, profile_completed, role_confirmed)
                SELECT id, 5, 'completed', 
                       CASE WHEN organization_type IS NOT NULL AND organization_type != '' THEN 1 ELSE 0 END,
                       1
                FROM organizations
                WHERE status IN ('active', 'enabled', 'approved')
            """)

        conn.commit()

        summary = {
            "db_path": str(db_path),
            "added_columns": added_columns,
            "tables": [
                "organization_invitations",
                "organization_audit_log",
                "organization_onboarding",
            ],
            "organizations": cursor.execute("SELECT COUNT(*) FROM organizations").fetchone()[0],
        }
        logger.info("Sprint 2 migration complete: %s", summary)
        return summary
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Apply GARI Sprint 2 organization schema migration.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database.")
    parser.add_argument("--no-backup", action="store_true", help="Skip the pre-migration backup.")
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    if not args.no_backup:
        backup_database(db_path)
    summary = apply_sprint2_migration(db_path)
    print("Sprint 2 migration applied successfully.")
    print(summary)


if __name__ == "__main__":
    main()
