"""
GARI Module 06 Migration: Tasks & Crop Calendar Enhancements
- Adds diagnosis_id, cycle_id, recurrence_rule, recurrence_interval, parent_task_id,
  completed_by_user_id, reminder_status, reminder_sent_at, timezone to cultivation_tasks.
- Creates task_activities table for audit logging.
- Adds appropriate indexes for fast queries.
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "disease_detector.db")

def run_migration():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Inspect existing columns in cultivation_tasks
    cursor.execute("PRAGMA table_info(cultivation_tasks)")
    existing_cols = {col[1] for col in cursor.fetchall()}

    columns_to_add = [
        ("diagnosis_id", "INTEGER"),
        ("cycle_id", "INTEGER"),
        ("recurrence_rule", "TEXT DEFAULT 'none'"),
        ("recurrence_interval", "INTEGER DEFAULT 1"),
        ("parent_task_id", "INTEGER"),
        ("completed_by_user_id", "INTEGER"),
        ("reminder_status", "TEXT DEFAULT 'pending'"),
        ("reminder_sent_at", "DATETIME"),
        ("timezone", "TEXT DEFAULT 'Asia/Ho_Chi_Minh'")
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_cols:
            print(f"Adding column '{col_name}' to cultivation_tasks...")
            cursor.execute(f"ALTER TABLE cultivation_tasks ADD COLUMN {col_name} {col_type}")
        else:
            print(f"Column '{col_name}' already exists in cultivation_tasks.")

    # 2. Create task_activities table for activity audit history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS task_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        actor_user_id INTEGER,
        action TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(task_id) REFERENCES cultivation_tasks(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_activities_task_id ON task_activities(task_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON cultivation_tasks(due_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON cultivation_tasks(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_org_id ON cultivation_tasks(organization_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_diagnosis_id ON cultivation_tasks(diagnosis_id)")

    conn.commit()
    conn.close()
    print("Module 06 migration completed successfully!")

if __name__ == "__main__":
    run_migration()
