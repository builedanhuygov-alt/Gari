"""
GARI AI LAB — Persistent Database Migrations Engine (migrations_v2.py)
Idempotent migration runner for local SQLite persistence.
Creates backup before applying changes.
"""

import logging
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_migrations")

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "disease_detector.db"
BACKUP_DIR = DB_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def backup_database() -> Path:
    """Create a timestamped backup of the database before applying migrations."""
    if not DB_PATH.exists():
        logger.info("Database file does not exist yet; skipping backup.")
        return None
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"disease_detector_backup_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_file)
    logger.info("Created pre-migration backup at: %s", backup_file)
    return backup_file


def run_migrations():
    """Apply schema migrations idempotently."""
    backup_database()

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    logger.info("Applying tables and column migrations...")

    # 1. users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT,
        name TEXT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        phone TEXT,
        account_type TEXT DEFAULT 'Nông hộ',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Ensure columns exist on users
    user_cols = [r[1] for r in cursor.execute("PRAGMA table_info(users)").fetchall()]
    if "full_name" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
    if "password_hash" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "phone" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    if "account_type" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN account_type TEXT DEFAULT 'Nông hộ'")

    # 2. farms table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        location TEXT,
        province TEXT,
        area_hectare REAL DEFAULT 1.0,
        primary_crop TEXT DEFAULT 'Tomato',
        variety TEXT,
        soil_type TEXT,
        irrigation_type TEXT,
        status TEXT DEFAULT 'active',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    farm_cols = [r[1] for r in cursor.execute("PRAGMA table_info(farms)").fetchall()]
    if "user_id" not in farm_cols:
        cursor.execute("ALTER TABLE farms ADD COLUMN user_id INTEGER DEFAULT 1")

    # 3. farm_plots table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farm_plots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farm_id INTEGER NOT NULL,
        user_id INTEGER DEFAULT 1,
        crop_id TEXT,
        crop_name TEXT,
        plot_name TEXT NOT NULL,
        area_hectares REAL DEFAULT 0.5,
        area_hectare REAL DEFAULT 0.5,
        planting_date TEXT,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    plot_cols = [r[1] for r in cursor.execute("PRAGMA table_info(farm_plots)").fetchall()]
    if "user_id" not in plot_cols:
        cursor.execute("ALTER TABLE farm_plots ADD COLUMN user_id INTEGER DEFAULT 1")
    if "crop_name" not in plot_cols:
        cursor.execute("ALTER TABLE farm_plots ADD COLUMN crop_name TEXT")
    if "area_hectare" not in plot_cols:
        cursor.execute("ALTER TABLE farm_plots ADD COLUMN area_hectare REAL DEFAULT 0.5")

    # 4. diagnoses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS diagnoses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        farm_id INTEGER,
        plot_id INTEGER,
        farm_name TEXT,
        crop_id TEXT NOT NULL,
        crop_name TEXT NOT NULL,
        image_path TEXT,
        image_preview TEXT,
        predicted_disease TEXT NOT NULL,
        disease_name_vi TEXT,
        confidence REAL NOT NULL,
        confidence_percent REAL,
        severity TEXT DEFAULT 'MEDIUM',
        top_predictions_json TEXT,
        model_name TEXT,
        model_arch TEXT,
        inference_time_ms REAL,
        device TEXT,
        user_notes TEXT,
        treatment_status TEXT DEFAULT 'pending',
        is_verified_by_expert BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE SET NULL,
        FOREIGN KEY (plot_id) REFERENCES farm_plots (id) ON DELETE SET NULL
    );
    """)

    diag_cols = [r[1] for r in cursor.execute("PRAGMA table_info(diagnoses)").fetchall()]
    if "user_id" not in diag_cols:
        cursor.execute("ALTER TABLE diagnoses ADD COLUMN user_id INTEGER DEFAULT 1")
    if "plot_id" not in diag_cols:
        cursor.execute("ALTER TABLE diagnoses ADD COLUMN plot_id INTEGER")

    # 5. user_sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    # 6. password_resets table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL,
        used BOOLEAN DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    # 7. notifications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        notification_type TEXT DEFAULT 'info',
        is_read BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    # 8. expert_cases table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expert_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER DEFAULT 1,
        diagnosis_id INTEGER,
        farm_id INTEGER,
        farm_name TEXT,
        farmer_name TEXT NOT NULL,
        phone TEXT,
        crop_name TEXT NOT NULL,
        suspected_disease TEXT,
        symptoms_description TEXT NOT NULL,
        field_conditions TEXT,
        image_preview TEXT,
        status TEXT DEFAULT 'Submitted',
        expert_notes TEXT,
        assigned_expert TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (diagnosis_id) REFERENCES diagnoses (id) ON DELETE SET NULL,
        FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE SET NULL
    );
    """)

    expert_cols = [r[1] for r in cursor.execute("PRAGMA table_info(expert_cases)").fetchall()]
    if "user_id" not in expert_cols:
        cursor.execute("ALTER TABLE expert_cases ADD COLUMN user_id INTEGER DEFAULT 1")

    # 9. Indexes for optimal query execution
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON user_sessions(expires_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_farms_user_id ON farms(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_plots_farm_id ON farm_plots(farm_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_farm_plots_user_id ON farm_plots(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnoses_user_id ON diagnoses(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_diagnoses_farm_id ON diagnoses(farm_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);")

    conn.commit()
    conn.close()
    logger.info("All migrations completed successfully!")


if __name__ == "__main__":
    run_migrations()
