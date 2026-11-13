# GARI 2.0 — Báo Cáo Kiểm Thử Toàn Diện (Comprehensive Test Report)

**Ngày báo cáo:** 03/11/2026  
**Môi trường kiểm thử:** Local Node.js + Python 3.13 + Playwright Chromium  
**Kết quả tổng quan:** **TẤT CẢ CÁC BÀI KIỂM THỬ ĐẠT 100% THÀNH CÔNG (PASSED)**

---

## 1. Kiểm Thử Trình Duyệt Thực Tế End-to-End (Playwright)

File kịch bản: `tests/verify_production_cutover.py`

| Bước | Mô Tả Kịch Bản | Kết Quả | Bằng Chứng (Screenshot) |
|---|---|---|---|
| **1** | Tạo phiên làm việc được chứng thực SHA-256 cho Kỹ sư Đan Huỳnh (User #1) | **PASS** | Token SHA-256 hợp lệ |
| **2** | Kiểm tra Bàn làm việc Desktop (1440x900) & Bộ chọn ngữ cảnh: 0 dữ liệu rác, chỉ có dữ liệu thực | **PASS** | `tests/screenshots/cutover_desktop_workbench.png` |
| **3** | Chạy Pipeline suy luận AI thực tế: Tải ảnh lá cây, kích hoạt suy luận & cổng quang học | **PASS** | `tests/screenshots/cutover_diagnosis_result.png` |
| **4** | Kiểm tra Bảng giá & Modal Chuyển khoản VietQR: Hiển thị đơn chờ đối soát, không có xác nhận ảo | **PASS** | `tests/screenshots/cutover_bank_qr_modal.png` |
| **5** | Kiểm tra Cách ly Host Server Console: Chặn người dùng thường (HTTP 403) và điều hướng về login | **PASS** | `tests/screenshots/cutover_host_security_gate.png` |
| **6** | Trải nghiệm thực địa di động (Mobile Viewport 390x844 iPhone): Bộ chọn ngữ cảnh phản hồi tốt | **PASS** | `tests/screenshots/cutover_mobile_workbench.png` |
| **7** | Kiểm tra toàn vẹn Cơ sở dữ liệu: `PRAGMA foreign_key_check` = 0 lỗi | **PASS** | 0 lỗi ràng buộc khóa ngoại |

---

## 2. Kiểm Thử Đơn Vị & Hồi Quy (Unit & Regression Tests)

Tổng số bài kiểm thử đơn vị: **66 tests**

### 2.1. Phân quyền và Lựa chọn Loại tài khoản (`test_account_type_selection.py`)
- Mỗi tài khoản chỉ có 1 loại hình hoạt động (`farmer`, `cooperative`, `expert`, `enterprise`): **PASS**
- Không thể tự ý thay đổi vai trò trực tiếp từ client: **PASS**
- Quy trình thay đổi vai trò có xác nhận và ghi nhận nhật ký kiểm toán: **PASS**
- Bảo toàn gói VIP khi thay đổi vai trò: **PASS**

### 2.2. Kiểm soát Bảng điều khiển Quản trị Host (`test_host_admin_console.py`)
- Người dùng thường không thể truy cập API Host: **PASS** (HTTP 403)
- Host Admin có thể truy xuất danh sách người dùng, thống kê máy chủ: **PASS**
- Không bao giờ trả về mật khẩu hay secret ra JSON: **PASS**

### 2.3. Hệ thống Kiểm duyệt Tự động (`test_moderation_system.py`)
- Phát hiện từ khóa spam, nội dung quấy rối hoặc lạm dụng API: **PASS**
- Tự động tạo hồ sơ vi phạm (`moderation_cases`): **PASS**
- Host Admin duyệt hành động (dismiss, warn, suspend, ban): **PASS**
- AI không tự động ban vĩnh viễn tài khoản: **PASS**

### 2.4. Phân lập Ngữ cảnh Nông trại & Hợp tác xã (`test_farm_org_selector.py`)
- Chỉ trả về các nông trại và tổ chức mà người dùng được cấp quyền: **PASS**
- Ngăn chặn rò rỉ dữ liệu chéo giữa các nông trại: **PASS**

### 2.5. Thanh toán VietQR & Đối soát (`test_bank_qr_sepay.py`, `test_voucher_api.py`, `test_vouchers.py`)
- Khởi tạo đơn thanh toán VietQR với mã định danh duy nhất: **PASS**
- Trạng thái ban đầu luôn là `pending_review`: **PASS**
- Người dùng bấm thông báo chuyển khoản không tự động kích hoạt VIP: **PASS**
- Quản trị viên duyệt thủ công hoặc webhook hợp lệ mới kích hoạt gói cước: **PASS**
- Tạo mã voucher, áp dụng giảm giá và ghi nhận kiểm toán: **PASS**

---

## 3. Kiểm Thử An Ninh Hệ Thống (Security Assessment)

1. **Kiểm tra Leo thang Đặc quyền (Privilege Escalation):**
   - Đã kiểm tra: Người dùng gửi header giả mạo `X-Gari-Dev-Pro` trong môi trường production bị hệ thống từ chối.
2. **Kiểm tra Rò rỉ Dữ liệu Nhạy cảm (Secret Leakage):**
   - Đã kiểm tra: Toàn bộ API response của Host Admin, User và Billing không chứa chuỗi bí mật, private key hay password hash.
3. **Quy tắc Firestore & Storage Rules:**
   - Đã thiết lập nguyên tắc `Default Deny`. Người dùng chỉ đọc/ghi được tài liệu trong phạm vi UID của mình.
