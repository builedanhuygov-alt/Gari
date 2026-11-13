# GARI 2.0 — Kiến Trúc Hệ Thống Tổng Thể (System Architecture)

## 1. Giới Thiệu & Triết Lý Thiết Kế
**GARI AgriTech 2.0** là nền tảng ứng dụng trí tuệ nhân tạo (Agricultural AI Platform) phục vụ toàn diện các phân khúc nông nghiệp tại Việt Nam: Nông hộ cá thể (`farmer`), Hợp tác xã (`cooperative`), Chuyên gia bảo vệ thực vật (`expert`) và Doanh nghiệp chế biến/chuỗi cung ứng (`enterprise`).

### Nguyên Tắc Cốt Lõi:
1. **Phân quyền độc lập (Single Active Account Type):** Mỗi người dùng được xác thực sở hữu chính xác một vai trò hoạt động chủ đạo, không ghép chồng quyền.
2. **Tách biệt hạ tầng Máy chủ Host (Host Server Isolation):** Bộ máy quản trị máy chủ, quản lý mô hình AI, đối soát thanh toán và kiểm duyệt nội dung chạy trên vùng quản trị chuyên biệt (`/frontend2/host.html`), tách rời hoàn toàn khỏi không gian làm việc của nông dân.
3. **Định danh kép tin cậy (Dual-Auth Architecture):** Kết hợp định danh toàn cầu qua Firebase Authentication (ID Token Bearer) và cơ chế phiên mã hóa SHA-256 an toàn trên máy chủ Host.
4. **Trung thực về dữ liệu & AI (No Fake Inference / No Fake Payments):**
   - 100% chẩn đoán chạy qua mô hình thực tế kết hợp cổng kiểm định lá quang học (Optical Leaf Validation Gate).
   - Thanh toán quét mã QR NAPAS 24/7 ghi nhận trạng thái chờ đối soát (`pending_review`), chỉ kích hoạt khi có chứng từ giao dịch được quản trị viên duyệt.

---

## 2. Mô Hình Phân Tầng Kiến Trúc

```
+-----------------------------------------------------------------------------------+
|                            CLIENT TIER (GARI 2.0)                                 |
|  [Desktop 1440px / Mobile 390px]                                                  |
|  - Farmer / Expert Workbench (/frontend2/predict.html)                            |
|  - Pricing & VietQR Modal (/frontend2/pricing.html)                               |
|  - Dedicated Host Console (/frontend2/host.html, host-login.html)                 |
+-----------------------------------------+-----------------------------------------+
                                          |
                      +-------------------+-------------------+
                      | Bearer Token (Firebase / SHA-256)     |
                      v                                       v
+------------------------------------+   +------------------------------------------+
|      FIREBASE IDENTITY CLOUD       |   |       GARI INDEPENDENT HOST SERVER       |
|  - Firebase Authentication         |   |  - FastAPI / Uvicorn Server (Port 8000)  |
|  - Firestore Profiles & Orgs       |   |  - Dual-Auth Guard (gari_auth.py)        |
|  - Firebase Storage (Media/Avatar) |   |  - Atomic Quota Engine (_QUOTA_LOCK)     |
|  - Security Rules (Default Deny)   |   |  - Moderation System (Automated Scan)    |
|                                    |   |  - Payment Gateway & Order Ledger        |
+------------------------------------+   +--------------------+---------------------+
                                                              |
                                                              v
                                         +------------------------------------------+
                                         |      INFERENCE & DATABASE SUBSYSTEM      |
                                         |  - 51 Valid PyTorch / ViT Models (CPU)   |
                                         |  - Optical Leaf Validation Gate          |
                                         |  - SQLite (WAL Mode, Foreign Keys ON)    |
                                         |  - Host Audit Logs & Metric Counters     |
                                         +------------------------------------------+
```

---

## 3. Các Phân Hệ Thành Phần

### 3.1. Phân Hệ Xác Thực & Quản Lý Hồ Sơ
- **Firebase Auth Bridge (`gari_firebase.py`):** Tiếp nhận Firebase ID Token gửi từ frontend, kiểm tra tính hợp lệ qua Firebase Admin SDK, ánh xạ với `firebase_uid` trong cơ sở dữ liệu nội bộ.
- **Account Type Enforcement (`gari_auth.py`):** Ngăn chặn việc gửi UID giả lập từ client. Tất cả UID được trích xuất từ token đã ký. Khi tài khoản đã chọn loại hình (`farmer`, `cooperative`, `expert`, `enterprise`), loại hình này được khóa an toàn và chỉ có thể chuyển đổi qua quy trình có kiểm toán (`/api/user/account-type/change`).

### 3.2. Phân Hệ Chẩn Đoán Cây Trồng & Kiểm Định Lá
- **Cổng kiểm định lá quang học (Optical Leaf Gate):** Trước khi gọi mô hình phân loại bệnh, ảnh tải lên được kiểm tra hình thái sinh học (độ phủ màu diệp lục, tỷ lệ khung hình, độ sắc nét).
- Nếu ảnh không phải lá cây hoặc chất lượng kém: Hệ thống ngắt sớm, không trừ quota của người dùng và trả về hướng dẫn chụp lại.
- **51 Mô hình AI Đa cây trồng:** Nhận diện các loại cây trồng chủ lực (Cà phê, Hồ tiêu, Lúa, Sầu riêng, Cà chua, Ớt, Ngô) và các loại bệnh lý tương ứng.

### 3.3. Phân Hệ Hạn Ngạch & Thuê Bao
- **Atomic Metering:** Sử dụng `asyncio.Lock` nội bộ (`_QUOTA_LOCK`) đảm bảo mọi giao dịch trừ lượt phân loại diễn ra tuần tự, loại bỏ hoàn toàn lỗ hổng race-condition.
- Tách biệt hoàn toàn giữa vai trò tài khoản (`account_type`) và gói cước thuê bao (`is_vip`, `subscription_tier`).

### 3.4. Phân Hệ Thanh Toán VietQR Minh Bạch
- Tạo mã thanh toán chuẩn NAPAS 24/7 (VietQR / MoMo) với cú pháp nội dung chuyển khoản định danh duy nhất (VD: `GARI-U1-16751218`).
- Quy trình đối soát thủ công có nhật ký kiểm toán: Host Admin kiểm tra tài khoản ngân hàng thực tế rồi mới bấm phê duyệt trên Host Console.

### 3.5. Bảng Điều Khiển Host Admin Tách Biệt
- Giao diện độc lập: `/frontend2/host.html`.
- Xác thực riêng biệt qua mật khẩu mạnh đã băm và cờ `is_host_admin = 1`.
- Quản lý toàn diện: Người dùng, Tổ chức, Mô hình AI, Cấu hình API, Kiểm duyệt vi phạm và Báo cáo kiểm toán.
