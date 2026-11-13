import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
DB_PATH = Path(__file__).resolve().parent / "disease_detector.db"

def seed_plots():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM farm_plots")
    if cursor.fetchone()[0] == 0:
        print("Seeding initial farm plots...")
        plots = [
            (1, 1, None, "Tomato", "Cà chua", "Lô Cà Chua Bi Cherry 1", "Miền Bắc", 1.2, 1.2, "2026-09-15", "Canh tác trong nhà màng phủ lưới ngăn côn trùng", "active", "open"),
            (1, 1, None, "Tomato", "Cà chua", "Lô Cà Chua Beef VietGAP 2", "Miền Bắc", 1.5, 1.5, "2026-10-01", "Khu vực đang theo dõi phục hồi sau xử lý đốm lá", "active", "monitoring"),
            (1, 1, None, "Tomato", "Cà chua", "Lô Khảo Nghiệm Giống Mới", "Miền Bắc", 0.8, 0.8, "2026-10-20", "Thử nghiệm giống chịu nhiệt F1 vụ đông xuân", "active", "open"),
            (2, 1, None, "Potato", "Khoai tây", "Lô Khoai Tây Atlantic A1", "Tây Nguyên", 2.6, 2.6, "2026-09-20", "Luống thoát nước cao 30cm, tưới phun mưa tự động", "active", "open"),
            (2, 1, None, "Potato", "Khoai tây", "Lô Khoai Tây Atlantic A2", "Tây Nguyên", 2.6, 2.6, "2026-09-28", "Áp dụng quy trình phòng ngừa mốc sương định kỳ", "active", "open"),
            (3, 1, None, "Tea", "Chè", "Đồi Chè Shan Tuyết Cổ Thụ 1", "Tây Bắc", 6.0, 6.0, "2020-03-10", "Chè hữu cơ tiêu chuẩn Châu Âu, thu hái 1 tôm 2 lá", "active", "open"),
            (3, 1, None, "Tea", "Chè", "Đồi Chè Kim Tuyên Xuất Khẩu", "Tây Bắc", 6.0, 6.0, "2022-05-15", "Đang giai đoạn phát triển búp đông", "active", "open"),
        ]

        cursor.executemany("""
        INSERT INTO farm_plots (
            farm_id, user_id, organization_id, crop_id, crop_name,
            plot_name, region, area_hectares, area_hectare,
            planting_date, notes, status, monitoring_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, plots)
        print(f"Seeded {len(plots)} plots.")

        # Seed timeline events for Plot #2 (Lô Cà Chua Beef VietGAP 2)
        # Find ID of Plot 2
        cursor.execute("SELECT id FROM farm_plots WHERE plot_name = 'Lô Cà Chua Beef VietGAP 2'")
        plot_2_id = cursor.fetchone()[0]

        # Get latest diagnosis ID
        cursor.execute("SELECT id FROM diagnoses ORDER BY id DESC LIMIT 1")
        diag_row = cursor.fetchone()
        diag_id = diag_row[0] if diag_row else None

        events = [
            (plot_2_id, 1, None, "observation", None, "open", "Phát hiện vết chấm nâu rải rác trên tán lá dưới sau 2 ngày mưa ẩm liên tục.", "2026-10-28 08:30:00"),
            (plot_2_id, 1, None, "diagnosis", diag_id, "monitoring", "Chẩn đoán AI LeafLens xác định nguy cơ Đốm vòng sớm (Early Blight) 92.4%. Kích hoạt quy trình theo dõi phục hồi.", "2026-10-28 09:15:00"),
            (plot_2_id, 1, None, "observation", None, "monitoring", "Đã tiến hành cắt tỉa các lá già nhiễm bệnh, phun chế phẩm nano đồng hữu cơ lúc chiều mát.", "2026-10-29 16:45:00"),
            (plot_2_id, 1, None, "observation", None, "monitoring", "Kiểm tra sau 5 ngày: Vết bệnh đã khô se mép, chồi non trên ngọn sinh trưởng khỏe mạnh bình thường.", "2026-11-03 10:00:00")
        ]

        cursor.executemany("""
        INSERT INTO plot_timeline_events (
            plot_id, user_id, organization_id, event_type, diagnosis_id,
            monitoring_status, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, events)
        print(f"Seeded {len(events)} timeline events for Plot #{plot_2_id}.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    seed_plots()
