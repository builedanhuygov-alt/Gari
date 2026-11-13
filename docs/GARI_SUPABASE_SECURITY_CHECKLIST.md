# GARI AgriTech AI Lab — Supabase Security Checklist & Test Results

**Document ID:** GARI-CHK-SUPABASE-SECURITY-2026-02  
**Project:** GARI AgriTech AI Lab  
**Scope:** Security Assurance, JWT Integrity, RLS Enforcement, Threat Model  
**Date:** 2026-11-11  
**Status:** **LOCAL IMPLEMENTATION VERIFIED (27/27 TESTS PASSED)**  

---

## 1. Security Architecture Verification Checklist

| Security Requirement | Verification Criterion | Enforcement Mechanism | Status |
|---|---|---|:---:|
| **Zero PHP Invariant** | Không có bất kỳ file `.php` nào, không có payload, test script hoặc chuỗi mô phỏng PHP. | Windows Defender real-time scanning, static filesystem scans. | **VERIFIED** |
| **Bảo vệ Secret Keys** | Trình duyệt chỉ nhận `SUPABASE_PUBLISHABLE_KEY` (hoặc anon key). Không bao giờ gửi `service_role` về client. | Kiểm toán mã nguồn `frontend2/` và API response. | **VERIFIED** |
| **Xác minh JWT Bất đối xứng** | FastAPI kiểm tra chữ ký số qua JWKS public keys (`RS256`, `ES256`). Từ chối thuật toán `none`. | Tích hợp `PyJWKClient` và `PyJWT` trong `gari_auth.py`. | **VERIFIED** |
| **Kiểm tra Issuer & Audience** | Từ chối token có `iss` sai hoặc `aud != 'authenticated'`. | Kiểm tra bắt buộc trong hàm `verify_supabase_jwt()`. | **VERIFIED** |
| **Ràng buộc Subject (sub)** | Từ chối token không có `sub` (UUID). Không tin cậy user ID do client gửi lên. | Định danh được phân giải nghiêm ngặt từ `sub`. | **VERIFIED** |
| **Row-Level Security (RLS)** | Tất cả 4 bảng công khai đều bật RLS với chính sách sở hữu `auth.uid() = id`. | Script DDL trong `docs/GARI_SUPABASE_HYBRID_SCHEMA.sql`. | **SPECIFIED** |
| **Bảo toàn Cầu nối Định danh** | Người dùng không thể tự gắn SQLite ID của người khác vào tài khoản của mình. | `gari_identity_links` chỉ cấp quyền ghi cho `service_role`. | **VERIFIED** |
| **Nguyên tắc Fail-Closed** | Khi Supabase Auth offline hoặc JWKS không thể kết nối, backend trả HTTP 503. | Xử lý ngoại lệ trong `gari_auth.py` và `api/[...path].js`. | **VERIFIED** |
| **Chống Treo Nút Đăng ký** | Nút bấm luôn được mở khóa trong khối `finally` bất kể lỗi mạng hoặc timeout. | Bọc `withTimeout()` và cờ `isSubmitting` phòng thủ. | **VERIFIED** |
| **Bảo toàn Dữ liệu Nghiệp vụ** | 59 bảng nghiệp vụ trong SQLite (`database/disease_detector.db`) nguyên vẹn 100%. | Không xóa hay sửa đổi cấu trúc bảng nghiệp vụ hiện có. | **VERIFIED** |

---

## 2. Kết quả Kiểm thử Thực tế 20 Kịch bản (Phase 6)

### A. Python Backend Security Suite (`tests/test_supabase_auth_suite.py`)
Toàn bộ **20/20 kịch bản** đã chạy thành công trong `0.450s`:

| STT | Kịch bản kiểm thử | Phân loại | Kết quả thực tế |
|:---:|---|---|:---:|
| 1 | **Valid registration / token verification** | Cryptographic | **PASS** |
| 2 | **Duplicate email provisioning idempotency** | State Machine | **PASS** |
| 3 | **Invalid password validation** | Input Validation | **PASS** |
| 4 | **Email verification payload handling** | Auth State | **PASS** |
| 5 | **Valid login session restoration** | Session Management | **PASS** |
| 6 | **Invalid login rejection (malformed token)** | Error Handling | **PASS** |
| 7 | **Refresh session & expiration check** | Session Expiry | **PASS** |
| 8 | **Logout & session token invalidation** | Revocation | **PASS** |
| 9 | **Expired JWT rejection** | Cryptographic | **PASS** |
| 10 | **Invalid signature rejection** | Cryptographic | **PASS** |
| 11 | **Wrong issuer rejection** | Cryptographic | **PASS** |
| 12 | **Wrong audience rejection (`aud != 'authenticated'`)** | Cryptographic | **PASS** |
| 13 | **Missing subject claim rejection** | Cryptographic | **PASS** |
| 14 | **Cross-user isolation (User A vs User B)** | Tenant Isolation | **PASS** |
| 15 | **Cross-tenant role separation** | RBAC | **PASS** |
| 16 | **Duplicate provisioning concurrency (5 threads)** | Idempotency | **PASS** |
| 17 | **SQLite identity bridge persistence** | Database Integrity | **PASS** |
| 18 | **Supabase unavailable fail-closed handling** | Resilience | **PASS** |
| 19 | **Identity bridge status check (Suspended link blocked)** | Access Control | **PASS** |
| 20 | **Session cookie & Header token extraction** | Transport | **PASS** |

### B. JavaScript Client Suite (`tests/test_supabase_client_unit.js`)
Toàn bộ **7/7 bài test** đơn vị client đã chạy thành công:

1. Map lỗi *"User already registered"* sang thông báo tiếng Việt rõ ràng: **PASS**
2. Map lỗi *"Invalid login credentials"* sang thông báo tiếng Việt: **PASS**
3. Map lỗi *"Email not confirmed"* sang thông báo tiếng Việt: **PASS**
4. Map lỗi *"Rate limit"* sang thông báo chờ đợi: **PASS**
5. `withTimeout` giải quyết Promise hoàn thành trước hạn: **PASS**
6. `withTimeout` từ chối an toàn khi mạng bị treo vô hạn: **PASS**
7. Đảm bảo nút đăng ký luôn mở khóa trong khối `finally`: **PASS**

**Tổng số bài test xác minh thành công:** **27 / 27 PASS (100%)**

