"""
GARI AI LAB — Dedicated Host Admin & Host Console Migration (migrations_host_admin.py)

Adds:
- `is_host_admin` column to users (DEFAULT 0)
- `is_active` column to users (DEFAULT 1)
- `host_audit_logs` table for tracking all administrative actions
- `host_api_config` table for manageable API controls, rate limits, and feature toggles
- Strict principle: NEVER grants host_admin automatically to any user.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_host_migrations")

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
    backup_file = BACKUP_DIR / f"disease_detector_pre_host_{timestamp}.db"
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
    """Apply Host Admin schema extensions idempotently."""
    backup_database()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # 1. Check existing columns in users table
    cursor.execute("PRAGMA table_info(users)")
    user_cols = {col[1] for col in cursor.fetchall()}

    if "is_host_admin" not in user_cols:
        logger.info("Adding is_host_admin column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_host_admin BOOLEAN DEFAULT 0")

    if "is_active" not in user_cols:
        logger.info("Adding is_active column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")

    # 2. Host Audit Logs
    logger.info("Creating host_audit_logs table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS host_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        host_admin_id INTEGER NOT NULL,
        host_email TEXT,
        action_type TEXT NOT NULL,
        target_resource TEXT,
        details_json TEXT,
        reason TEXT,
        outcome TEXT DEFAULT 'success',
        ip_address TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (host_admin_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_host_audit_created ON host_audit_logs(created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_host_audit_admin ON host_audit_logs(host_admin_id);")

    # 3. Host API & System Configuration
    logger.info("Creating host_api_config table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS host_api_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        description TEXT,
        updated_by_host_id INTEGER,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed default configuration toggles if empty
    default_configs = [
        ("rate_limit_per_minute", "120", "Giới hạn số lượng yêu cầu API tối đa mỗi phút cho mỗi IP"),
        ("maintenance_mode", "0", "Chế độ bảo trì hệ thống (1: Bật, 0: Tắt)"),
        ("allowed_public_registration", "1", "Cho phép người dùng tự đăng ký tài khoản (1: Bật, 0: Tắt)"),
        ("ai_inference_enabled", "1", "Kích hoạt cụm động cơ suy luận AI ConvNeXt (1: Bật, 0: Tắt)"),
        ("vouchers_enabled", "1", "Cho phép người dùng quy đổi mã voucher (1: Bật, 0: Tắt)")
    ]

    for key, val, desc in default_configs:
        cursor.execute("""
            INSERT OR IGNORE INTO host_api_config (key, value, description, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (key, val, desc))

    conn.commit()
    conn.close()
    logger.info("Host admin migration completed successfully.")


if __name__ == "__main__":
    run_migrations()
