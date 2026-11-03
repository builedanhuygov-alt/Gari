# Gari AI Lab — Trí Tuệ Nông Nghiệp & SaaS Chẩn Đoán Bệnh Cây

> **Brand**: GARI  
> **Application Name**: Gari AI Lab  
> **Subtitle**: Trí tuệ Nông nghiệp Việt Nam  
> **Active Frontend**: `frontend2/` (Linear & Stripe AgriTech Design)  
> **Active Backend**: Python FastAPI (`api_server.py`) với 45 Mô hình ConvNeXt Cục bộ  
> **Active Database**: SQLite Bền vững (`database/disease_detector.db`) với Cơ chế Di chuyển Schemas Tự động  

---

## 1. Khởi Chạy Nhanh (Local Development)

### Yêu cầu môi trường
- Python 3.10+ (Đã cấu hình ảo hóa `.venv`)
- Các thư viện cốt lõi: `fastapi`, `uvicorn`, `torch`, `timm`, `bcrypt`, `pyjwt`, `pillow`, `pydantic`

### Khởi động Máy chủ FastAPI Backend
```bash
# Kích hoạt môi trường và khởi chạy máy chủ
.\.venv\Scripts\python.exe -m uvicorn api_server:app --host 0.0.0.0 --port 8000
```

Truy cập hệ thống tại:
- **Trang chủ / Tổng quan Dashboard**: [http://localhost:8000/frontend2/index.html](http://localhost:8000/frontend2/index.html)
- **Đăng nhập**: [http://localhost:8000/frontend2/login.html](http://localhost:8000/frontend2/login.html)
- **Đăng ký tài khoản**: [http://localhost:8000/frontend2/register.html](http://localhost:8000/frontend2/register.html)
- **Khôi phục mật khẩu**: [http://localhost:8000/frontend2/forgot-password.html](http://localhost:8000/frontend2/forgot-password.html)
- **Nông trại của tôi**: [http://localhost:8000/frontend2/farms.html](http://localhost:8000/frontend2/farms.html)
- **Chẩn đoán AI (Gari Vision)**: [http://localhost:8000/frontend2/predict.html](http://localhost:8000/frontend2/predict.html)
- **Tài liệu API Swagger**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 2. Tài Khoản Kiểm Thử Cục Bộ (Seed Test Accounts)

| Vai trò / Loại tài khoản | Email | Mật khẩu | Dữ liệu khởi tạo |
|---|---|---|---|
| **Kỹ sư Nông học (Chuyên gia)** | `danhuynh@gari.vn` | `Password123!` | 5 Nông trại mẫu, Lô canh tác, Lịch sử chẩn đoán |
| **Nông hộ Trồng trọt** | `nongdan.mau@gari.vn` | `FarmerPassword123!` | Tài khoản nông hộ thực tế |

*Chức năng nạp dữ liệu kiểm thử*:
```bash
.\.venv\Scripts\python.exe database/seed_dev.py
```

---

## 3. Kiến Trúc Xác Thực & Bảo Mật (Authentication Security)

- **Mã hóa Mật khẩu**: Chuẩn công nghiệp Bcrypt (salt rounds: 12) với thuật toán hằng số thời gian chống timing attacks.
- **Quản lý Phiên (Session Management)**: Token ngẫu nhiên bảo mật 256-bit lưu trong bảng `user_sessions`, hỗ trợ Cookie `HttpOnly` (`SameSite=Lax`) và tiêu đề `Authorization: Bearer <token>`.
- **Chống Brute-force (Rate Limiting)**: Khóa tạm thời 5 phút sau 5 lần thử đăng nhập thất bại theo từng IP/Email.
- **Cô Lập Dữ Liệu Tuyệt Đối (Multi-Tenant Isolation)**: Tất cả truy vấn `farms`, `farm_plots`, `diagnoses`, `dashboard/stats` đều được lọc chặt chẽ theo `user_id` của phiên xác thực. Người dùng A không bao giờ có thể xem, chỉnh sửa hay xóa nông trại của Người dùng B.
- **Khôi phục Mật khẩu Cục bộ (Password Recovery)**: Hỗ trợ mã xác thực dùng một lần (15 phút) an toàn trong môi trường local khi chưa cấu hình máy chủ SMTP.

---

## 4. Danh Mục API Backend

### Xác Thực (Authentication)
- `POST /api/auth/register`: Đăng ký tài khoản mới (Họ tên, Email, SĐT, Loại tài khoản, Mật khẩu Bcrypt).
- `POST /api/auth/login`: Xác thực đăng nhập, cấp token & HttpOnly cookie `gari_session`.
- `POST /api/auth/logout`: Hủy phiên đăng nhập trên server và xóa cookie.
- `GET /api/auth/me`: Lấy thông tin tài khoản đang đăng nhập.
- `POST /api/auth/forgot-password`: Khởi tạo mã khôi phục mật khẩu 15 phút.
- `POST /api/auth/reset-password`: Đổi mật khẩu mới bằng mã xác thực hợp lệ.

### Tổng Quan Dashboard (User-Scoped Analytics)
- `GET /api/dashboard/stats`: Thống kê tổng diện tích, số nông trại, lượt chẩn đoán, tỷ lệ khỏe mạnh và phân bố bệnh của người dùng.
- `GET /api/dashboard/activity`: Nhật ký chẩn đoán gần nhất của người dùng.
- `GET /api/dashboard/crop-distribution`: Phân bố các loại cây trồng đang giám sát.
- `GET /api/dashboard/disease-distribution`: Phân bố dịch bệnh thực tế ghi nhận trên các nông trại.

### Quản Lý Nông Trại & Lô Canh Tác (Farms & Plots CRUD)
- `GET /api/farms`: Danh sách nông trại thuộc quyền sở hữu của người dùng.
- `POST /api/farms`: Đăng ký nông trại mới.
- `GET /api/farms/{id}`: Xem chi tiết nông trại, các lô và lịch sử bệnh.
- `PUT /api/farms/{id}`: Cập nhật thông tin nông trại.
- `DELETE /api/farms/{id}`: Xóa nông trại có xác nhận.
- `GET /api/farms/{id}/plots`: Danh sách lô canh tác trong nông trại.
- `POST /api/farms/{id}/plots`: Đăng ký lô canh tác mới.
- `DELETE /api/plots/{plot_id}`: Xóa lô canh tác.

### Chẩn Đoán AI & Lưu Trữ Ảnh Thật (Gari Vision)
- `POST /api/predict`: Tải ảnh lá cây thật (`multipart/form-data`), suy luận cục bộ bằng mạng ConvNeXt, lưu trữ ảnh thực tế tại `database/uploads/`, và lưu bản ghi vào bảng `diagnoses` liên kết với người dùng & nông trại.
- `GET /api/diagnoses`: Danh sách lịch sử chẩn đoán của người dùng.
- `GET /api/diagnoses/{id}`: Chi tiết bản ghi chẩn đoán.

### Thông Báo & Cảnh Báo Dịch Tễ
- `GET /api/notifications`: Danh sách thông báo nông nghiệp của tài khoản.
- `PATCH /api/notifications/{id}/read`: Đánh dấu thông báo đã đọc.
- `GET /api/risk/monitoring`: Trạm quan trắc vi khí hậu & nguy cơ dịch hại khu vực.

---

## 5. Di Chuyển CSDL & Sao Lưu (Migrations & Backup)

Chạy di chuyển schemas (tự động tạo bản sao lưu trước khi thực thi):
```bash
.\.venv\Scripts\python.exe database/migrations_v2.py
```

Bản sao lưu được lưu tự động tại `database/backups/`.

---

## 6. Kiểm Thử Tự Động Toàn Diện (Automated Verification)

Chạy bộ kiểm thử end-to-end 12 hạng mục (Đăng ký, Đăng nhập, Sai mật khẩu, Trùng email, CRUD Nông trại, Phân lô, Cô lập dữ liệu, Suy luận AI với ảnh lá thật, Cập nhật Dashboard, Khôi phục mật khẩu, Đăng xuất):
```bash
.\.venv\Scripts\python.exe scratch/run_full_verification.py
```
