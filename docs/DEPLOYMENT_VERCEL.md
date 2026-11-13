# GARI AgriTech Platform — Vercel Deployment Guide

Hướng dẫn chi tiết triển khai GARI Web Frontend và kết nối Backend trên hạ tầng Vercel Edge Network.

---

## 1. Kiến trúc Hệ thống (System Architecture)

```
                       ┌────────────────────────────┐
                       │   End Users / Agronomists  │
                       └──────────────┬─────────────┘
                                      │
                                      ▼
                        https://app.gari.vn (Vercel)
         ┌────────────────────────────┴───────────────────────────┐
         │                                                        │
         ▼                                                        ▼
┌──────────────────┐                                     ┌──────────────────┐
│  Static Assets   │                                     │ /api/* Rewrites  │
│  frontend2/*.html│                                     │ Proxy to Backend │
│  frontend2/css/  │                                     └────────┬─────────┘
│  frontend2/js/   │                                              │
└──────────────────┘                                              ▼
                                      VERCEL_BACKEND_API_URL (GARI Backend)
                                                  ┌───────────────────────────────┐
                                                  │ • FastAPI Engine              │
                                                  │ • PyTorch/ONNX Diagnosis      │
                                                  │ • Gemini Explainer Chatbot    │
                                                  │ • SQLite / PostgreSQL DB      │
                                                  │ • Firebase Auth & RBAC        │
                                                  └───────────────────────────────┘
```

---

## 2. Chuẩn bị Trước khi Triển khai

1. **Tài khoản Vercel**: Đăng nhập [vercel.com](https://vercel.com).
2. **Cài đặt Vercel CLI (tùy chọn)**:
   ```bash
   npm i -g vercel
   ```
3. **Repository**: Đảm bảo toàn bộ mã nguồn `frontend2`, `vercel.json` đã được đẩy lên GitHub/GitLab.

---

## 3. Cấu hình Vercel (`vercel.json`)

Tệp `vercel.json` tại thư mục gốc repository đã được tối ưu hóa cho môi trường Production:

- **Clean URLs**: Tự động chuyển đổi URLs đẹp không đuôi `.html` (ví dụ: `/crops`, `/predict`, `/host`, `/expert`).
- **Security Headers**:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(self), microphone=(), geolocation=(self)`
- **Asset Caching**: Bộ đệm vĩnh viễn `Cache-Control: public, max-age=31536000, immutable` cho tài nguyên tĩnh trong `/frontend2/assets/`.
- **API Rewrites**: Proxy trực tiếp tất cả các lệnh gọi `/api/:path*` về Backend máy chủ AI mà không gặp lỗi CORS.

---

## 4. Các bước Triển khai qua Vercel Dashboard

1. Nhấp **Add New Project** trong Vercel Dashboard.
2. Chọn repository `leaf-diseases-detector` (hoặc `gari-platform`).
3. Cấu hình Project:
   - **Framework Preset**: Other
   - **Root Directory**: `./` (để nguyên thư mục gốc)
   - **Build Command**: Để trống (hoặc `npm run build` nếu có bước nén asset)
   - **Output Directory**: `./`
4. Cấu hình Environment Variables:
   - `VERCEL_BACKEND_API_URL`: URL gốc của FastAPI backend đang hoạt động (ví dụ: `https://gari-api-production.example.com`; không thêm `/api`). Vercel function `api/[...path].js` đọc biến này khi chạy và chuyển tiếp các yêu cầu cùng origin `/api/*`.
   - Không dùng `localhost`, `127.0.0.1` hoặc hostname chưa có DNS. Xác nhận `GET <backend>/health` trả về 200 trước khi deploy frontend.
   - Nếu dùng Firebase Email/Password, cấu hình ở backend: `FIREBASE_PROJECT_ID`, `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_APP_ID` và **một trong** `FIREBASE_CREDENTIALS_JSON` hoặc `FIREBASE_CREDENTIALS_PATH`. Chỉ service account ở backend; không đặt service account trong Vercel frontend.
   - Backend production phải đặt `ALLOWED_ORIGINS=https://gari-team.vercel.app` (thêm custom domain nếu có), `APP_ENV=production`, `SESSION_SECRET` và `JWT_SECRET` đủ mạnh.
5. Bấm **Deploy**.

---

## 5. Cấu hình Tên miền Tùy chỉnh (Custom Domain)

1. Đi tới **Project Settings** → **Domains**.
2. Thêm domain: `app.gari.vn` hoặc `gari.vn`.
3. Cập nhật bản ghi DNS tại nhà cung cấp tên miền:
   - **CNAME**: `app` trỏ đến `cname.vercel-dns.com`
   - Hoặc **A record**: `@` trỏ đến `76.76.21.21`

---

## 6. Kiểm tra Sau khi Triển khai (Post-Deployment Verification)

Sau khi deploy thành công, hãy kiểm tra danh sách routes:

| Route | Mục đích | Trạng thái dự kiến |
|---|---|---|
| `https://app.gari.vn/` | Trang chủ / Dashboard nông hộ | HTTP 200, tải giao diện SaaS |
| `https://app.gari.vn/predict` | Chẩn đoán thông minh & Trợ lý AI | HTTP 200, camera / upload hoạt động |
| `https://app.gari.vn/host-login` | Đăng nhập Host Administrator | HTTP 200, bảo mật cao |
| `https://app.gari.vn/host` | GARI Host Console | HTTP 200 (yêu cầu quyền Host Admin) |
| `https://app.gari.vn/expert` | GARI Expert Portal | HTTP 200 (yêu cầu quyền Chuyên gia) |
| `https://app.gari.vn/api/health` | Kiểm tra kết nối Backend qua Proxy | HTTP 200 `{"status": "ok"}` |
