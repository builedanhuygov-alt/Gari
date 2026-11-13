# GARI 2.0 — Báo Cáo Chuyển Đổi Vận Hành Thực Tế (Production Cutover Report)

**Ngày hoàn thành:** 03/11/2026  
**Phiên bản hệ thống:** GARI AgriTech 2.0 Production Release Candidate  
**Chi nhánh / Nhánh Git:** `gari-2.0-redesign`  
**Mục tiêu:** Chuyển đổi toàn diện hệ thống từ chế độ Demo / Thử nghiệm sang chế độ vận hành thực tế (Real Operations), loại bỏ triệt để dữ liệu rác/demo khỏi cơ sở dữ liệu và giao diện, đồng bộ định danh Firebase Auth, áp dụng kiểm định mô hình AI thực tế và quy trình phê duyệt thanh toán minh bạch.

---

## 1. Tóm Tắt Kết Quả Chuyển Đổi (Executive Summary)

1. **Sao lưu an toàn (Verified Backup):**
   - Đã tạo bản sao lưu toàn vẹn trước khi dọn dẹp tại `database/backups/disease_detector_pre_cutover_20261103_132149.db` (2.05 MB).
   - Kiểm tra `PRAGMA quick_check` và `PRAGMA foreign_key_check` đạt **OK** (0 lỗi ràng buộc khóa ngoại).
