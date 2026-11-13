# GARI 2.0 — Cẩm Nang Quản Trị Máy Chủ Host (Host Admin Guide)

Cẩm nang vận hành dành riêng cho Quản trị viên Máy chủ GARI (Host Administrator).

---

## 1. Khởi Tạo Tài Khoản Host Admin Ban Đầu (Bootstrap Procedure)

Để đảm bảo tính toàn vẹn và ngăn chặn nguy cơ leo thang đặc quyền:
- Hệ thống **không có trang đăng ký công khai** cho tài khoản Host.
- Người dùng đầu tiên đăng ký cũng **không được tự động thăng cấp**.
- Quyền Host Admin chỉ được thiết lập thông qua **CLI Bootstrap Tool** trên máy chủ:

### Lệnh chạy CLI Bootstrap:
```powershell
.\.venv\Scripts\python.exe bootstrap_host.py --email admin@gari.vn --name "Quản trị viên Hệ thống"
```
CLI sẽ yêu cầu nhập mật khẩu bảo mật (ẩn ký tự trên màn hình) và yêu cầu xác nhận.
- **Tiêu chuẩn mật khẩu:** Tối thiểu 8 ký tự, có chữ hoa, chữ thường và chữ số.
- Mật khẩu được mã hóa an toàn qua thuật toán Salt + Hash SHA-256 / PBKDF2.
- Thao tác khởi tạo được ghi nhận tự động vào bảng `host_audit_logs`.

---

## 2. Truy Cập Bảng Điều Khiển Host Console

- **Đường dẫn quản trị:** `http://localhost:8000/frontend2/host.html`
- **Màn hình đăng nhập bảo mật:** `http://localhost:8000/frontend2/host-login.html`

Nếu tài khoản người dùng bình thường (không có `is_host_admin = 1`) cố tình truy cập `/frontend2/host.html`, hệ thống sẽ trả về mã lỗi HTTP 403 Forbidden và chuyển hướng người dùng ra màn hình đăng nhập bảo mật.

---

## 3. Các Phân Vùng Chức Năng Trên Host Console

### 3.1. Tổng Quan Máy Chủ (Server Overview)
- Giám sát trạng thái Backend (Uptime, Phiên bản API).
- Thông số phần cứng: Mức sử dụng CPU, RAM, Ổ đĩa lưu trữ.
- Thống kê người dùng đang hoạt động (Active Sessions).
- Lưu lượng yêu cầu (Request Volume) và độ trễ phản hồi trung bình (API Latency).

### 3.2. Quản Trị Người Dùng & Doanh Nghiệp (User & Business Administration)
- Tra cứu tài khoản theo UID, Email hoặc Họ tên.
- Xem loại hình tài khoản (`farmer`, `cooperative`, `expert`, `enterprise`).
- Quản lý trạng thái: Khóa tài khoản tạm thời (`suspend`), Cảnh báo (`warn`), hoặc Chặn vĩnh viễn (`ban`).
- Điều chỉnh hạn ngạch phân loại và cấp quyền thuê bao VIP.

### 3.3. Đối Soát & Phê Duyệt Thanh Toán VietQR (Payment Review Queue)
- Danh sách các đơn hàng chuyển khoản qua MoMo / VietQR đang ở trạng thái `pending_review`.
- Kiểm tra mã giao dịch ngân hàng, đối soát với tài khoản thực tế.
- Bấm **"Xác Nhận Đã Nhận Tiền"** để kích hoạt gói dịch vụ VIP cho người dùng. Thao tác này được lưu vết đầy đủ trong `payment_audit_log`.

### 3.4. Vận Hành Mô Hình Trí Tuệ Nhân Tạo (AI Model Operations)
- Danh mục 51 mô hình AI nhận diện cây trồng và bệnh học thực tế.
- Kiểm tra trạng thái nạp vào bộ nhớ (Loaded / Unloaded).
- Theo dõi thiết bị suy luận (CPU / GPU) và độ trễ suy luận (ms).
- Xem nhật ký lỗi suy luận (Inference Errors) nếu có mẫu ảnh bất thường.

### 3.5. Kiểm Duyệt Vi Phạm Tự Động & Phê Duyệt Thủ Công (Moderation Review)
- Hệ thống tự động quét và gắn cờ các hoạt động bất thường (Spam, Lừa đảo mạo danh, Lạm dụng voucher, Tải lên ảnh độc hại).
- Host Admin xem bằng chứng vi phạm và đưa ra quyết định:
  - **Bỏ qua (Dismiss)**
  - **Cảnh báo (Warn)**
  - **Hạn chế tính năng (Restrict)**
  - **Đình chỉ tạm thời (Suspend)**
  - **Cấm tài khoản (Ban)** kèm lý do cụ thể.
- Hệ thống AI không tự động cấm vĩnh viễn tài khoản; quyền quyết định cuối cùng thuộc về Host Admin.

### 3.6. Quản Lý Voucher Ưu Đãi (Voucher Management)
- Tạo mã voucher mới với hạn mức giảm giá, số lượt kích hoạt và ngày hết hạn.
- Xem lịch sử kích hoạt của người dùng.
- Thu hồi mã voucher khẩn cấp khi phát hiện lạm dụng.

### 3.7. Nhật Ký Kiểm Toán Toàn Diện (Audit Trail)
- Mọi thao tác quản trị trên Host Console (thay đổi trạng thái người dùng, duyệt thanh toán, thu hồi voucher) đều được ghi lại với dấu thời gian, ID người thực hiện và địa chỉ IP.
