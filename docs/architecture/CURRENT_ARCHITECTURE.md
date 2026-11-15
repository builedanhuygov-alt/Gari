# GARI 3.0 — CURRENT SYSTEM ARCHITECTURE BASELINE

## 1. TỔNG QUAN KIẾN TRÚC HIỆN TRẠNG (AS-IS)

GARI 3.0 hiện vận hành theo mô hình kiến trúc lai (**Hybrid Edge-to-Local AI Inference & Cloud Gateway Architecture**):

```
[Người dùng: Web Browser / Mobile Browser]
       │
       ▼ (HTTPS)
[Vercel Global Edge Network (sin1 - Singapore)]
       ├─ Static Frontend Assets: /frontend2/*.html, style.css, motion.css, app.js
       ├─ Edge Security Rewrites & Headers (vercel.json)
       │
       ├─ Serverless Function 1: api/index.py (Fluid Compute Python 3.12)
       │       └── GARI Auth Server (FastAPI ASGI)
       │               ├── Endpoints: /api/v1/auth/*, /api/auth/*, /api/v1/profile/*, /api/v1/voucher/*
       │               └── Primary Auth DB: Neon Serverless PostgreSQL (Singapore sin1)
       │                       └── Tables: users, sessions, security_events
       │
       └─ Serverless Function 2: api/[...path].js (Node.js Gateway Proxy)
               ├── Routes: /api/predict, /api/diagnose, /api/farms, /api/calendar, /api/weather, /uploads
               └── Proxy Forwarding via VERCEL_BACKEND_API_URL
                       │
                       ▼ (Cloudflare Tunnel - Zero Trust HTTPS)
       [Windows Local AI Inference Worker Daemon]
               ├── Process: scripts/run_ai_worker.py -> uvicorn api_server:app (Port 8000)
               ├── Model Directory: D:\leaf-diseases-detector-main\models (51 PyTorch/ONNX Checkpoints)
               ├── Preloaded Models: Combined ConvNeXt + Crop-specific (Coffee, Rice, Tomato, Pepper...)
               ├── Local Persistence: SQLite WAL (database/disease_detector.db - 86 Tables)
               ├── Microclimate Engine: Open-Meteo REST API Adapter (gari_weather_service.py)
               └── Phenology & Task Engine: gari_smart_calendar.py & gari_tasks.py
```

---

## 2. CÁC THÀNH PHẦN THỰC THI (RUNTIME COMPONENTS)

### A. Vercel Frontend & Serverless Edge (`sin1`)
- **Hosting:** Vercel Hobby/Team plan (`bui11 / gari-team`).
- **Region:** `sin1` (Singapore) đặt gần máy chủ Neon PostgreSQL để tối ưu RTT (khoảng 30-60ms).
- **Frontend Pages:** 30 file HTML tĩnh tại `frontend2/`, sử dụng ES6 modules (`app.js`, `voucher-banner.js`, `motion.css`).
- **Rewrite Proxy:** `api/[...path].js` nhận toàn bộ request nông nghiệp và forward về `VERCEL_BACKEND_API_URL` với cơ chế stream buffering an toàn chống deadlock.

### B. Dịch vụ Xác thực Độc lập (`auth-server`)
- **Vị trí:** `auth-server/app/main.py`, thực thi trên Vercel Serverless Function qua `api/index.py`.
- **Cơ sở dữ liệu xác thực:** Neon Serverless PostgreSQL (`ep-red-night-b3zzbyoh-pooler.c-4.ap-southeast-1.aws.neon.tech`).
- **Bảo mật:** HttpOnly Cookie `gari_session`, CSRF Token qua header `X-CSRF-Token`, mật khẩu băm chuẩn Argon2id / Bcrypt.

### C. Máy chủ Suy luận AI Cục bộ (Windows AI Worker Daemon)
- **Vị trí:** `scripts/run_ai_worker.py` điều khiển `api_server.py` chạy trên `127.0.0.1:8000`.
- **Thư viện Model:** 51 checkpoint phân bố theo các dòng:
  - Model nhận diện lá (`is_leaf` gate).
  - Model tổng hợp toàn diện (Combined ConvNeXt / MobileNetV4).
  - Model chuyên biệt theo cây trồng (Cà phê, Lúa, Cà chua, Hồ tiêu, Sầu riêng, Ớt, Bắp).
- **Hầm kết nối Cloudflare Tunnel:** `cloudflared.exe` ánh xạ cổng cục bộ `8000` ra địa chỉ công khai an toàn được Vercel Gateway gọi.

---

## 3. ĐÁNH GIÁ ĐIỂM NGHẼN VÀ RỦI RO KIẾN TRÚC

1. **Phụ thuộc kết nối Tunnel:** Nếu máy trạm cục bộ tắt hoặc Cloudflare Tunnel bị ngắt, Vercel Gateway cần fallback sang Cloud AI Worker nhưng hiện tại Cloud Worker chưa được triển khai chính thức.
2. **Đồng bộ Session giữa Neon và SQLite:** `auth-server` ghi user và session vào Neon PostgreSQL, trong khi một số module nông nghiệp cũ của `api_server.py` trước đây dựa vào SQLite cục bộ. Hiện đã có bridge xác thực token Neon trong `gari_auth.py`, cần duy trì nghiêm ngặt.
3. **Phân tách trách nhiệm API:** `auth-server` xử lý đăng ký/đăng nhập/voucher/profile, trong khi `api_server.py` xử lý chẩn đoán, nông trại, lịch mùa vụ và thời tiết.
