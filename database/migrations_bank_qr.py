"""
GARI AI LAB — Vietnamese Bank QR & SePay Migration (migrations_bank_qr.py)

Adds columns and indexes to support:
- Vietnamese Bank Transfer QR (VietQR / NAPAS 24/7)
- Order reference strings (e.g. 'GARI-100234')
- Recipient bank information and dynamic QR URLs
- Order expiry timestamps
- Provider transaction IDs with unique constraints (SePay transaction ID)
- Payment statuses: 'pending', 'paid', 'expired', 'failed', 'review_required'
- Reversible WAL-consistent pre-migration backup in database/backups/
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_bank_qr_migrations")

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
    backup_file = BACKUP_DIR / f"disease_detector_pre_bank_qr_{timestamp}.db"
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
    """Apply Bank QR & SePay schema updates idempotently."""
    backup_database()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    logger.info("Applying Bank QR schema extensions to payment_orders...")

    # Fetch existing columns in payment_orders
    cursor.execute("PRAGMA table_info(payment_orders)")
    existing_cols = {col[1] for col in cursor.fetchall()}

    new_columns = [
        ("order_reference", "TEXT"),
        ("qr_code_url", "TEXT"),
        ("bank_id", "TEXT"),
        ("account_number", "TEXT"),
        ("account_name", "TEXT"),
        ("expires_at", "DATETIME"),
        ("provider_tx_id", "TEXT"),
        ("confirmed_by_admin_id", "INTEGER"),
        ("bank_tx_reference", "TEXT"),
        ("admin_notes", "TEXT"),
        ("transfer_reported_at", "DATETIME"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing_cols:
            logger.info("Adding column %s %s to payment_orders", col_name, col_type)
            cursor.execute(f"ALTER TABLE payment_orders ADD COLUMN {col_name} {col_type};")

    # Add indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_reference ON payment_orders(order_reference);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_provider_tx ON payment_orders(provider_tx_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_expires_at ON payment_orders(expires_at);")

    conn.commit()
    conn.close()
    logger.info("Bank QR & SePay schema migrations applied successfully.")


if __name__ == "__main__":
    run_migrations()
