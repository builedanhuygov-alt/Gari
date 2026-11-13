"""
GARI MODULE 05 MIGRATION: Organization & Team Management Extensions
Adds:
- organization_member_assignments table (farm, zone, plot scoped assignments)
- declined_by_user_id, declined_at, decline_reason columns on organization_invitations
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger("gari_migration_module_05")
logging.basicConfig(level=logging.INFO)

DB_PATH = Path(__file__).resolve().parent / "disease_detector.db"


def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    logger.info("Migrating database for Module 05: Organization & Team Management...")

    # 1. organization_member_assignments
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS organization_member_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            farm_id INTEGER,
            zone_id INTEGER,
            plot_id INTEGER,
            assigned_by_user_id INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
            FOREIGN KEY (zone_id) REFERENCES farm_zones(id) ON DELETE CASCADE,
            FOREIGN KEY (plot_id) REFERENCES farm_plots(id) ON DELETE CASCADE
        );
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_org_member_assignments 
        ON organization_member_assignments(organization_id, user_id);
    """)

    # 2. Add columns to organization_invitations if missing
    cursor.execute("PRAGMA table_info(organization_invitations)")
    columns = [row[1] for row in cursor.fetchall()]

    if "declined_by_user_id" not in columns:
        cursor.execute("ALTER TABLE organization_invitations ADD COLUMN declined_by_user_id INTEGER")
        logger.info("Added declined_by_user_id to organization_invitations")

    if "declined_at" not in columns:
        cursor.execute("ALTER TABLE organization_invitations ADD COLUMN declined_at TIMESTAMP")
        logger.info("Added declined_at to organization_invitations")

    if "decline_reason" not in columns:
        cursor.execute("ALTER TABLE organization_invitations ADD COLUMN decline_reason TEXT")
        logger.info("Added decline_reason to organization_invitations")

    conn.commit()
    conn.close()
    logger.info("Module 05 migration applied successfully.")


if __name__ == "__main__":
    run_migration()
