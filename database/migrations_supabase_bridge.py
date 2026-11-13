"""
GARI AgriTech AI Lab — SQLite Identity Bridge Migration
Creates gari_identity_links and account_provisioning tables in SQLite.
Safe, idempotent, preserves all existing data.
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "disease_detector.db"

def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Table: gari_identity_links
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gari_identity_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supabase_uid TEXT UNIQUE NOT NULL,
        sqlite_user_id INTEGER UNIQUE NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sqlite_user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gari_identity_links_sub ON gari_identity_links(supabase_uid);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gari_identity_links_uid ON gari_identity_links(sqlite_user_id);")

    # 2. Table: account_provisioning
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS account_provisioning (
        supabase_uid TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'PENDING',
        error_code TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        metadata TEXT DEFAULT '{}',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    print("SQLite identity bridge tables migrated successfully.")

if __name__ == "__main__":
    run_migration()

