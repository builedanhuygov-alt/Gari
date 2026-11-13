"""
GARI Module 07 Migration: Expert Network & Consultation Workflows
- Adds missing 'status' column to expert_profiles.
- Adds consent_share_farm_data, organization_id, closed_at, rating, feedback_notes to expert_cases.
- Creates expert_case_activities table for audit logging.
- Adds proper indexes for rapid case filtering and expert isolation queries.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "disease_detector.db")

def run_migration():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Update expert_profiles
    cursor.execute("PRAGMA table_info(expert_profiles)")
    exp_profile_cols = {col[1] for col in cursor.fetchall()}
    if "status" not in exp_profile_cols:
        print("Adding column 'status' to expert_profiles...")
        cursor.execute("ALTER TABLE expert_profiles ADD COLUMN status TEXT DEFAULT 'active'")
    else:
        print("Column 'status' already exists in expert_profiles.")

    # 2. Update expert_cases
    cursor.execute("PRAGMA table_info(expert_cases)")
    case_cols = {col[1] for col in cursor.fetchall()}
    cases_columns_to_add = [
        ("consent_share_farm_data", "INTEGER DEFAULT 1"),
        ("organization_id", "INTEGER"),
        ("closed_at", "DATETIME"),
        ("rating", "REAL"),
        ("feedback_notes", "TEXT")
    ]
    for col_name, col_type in cases_columns_to_add:
        if col_name not in case_cols:
            print(f"Adding column '{col_name}' to expert_cases...")
            cursor.execute(f"ALTER TABLE expert_cases ADD COLUMN {col_name} {col_type}")
        else:
            print(f"Column '{col_name}' already exists in expert_cases.")

    # 3. Create expert_case_activities table for case lifecycle audit history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expert_case_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        actor_user_id INTEGER,
        action TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        details TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(case_id) REFERENCES expert_cases(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_case_activities_case ON expert_case_activities(case_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expert_cases_assigned_expert ON expert_cases(assigned_expert_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expert_cases_consent ON expert_cases(consent_share_farm_data)")

    conn.commit()
    conn.close()
    print("Module 07 migration completed successfully!")

if __name__ == "__main__":
    run_migration()
