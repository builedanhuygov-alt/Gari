"""
GARI AI LAB — Payment Gateway & Webhook Migrations (migrations_payments.py)

Creates:
- payment_orders table (tracks orders, amounts, plans, provider links, statuses)
- payment_webhook_events table (durable idempotency for provider events with UNIQUE constraints)
- payment_audit_log table (tamper-evident audit trail of payment and lifecycle transitions)
- Safe pre-migration WAL-consistent backup in database/backups/
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_payment_migrations")

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
    backup_file = BACKUP_DIR / f"disease_detector_pre_payments_{timestamp}.db"
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
    """Apply payment schema migrations idempotently."""
    backup_database()

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    logger.info("Applying payment gateway schema tables and indexes...")

    # 1. payment_orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code INTEGER UNIQUE NOT NULL,
        internal_payment_id TEXT UNIQUE NOT NULL,
        target_type TEXT NOT NULL,                  -- 'user' | 'organization'
        target_id INTEGER NOT NULL,                 -- user_id or organization_id
        user_id INTEGER NOT NULL,                   -- initiating user
        organization_id INTEGER,                    -- org_id if B2B
        plan_id TEXT NOT NULL,                      -- 'personal' | 'business'
        amount INTEGER NOT NULL,                    -- Integer VND amount from canonical pricing
        currency TEXT NOT NULL DEFAULT 'VND',
        provider TEXT NOT NULL DEFAULT 'payos',     -- 'payos' | 'vnpay' | 'manual'
        provider_order_id TEXT,                     -- External provider paymentLinkId or orderId
        checkout_url TEXT,
        payment_status TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'succeeded' | 'failed' | 'cancelled' | 'expired'
        idempotency_key TEXT UNIQUE,
        subscription_id INTEGER,
        invoice_id INTEGER,
        failure_reason TEXT,
        metadata_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        paid_at DATETIME,
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL
    );
    """)

    # 2. payment_webhook_events table (Durable Webhook Idempotency)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_webhook_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT NOT NULL,                     -- e.g. 'payos'
        event_id TEXT NOT NULL,                     -- unique transaction reference or event ID from provider
        event_type TEXT,
        order_code INTEGER,
        raw_payload TEXT NOT NULL,
        signature TEXT,
        status TEXT NOT NULL DEFAULT 'received',    -- 'received' | 'processing' | 'processed' | 'failed' | 'duplicate' | 'ignored'
        processing_error TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        processed_at DATETIME,
        UNIQUE(provider, event_id)
    );
    """)

    # 3. payment_audit_log table (Tamper-evident Audit Trail)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code INTEGER,
        internal_payment_id TEXT,
        action TEXT NOT NULL,                       -- 'order_created' | 'webhook_received' | 'payment_confirmed' | 'subscription_granted' | 'payment_failed' | 'payment_cancelled'
        actor_type TEXT NOT NULL,                   -- 'user' | 'webhook' | 'system' | 'admin'
        actor_id TEXT,
        details_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Indexes for fast, indexed lookups under concurrent load
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_order_code ON payment_orders(order_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_internal_id ON payment_orders(internal_payment_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_target ON payment_orders(target_type, target_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_orders_status ON payment_orders(payment_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_webhook_events_order_code ON payment_webhook_events(order_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pay_webhook_events_status ON payment_webhook_events(status);")

    conn.commit()
    conn.close()
    logger.info("Payment gateway migrations applied successfully.")


if __name__ == "__main__":
    run_migrations()