2. **Dọn dẹp dữ liệu thử nghiệm (Data Cleanup Manifest):**
   - Đã xuất bản kê chi tiết tại `docs/CLEANUP_MANIFEST.json`.
   - **Đã xóa an toàn:** 28 tổ chức thử nghiệm (`is_test = 1`), 11 trang trại thử nghiệm (`is_test = 1`), 118 tài khoản người dùng test/seeded, 10 lượt chẩn đoán giả lập, cùng các liên kết rác liên quan trong bảng nhật ký và quota.
   - **Bảo toàn 100% dữ liệu thực:**
     - Người dùng thực: Kỹ sư Đan Huỳnh (`danhuynh@gari.vn`, ID: 1), Bùi Lê Đan Huy (`huy175209@gmail.com`, ID: 175).
     - Hợp tác xã / Tổ chức thực: HTX Nông Nghiệp Ba Vì (ID: 1), Trang Trại Sinh Thái 7 (ID: 2).
     - Trang trại thực: 7 trang trại đang canh tác (Trang trại Ba Vì Organic, Trang trại Cà phê Cư M'gar, Vườn Hồ tiêu Gia Lai, v.v.).
     - Lịch sử chẩn đoán thực & đơn hàng thực.
   - **Tài khoản diện nghi vấn (Uncertain):** Đã tạm giữ an toàn các tài khoản ID 2 (`farmer@gari.vn`), ID 3 (`expert@gari.vn`), ID 7 (`coop@gari.vn`) chờ quyết định chính thức từ chủ sở hữu.
3. **Định danh & Phân quyền chuẩn Firebase (Production Auth):**
   - Tạo migration `database/migrations_firebase.py` bổ sung cột `firebase_uid TEXT` và chỉ mục duy nhất `idx_users_firebase_uid`.
   - Xây dựng module `gari_firebase.py` xác thực Firebase ID Token với Firebase Admin SDK, hỗ trợ đồng bộ hồ sơ và phân quyền tùy biến (`custom_claims`).
   - Cập nhật cơ chế xác thực kép (Dual-Auth) trong `gari_auth.py`: ưu tiên kiểm tra Firebase Bearer Token, sau đó đối soát phiên nội bộ có chữ ký SHA-256 bảo mật.
   - Ép buộc nguyên tắc: **Mỗi tài khoản chỉ sở hữu duy nhất 1 vai trò hoạt động** (`farmer`, `cooperative`, `expert`, `enterprise`).
4. **Hạ tầng AI & Kiểm định lá quang học thực (Real AI Diagnostics):**
   - Quét và phát hiện 51 mô hình PyTorch & ViT thực tế sẵn sàng trong thư mục `models/`.
   - Khóa chặt tham số `dev_pro` bypass trong môi trường production (`ALLOW_DEV_PRO_BYPASS = False`). Mọi yêu cầu chẩn đoán đều được định tuyến qua pipeline thực của `gari_inference_engine.py`.
   - Cổng kiểm định quang học (Optical Leaf Validation Gate) ngăn chặn ảnh chụp không phải lá cây hoặc chất lượng kém và không trừ quota người dùng khi ảnh vi phạm.
   - Xử lý lỗi chuẩn HTTP 503 Service Unavailable khi mô hình chưa tải hoặc lỗi phần cứng, không bao giờ trả kết quả giả định.
5. **Hạn ngạch & Thuê bao thực tế (Real Quotas & Atomic Metering):**
   - Loại bỏ hoàn toàn các API cho phép client tự cập nhật hoặc gian lận quota.
   - Áp dụng cơ chế khóa phân đoạn `_QUOTA_LOCK` đảm bảo trừ hạn ngạch nguyên tử (Atomic Quota Deduction), chống race-condition khi gọi đồng thời.
6. **Thanh toán VietQR minh bạch (Bank QR Review Flow):**
   - Chế độ thanh toán quét mã QR qua MoMo / VietQR NAPAS 24/7 ghi nhận trạng thái `pending_review`.
   - Không tự động kích hoạt VIP ngay lập tức mà yêu cầu Webhook từ đối tác thanh toán có chữ ký số hoặc hành động phê duyệt thủ công của Host Admin trong trang quản trị.
7. **Phân tách hoàn toàn Bảng điều khiển Quản trị Host (Host Console):**
   - Tách biệt `/frontend2/host.html` khỏi bảng điều khiển người dùng thông thường (`/frontend2/predict.html`).
   - Yêu cầu xác thực tài khoản Host Admin (`is_host_admin = 1`). Người dùng thông thường cố tình truy cập sẽ nhận mã lỗi 403 Forbidden và bị chuyển hướng về màn hình bảo vệ `host-login.html`.
8. **Kiểm thử trình duyệt thực tế Playwright (End-to-End Verification):**
   - Kịch bản `tests/verify_production_cutover.py` vượt qua toàn bộ 7/7 bước kiểm thử trình duyệt thực tế trên cả giao diện Desktop (1440x900) và Mobile (390x844).

---

## 2. Bảng Thống Kê Dữ Liệu Trước và Sau Cutover

| Thực thể (Table) | Tổng trước Cutover | Bản ghi Demo đã xóa | Bản ghi thực tế bảo toàn | Trạng thái toàn vẹn |
|---|---|---|---|---|
| **Users** | 151 | 118 | 33 (Bao gồm User 1, 175 và 3 tài khoản nghi vấn) | 0 orphan foreign keys |
| **Organizations** | 30 | 28 | 2 (HTX Ba Vì, Trang Trại 7) | `is_test = 0` |
| **Farms** | 18 | 11 | 7 (Ba Vì, Cư M'gar, Gia Lai, v.v.) | `is_test = 0` |
| **Diagnoses** | 104 | 10 | 94 | Dữ liệu kiểm định thực |
| **Payment Orders** | 264 | 4 | 260 | Không có đơn giả lập |
| **Vouchers** | 199 | 12 | 187 | Bản ghi kiểm toán đầy đủ |
| **Foreign Key Errors** | 0 | - | **0** | Đạt chuẩn toàn vẹn SQLite |

---

## 3. Danh Sách Bản Ghi Đang Tạm Giữ Nghi Vấn (Cần Chủ Sở Hữu Xác Nhận)

Các tài khoản sau có dấu hiệu được tạo trong quá trình kiểm thử nhưng có hồ sơ tương tự người dùng thực. Hệ thống đã **giữ nguyên không xóa** để đảm bảo an toàn tuyệt đối:

| User ID | Email | Họ và tên | Vai trò hiện tại | Ghi chú / Khuyến nghị |
|---|---|---|---|---|
| **2** | `farmer@gari.vn` | Nông dân Mẫu | `farmer` | Khuyến nghị: Chuyển đổi thành tài khoản demo mẫu hoặc xóa nếu không sử dụng thực tế. |
| **3** | `expert@gari.vn` | Chuyên gia BVTV Mẫu | `expert` | Khuyến nghị: Giữ lại làm tài khoản chuyên gia kiểm định hoặc bàn giao cho kỹ sư thực tế. |
| **7** | `coop@gari.vn` | Ban Quản Trị HTX | `cooperative` | Khuyến nghị: Gán quyền cho quản lý HTX Ba Vì hoặc xóa bỏ nếu không còn sử dụng. |

---

## 4. Bằng Chứng Kiểm Thử Trình Duyệt Thực Tế (Screenshots)

Tất cả ảnh chụp màn hình được sinh tự động từ Playwright tại `tests/screenshots/`:

1. **cutover_desktop_workbench.png**:
   - Giao diện làm việc Desktop chẩn đoán lá cây chuẩn hóa (1440x900).
   - Bộ chọn ngữ cảnh tổ chức / nông trại hiển thị 100% bản ghi thực (HTX Nông Nghiệp Ba Vì, Trang trại Ba Vì Organic), sạch hoàn toàn các dữ liệu rác như "Test Concurrent HTX" hay "Hợp Tác Xã Cô Đơn".
2. **cutover_diagnosis_result.png**:
   - Kết quả kiểm định AI thực tế. Cổng kiểm định lá quang học phản hồi chính xác và hướng dẫn người dùng chụp lại ảnh chiếc lá chuẩn nông học.
3. **cutover_bank_qr_modal.png**:
   - Khung giao dịch Chuyển khoản VietQR hiển thị đầy đủ thông tin MoMo / NAPAS 24/7, mã đơn hàng định danh duy nhất, và trạng thái đang chờ đối soát với nút báo *"✓ Tôi Đã Chuyển Khoản"*. Không có tình trạng tự động kích hoạt ảo.
4. **cutover_host_security_gate.png**:
   - Cổng kiểm soát an ninh của Host Admin Console từ chối người dùng thường và điều hướng an toàn về `host-login.html`.
5. **cutover_mobile_workbench.png**:
   - Trải nghiệm thực địa trên thiết bị di động (iPhone Viewport 390x844) mượt mà, bộ chọn ngữ cảnh co giãn phản hồi tốt.

---

## 5. Kết Quả Kiểm Thử Đơn Vị (Regression Test Suites)

Hệ thống đã chạy hồi quy toàn diện các bộ kiểm thử backend:
- `tests.test_account_type_selection`: 14 tests — **OK**
- `tests.test_host_admin_console`: 10 tests — **OK**
- `tests.test_moderation_system`: 8 tests — **OK**
- `tests.test_farm_org_selector`: 5 tests — **OK**
- `tests.test_bank_qr_sepay`: 9 tests — **OK**
- `tests.test_voucher_api`: 11 tests — **OK**
- `tests.test_vouchers`: 9 tests — **OK**

**Tổng kết:** 66/66 unit & integration tests đạt trạng thái **PASSED (100% OK)**.

---

## 6. Hướng Dẫn Vận Hành Môi Trường Thực Tế

### Lệnh khởi động Backend:
```powershell
$env:APP_ENV="production"
$env:PORT="8000"
$env:PAYMENT_PUBLIC_CHECKOUT_ENABLED="1"
$env:FIREBASE_CREDENTIALS_PATH="config/firebase-service-account.json"
.\.venv\Scripts\python.exe -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 4
```

### Lệnh khởi động Frontend:
```powershell
npm --prefix frontend run build
npm --prefix frontend run preview -- --host 0.0.0.0 --port 5173
```

### Các đường dẫn cổng dịch vụ:
- **Cổng chẩn đoán nông hộ & kỹ sư:** `http://localhost:8000/frontend2/predict.html`
- **Cổng bảng giá & đăng ký gói cước:** `http://localhost:8000/frontend2/pricing.html`
- **Cổng điều hành Host Admin Server:** `http://localhost:8000/frontend2/host.html`
- **Kiểm tra trạng thái hệ thống (Health Check):** `http://localhost:8000/api/health`
