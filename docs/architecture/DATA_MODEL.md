# GARI 3.0 — DATA MODEL & DATABASE INVENTORY

## 1. HỆ CƠ SỞ DỮ LIỆU LAI (HYBRID DATABASE ARCHITECTURE)

GARI 3.0 kết hợp hai lớp lưu trữ dữ liệu có nhiệm vụ rõ ràng:

1. **Neon Serverless PostgreSQL (Singapore `sin1`):** Lưu trữ định danh người dùng, phiên làm việc (sessions), hạn mức dịch vụ, thông tin đăng ký và nhật ký bảo mật. Đảm bảo tính toàn vẹn và độ sẵn sàng cao trên toàn cầu.
2. **SQLite Edge Database (`database/disease_detector.db`):** Lưu trữ dữ liệu nông nghiệp sâu, nông trại, lô đất, lịch mùa vụ, dữ liệu chẩn đoán bệnh, bản đồ số và thư viện tri thức cây trồng.

---

## 2. NEON POSTGRESQL TABLES (PRIMARY AUTH & ACCOUNTS)

### `users`
- `id` (INTEGER / SERIAL PRIMARY KEY)
- `email` (VARCHAR UNIQUE NOT NULL)
- `password_hash` (VARCHAR NOT NULL)
- `full_name` (VARCHAR)
- `account_type` (VARCHAR: `farmer`, `cooperative`, `expert`, `enterprise`, `admin`)
- `role` (VARCHAR: `user`, `admin`, `expert`)
- `is_vip` (BOOLEAN DEFAULT FALSE)
- `vip_expires_at` (TIMESTAMP WITH TIME ZONE)
- `created_at`, `updated_at` (TIMESTAMP WITH TIME ZONE)

### `sessions`
- `id` (INTEGER / SERIAL PRIMARY KEY)
- `token` (VARCHAR UNIQUE NOT NULL)
- `user_id` (INTEGER REFERENCES users(id) ON DELETE CASCADE)
- `expires_at` (TIMESTAMP WITH TIME ZONE NOT NULL)
- `ip_address` (VARCHAR)
- `user_agent` (TEXT)
- `created_at` (TIMESTAMP WITH TIME ZONE)

### `security_events`
- `id` (INTEGER / SERIAL PRIMARY KEY)
- `user_id` (INTEGER REFERENCES users(id))
- `event_type` (VARCHAR: `login_success`, `login_failed`, `password_change`, `voucher_activated`...)
- `ip_address` (VARCHAR)
- `details` (TEXT / JSONB)
- `created_at` (TIMESTAMP WITH TIME ZONE)

---

## 3. SQLITE DATABASE TABLES (AGRICULTURAL DOMAIN)

Gồm 86 bảng, trong đó các thực thể cốt lõi cho GARI 3.0 Core bao gồm:

### `farms`
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `user_id` (INTEGER NOT NULL)
- `organization_id` (INTEGER)
- `name` (TEXT NOT NULL)
- `province` (TEXT NOT NULL)
- `location` (TEXT)
- `latitude` (REAL)
- `longitude` (REAL)
- `altitude_m` (REAL)
- `terrain` (TEXT)
- `water_source` (TEXT)
- `primary_crop` (TEXT NOT NULL)
- `variety` (TEXT)
- `tree_age_years` (REAL)
- `growth_stage` (TEXT)
- `area_hectare` (REAL)
- `soil_type` (TEXT)
- `irrigation_type` (TEXT)
- `status` (TEXT DEFAULT 'active')
- `created_at`, `updated_at` (DATETIME)

### `cultivation_tasks`
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `user_id` (INTEGER NOT NULL)
- `farm_id` (INTEGER NOT NULL REFERENCES farms(id) ON DELETE CASCADE)
- `crop_id` (TEXT)
- `title` (TEXT NOT NULL)
- `description` (TEXT)
- `due_date` (TEXT NOT NULL: YYYY-MM-DD)
- `time_window` (TEXT)
- `growth_stage` (TEXT)
- `task_type` (TEXT: `routine`, `fertilizing`, `watering`, `spraying`, `treatment`, `scouting`, `pruning`, `harvesting`)
- `priority` (TEXT: `urgent`, `high`, `medium`, `low`)
- `status` (TEXT: `pending`, `completed`, `cancelled`)
- `rationale` (TEXT)
- `conditions` (TEXT)
- `source` (TEXT)
- `schedule_origin` (TEXT: `stage_based`, `weather_adaptive`, `user_custom`, `cyclic`)
- `completed_at` (DATETIME)
- `created_at`, `updated_at` (DATETIME)

### `diagnoses`
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `user_id` (INTEGER NOT NULL)
- `farm_id` (INTEGER REFERENCES farms(id))
- `crop_id` (TEXT)
- `predicted_disease` (TEXT)
- `disease_name_vi` (TEXT)
- `confidence` (REAL)
- `severity` (TEXT)
- `image_path` (TEXT)
- `heatmap_path` (TEXT - Grad-CAM)
- `model_version` (TEXT)
- `created_at` (DATETIME)
