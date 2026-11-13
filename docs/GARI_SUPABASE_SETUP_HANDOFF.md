# GARI AgriTech AI Lab — Supabase Auth Handoff & Dashboard Setup Guide

**Document ID:** GARI-HANDOFF-SUPABASE-2026-01  
**Project:** GARI AgriTech AI Lab  
**Repository:** `D:\leaf-diseases-detector-main`  
**Handoff Scope:** Supabase Dashboard Configuration & Staging Activation  
**Author:** Antigravity AI Systems Architect  
**Handoff Recipients:** User & ChatGPT Configuration Assistant  
**Date:** 2026-11-11  
**Current Milestone:** **LOCAL IMPLEMENTATION COMPLETED → SUPABASE CONFIGURATION REQUIRED**  

---

## A. NHỮNG HẠNG MỤC ĐÃ HOÀN THÀNH TẠI LOCAL CODEBASE

Mọi công tác thiết kế kiến trúc, mã nguồn adapter và bài test bảo mật cục bộ đã được hoàn tất 100%:

1. **Khảo sát toàn diện hệ thống (Phase 0):**
   - Đã kiểm toán 280 route FastAPI cần xác thực.
   - Xác định 59 bảng dữ liệu nghiệp vụ SQLite (`database/disease_detector.db`) gắn với `user_id INTEGER`.
   - Bảo toàn 100% cơ sở dữ liệu SQLite nghiệp vụ; không xóa hay chuyển đổi mật khẩu cũ.
