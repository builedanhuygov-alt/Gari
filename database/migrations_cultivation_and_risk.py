"""
Migration script: Cultivation Tasks and User Risk Acknowledgments
"""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path(__file__).resolve().parent / "disease_detector.db"

def run_migration():
    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # 1. Cultivation Tasks Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cultivation_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        organization_id INTEGER,
        farm_id INTEGER,
        plot_id INTEGER,
        crop_id TEXT,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT NOT NULL,
        priority TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'pending',
        task_type TEXT DEFAULT 'routine',
        creator_user_id INTEGER,
        assignee_user_id INTEGER,
        completed_at DATETIME,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE SET NULL,
        FOREIGN KEY (plot_id) REFERENCES farm_plots (id) ON DELETE SET NULL
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_user ON cultivation_tasks(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_farm ON cultivation_tasks(farm_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_plot ON cultivation_tasks(plot_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_status ON cultivation_tasks(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_due ON cultivation_tasks(due_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cultivation_tasks_org ON cultivation_tasks(organization_id);")

    # 2. User Risk Acknowledgments & Field Observations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_risk_acknowledgments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        farm_id INTEGER,
        plot_id INTEGER,
        status TEXT NOT NULL DEFAULT 'acknowledged',
        user_observation TEXT,
        severity_observed TEXT,
        acknowledged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        resolved_at DATETIME,
        FOREIGN KEY (alert_id) REFERENCES risk_alerts (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (farm_id) REFERENCES farms (id) ON DELETE SET NULL,
        FOREIGN KEY (plot_id) REFERENCES farm_plots (id) ON DELETE SET NULL
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_ack_alert ON user_risk_acknowledgments(alert_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_ack_user ON user_risk_acknowledgments(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_ack_farm ON user_risk_acknowledgments(farm_id);")

    # Seed initial cultivation tasks if empty
    cursor.execute("SELECT COUNT(*) FROM cultivation_tasks")
    count = cursor.fetchone()[0]
    if count == 0:
        print("Seeding initial cultivation tasks...")
        # Get first user and farm
        cursor.execute("SELECT id FROM users LIMIT 1")
        user_row = cursor.fetchone()
        user_id = user_row[0] if user_row else 1

        cursor.execute("SELECT id FROM farms LIMIT 1")
        farm_row = cursor.fetchone()
        farm_id = farm_row[0] if farm_row else 1

        initial_tasks = [
            (
                user_id, None, farm_id, None, "Tomato",
                "Kiểm tra mặt dưới lá cà chua sau mưa rào",
                "Độ ẩm 82% thuận lợi cho nấm thán thư và đốm vi khuẩn phát triển. Cần kiểm tra kỹ các tán lá sát mặt đất.",
                "2026-11-05", "high", "pending", "scouting", user_id, user_id, None, "Kiểm tra kỹ lô 1 và lô 2"
            ),
            (
                user_id, None, farm_id, None, "Tomato",
                "Bón thúc vi lượng kali và canxi bo đợt 2",
                "Tăng cường độ cứng phiến lá, giúp cuống hoa đậu chắc và hạn chế nứt quả trong điều kiện thời tiết ẩm ướt.",
                "2026-11-08", "medium", "pending", "fertilizing", user_id, user_id, None, "Dùng phân hữu cơ vi sinh VietGAP"
            ),
            (
                user_id, None, farm_id, None, "Potato",
                "Vun gốc và kiểm tra thoát nước rãnh luống",
                "Tránh ngập úng rễ cục bộ khi có mưa lớn, ngăn ngừa bệnh lở cổ rễ và mốc sương khoai tây.",
                "2026-11-12", "medium", "pending", "routine", user_id, user_id, None, "Độ cao luống đạt chuẩn 25-30cm"
            ),
            (
                user_id, None, farm_id, None, "Tea",
                "Tỉa cành thông thoáng và vệ sinh dụng cụ thu hái",
                "Loại bỏ cành sâu bệnh, làm sạch kéo cắt bằng cồn 70 độ để tránh lây nhiễm chéo nấm chấm xám.",
                "2026-11-02", "low", "completed", "pruning", user_id, user_id, "2026-11-02 16:30:00", "Đã hoàn thành đúng lịch kỹ thuật"
            )
        ]

        cursor.executemany("""
        INSERT INTO cultivation_tasks (
            user_id, organization_id, farm_id, plot_id, crop_id,
            title, description, due_date, priority, status, task_type,
            creator_user_id, assignee_user_id, completed_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_tasks)
        print(f"Seeded {len(initial_tasks)} cultivation tasks.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()
