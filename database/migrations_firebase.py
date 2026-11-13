"""
GARI AI LAB — Firebase Identity Integration Migration
File: database/migrations_firebase.py

Adds `firebase_uid` to users table with unique index for seamless server-side
Firebase ID token synchronization.
"""

import logging
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_firebase_migration")

DB_PATH = ROOT_DIR / "database" / "disease_detector.db"


def run_migration():
    logger.info("Running Firebase Identity database migration...")
    with sqlite3.connect(str(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cursor.fetchall()]

        if "firebase_uid" not in cols:
            logger.info("Adding column 'firebase_uid' to users...")
            cursor.execute("ALTER TABLE users ADD COLUMN firebase_uid TEXT")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid)")
            conn.commit()
            logger.info("Column 'firebase_uid' added successfully with unique index.")
        else:
            logger.info("Column 'firebase_uid' already exists.")

    logger.info("Firebase Identity migration complete!")


if __name__ == "__main__":
    run_migration()