2. **Thiết kế Schema PostgreSQL & RLS (Phase 1):**
   - Tệp migration SQL độc lập: [`docs/GARI_SUPABASE_HYBRID_SCHEMA.sql`](file:///d:/leaf-diseases-detector-main/docs/GARI_SUPABASE_HYBRID_SCHEMA.sql).
   - Thiết kế 4 bảng cốt lõi: `profiles`, `user_preferences`, `gari_identity_links`, `account_provisioning`.
   - Bật RLS và chính sách bảo vệ hàng dựa trên `auth.uid() = id`.
3. **Cơ sở dữ liệu Lai SQLite (Phase 4):**
   - Đã áp dụng migration an toàn tạo bảng cầu nối `gari_identity_links` và `account_provisioning` trên SQLite cục bộ.
4. **Mã nguồn Frontend Supabase Client (Phase 2):**
   - Tệp adapter: [`frontend2/supabase-client.js`](file:///d:/leaf-diseases-detector-main/frontend2/supabase-client.js) tích hợp `@supabase/supabase-js@2.48.0` (ESM).
   - Cơ chế phòng vệ: Bọc timeout (`withTimeout`), bảo đảm khối `finally` luôn mở khóa nút đăng ký, chống gửi trùng lặp, dịch toàn bộ thông báo lỗi sang tiếng Việt.
5. **Mã nguồn Xác thực Backend FastAPI (Phase 3):**
   - Đã cài đặt thư viện `PyJWT>=2.10.0` và tích hợp `PyJWKClient` trong [`gari_auth.py`](file:///d:/leaf-diseases-detector-main/gari_auth.py).
   - Hàm `verify_supabase_jwt(token)` xác minh chữ ký bất đối xứng qua JWKS (RS256/ES256), kiểm tra `iss`, `aud == 'authenticated'`, `exp`, và `sub`.
   - Hàm `resolve_or_provision_supabase_user()` tự động ánh xạ bất biến `supabase_uid (UUID) -> sqlite_user_id (INTEGER)`.
   - Đã bổ sung 2 API endpoint trong [`api_server.py`](file:///d:/leaf-diseases-detector-main/api_server.py):
     - `GET /api/auth/supabase-config` (Trả về URL và Publishable Key an toàn cho browser).
     - `POST /api/auth/supabase-sync` (Đồng bộ tài khoản sau khi đăng ký/đăng nhập).
6. **Kiểm thử tự động toàn diện (Phase 6):**
   - Bộ test Python 20 kịch bản ([`tests/test_supabase_auth_suite.py`](file:///d:/leaf-diseases-detector-main/tests/test_supabase_auth_suite.py)): **20/20 PASS (100%)**.
   - Bộ test Node.js 7 kịch bản client ([`tests/test_supabase_client_unit.js`](file:///d:/leaf-diseases-detector-main/tests/test_supabase_client_unit.js)): **7/7 PASS (100%)**.
   - **Tuyệt đối tuân thủ Zero-PHP:** Không sử dụng bất kỳ đoạn mã hay fixture PHP nào.

---

## B. NHỮNG THAO TÁC CẦN THỰC HIỆN TRÊN SUPABASE DASHBOARD

*(Dành cho Người dùng và ChatGPT khi thao tác trên giao diện điều khiển Supabase)*

### Bước 1: Tạo hoặc chọn Project Supabase
1. Đăng nhập [https://supabase.com/dashboard](https://supabase.com/dashboard).
2. Tạo một Project mới (đặt tên ví dụ: `gari-preview`).
3. Chọn khu vực (Region) gần nhất: **Singapore (`ap-southeast-1`)**.
4. Đặt mật khẩu cơ sở dữ liệu mạnh và lưu trữ an toàn.

### Bước 2: Áp dụng SQL Schema Migration
1. Trong menu bên trái của Dashboard, bấm vào mục **SQL Editor**.
2. Bấm **New query**.
3. Mở file [`docs/GARI_SUPABASE_HYBRID_SCHEMA.sql`](file:///d:/leaf-diseases-detector-main/docs/GARI_SUPABASE_HYBRID_SCHEMA.sql) trong project GARI, copy toàn bộ nội dung và dán vào SQL Editor.
4. Bấm nút **Run** (màu xanh lá).
5. Kiểm tra mục **Table Editor** để xác nhận 4 bảng đã xuất hiện trong schema `public`:
   - `profiles`
   - `user_preferences`
   - `gari_identity_links`
   - `account_provisioning`
6. Kiểm tra biểu tượng chiếc khiên **RLS enabled** cạnh cả 4 bảng.

### Bước 3: Cấu hình Authentication & URL Configuration
1. Vào mục **Authentication** -> **URL Configuration**:
   - **Site URL:** Nhập URL Preview Vercel của bạn (hoặc `http://localhost:8000` cho thử nghiệm local).
   - **Redirect URLs:** Thêm:
     - `http://localhost:8000/**`
     - `https://*.vercel.app/**`
2. Vào mục **Authentication** -> **Providers** -> **Email**:
   - **Enable Email provider:** Bật (ON).
   - **Confirm email:**
     - Nếu bật: Người dùng phải bấm link xác nhận gửi về email trước khi đăng nhập được.
     - Nếu tắt (khuyên dùng trong giai đoạn Preview test nhanh): Đăng ký xong có session ngay.

### Bước 4: Lấy thông tin Project API Keys
1. Vào mục **Project Settings** (biểu tượng bánh răng) -> **API**:
   - **Project URL:** Dạng `https://xxxxxxxxxxxxxxxxxxxx.supabase.co`.
   - **Project API Keys:** Lấy khóa `anon` / `public` (Bắt đầu bằng `sbp_...` hoặc `eyJ...`).
   - *(Lưu ý: Tuyệt đối KHÔNG sử dụng hay chia sẻ khóa `service_role` / secret key).*

---

## C. DANH SÁCH BIẾN MÔI TRƯỜNG CẦN CẤU HÌNH

Sau khi hoàn tất trên Supabase Dashboard, cấu hình các biến sau vào tệp `.env` cục bộ (và trên Vercel Preview Environment Variables):

```env
# 1. Supabase Project URL
SUPABASE_URL=https://<your-project-ref>.supabase.co

# 2. Supabase Publishable / Anon Key (Public cho Frontend & Backend)
SUPABASE_PUBLISHABLE_KEY=sbp_xxxxxxxxxxxxxxxxxxxx

# 3. Supabase JWKS Endpoint (Tự động suy ra nếu để trống)
SUPABASE_JWKS_URL=https://<your-project-ref>.supabase.co/auth/v1/.well-known/jwks.json
```

*(Tuyệt đối không commit tệp `.env` lên Git).*

---

## D. NHỮNG THAO TÁC CẦN NGƯỜI DÙNG XÁC NHẬN

1. Xác nhận đã tạo Project Supabase Preview độc lập (không dùng chung project sản xuất của ứng dụng khác).
2. Xác nhận đã chạy thành công script SQL [`docs/GARI_SUPABASE_HYBRID_SCHEMA.sql`](file:///d:/leaf-diseases-detector-main/docs/GARI_SUPABASE_HYBRID_SCHEMA.sql).
3. Xác nhận lựa chọn chính sách: Có bắt buộc người dùng xác nhận email (`Confirm email`) hay cho phép đăng nhập tức thì trong đợt thử nghiệm Preview.

---

## E. NHỮNG ĐIỀU TUYỆT ĐỐI CẤM TRÊN MÔI TRƯỜNG PRODUCTION

1. **CẤM** chạy `vercel --prod` hoặc chuyển đổi domain sản xuất khi đang ở giai đoạn Preview.
2. **CẤM** xóa, ghi đè hoặc drop cơ sở dữ liệu SQLite hiện tại (`database/disease_detector.db`).
3. **CẤM** tự ý chuyển đổi hàng loạt tài khoản cũ dựa thuần túy vào email mà không có bước xác thực mật khẩu cũ.
4. **CẤM** đưa khóa `service_role` hoặc `SUPABASE_SECRET_KEY` vào mã frontend hoặc đẩy lên Git.
5. **CẤM** tắt Windows Defender hay tạo thư mục ngoại lệ trên máy tính.

---

## F. TRẠNG THÁI HIỆN TẠI & BƯỚC TIẾP THEO

* **Trạng thái hiện tại:** **`SUPABASE CONFIGURATION REQUIRED`**
* Toàn bộ mã nguồn local đã hoàn tất, đã sẵn sàng để đón nhận thông số Supabase thật.
* Ngay sau khi Người dùng và ChatGPT hoàn tất thiết lập Dashboard và điền 2 thông số `SUPABASE_URL` và `SUPABASE_PUBLISHABLE_KEY` vào `.env`, chúng tôi sẽ lập tức kích hoạt bước **Phase 8: Kiểm thử trình duyệt thực tế & Chuẩn bị Vercel Preview**.

