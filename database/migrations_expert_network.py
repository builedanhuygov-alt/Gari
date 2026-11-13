import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

def migrate(db_path='database/disease_detector.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Running GARI Expert Network & RBAC Database Migrations...")

    # 1. Add is_expert column to users
    user_cols = [r[1] for r in cursor.execute("PRAGMA table_info(users)").fetchall()]
    if "is_expert" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_expert BOOLEAN DEFAULT 0;")
        print(" - Added is_expert column to users table")

    # 2. expert_profiles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expert_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        display_title TEXT NOT NULL,
        institution TEXT NOT NULL,
        degree TEXT,
        specialization TEXT NOT NULL,
        primary_crops_json TEXT NOT NULL,
        farming_regions_json TEXT NOT NULL,
        bio TEXT,
        verification_status TEXT DEFAULT 'approved',
        verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        verified_by_host_id INTEGER,
        is_active BOOLEAN DEFAULT 1,
        rating REAL DEFAULT 5.0,
        cases_resolved_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    print(" - Ensured expert_profiles table")

    # 3. expert_applications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expert_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT,
        institution TEXT NOT NULL,
        degree TEXT NOT NULL,
        specialization TEXT NOT NULL,
        primary_crops_json TEXT NOT NULL,
        farming_regions_json TEXT NOT NULL,
        bio TEXT,
        certificate_url TEXT,
        status TEXT DEFAULT 'submitted',
        rejection_reason TEXT,
        reviewed_by_host_id INTEGER,
        reviewed_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    print(" - Ensured expert_applications table")

    # 4. expert_case_messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expert_case_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        sender_user_id INTEGER NOT NULL,
        sender_role TEXT NOT NULL,
        sender_name TEXT,
        message TEXT NOT NULL,
        attachments_json TEXT,
        is_internal_note BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (case_id) REFERENCES expert_cases(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_user_id) REFERENCES users(id)
    );
    """)
    print(" - Ensured expert_case_messages table")

    # 5. Expand expert_cases columns
    case_cols = [r[1] for r in cursor.execute("PRAGMA table_info(expert_cases)").fetchall()]
    new_case_cols = [
        ("assigned_expert_id", "INTEGER"),
        ("resolution_notes", "TEXT"),
        ("resolved_at", "DATETIME"),
        ("user_consent_history", "BOOLEAN DEFAULT 1"),
        ("urgency", "TEXT DEFAULT 'medium'")
    ]
    for col, col_type in new_case_cols:
        if col not in case_cols:
            cursor.execute(f"ALTER TABLE expert_cases ADD COLUMN {col} {col_type};")
            print(f" - Added {col} to expert_cases table")

    # 6. Expand notifications columns
    notif_cols = [r[1] for r in cursor.execute("PRAGMA table_info(notifications)").fetchall()]
    if "target_url" not in notif_cols:
        cursor.execute("ALTER TABLE notifications ADD COLUMN target_url TEXT;")
        print(" - Added target_url to notifications table")

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expert_profiles_user ON expert_profiles(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expert_apps_user ON expert_applications(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expert_apps_status ON expert_applications(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_case_messages_case ON expert_case_messages(case_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expert_cases_expert ON expert_cases(assigned_expert_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_user_read ON notifications(user_id, is_read);")

    conn.commit()
    conn.close()
    print("Migrations completed successfully!")

if __name__ == '__main__':
    migrate()
