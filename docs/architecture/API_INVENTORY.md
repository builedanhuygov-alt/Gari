# GARI 3.0 — API INVENTORY & ROUTING MATRIX

## 1. PHÂN BỐ ROUTING CỦA VERCEL API GATEWAY

Mọi request từ phía Client được Vercel định tuyến dựa trên `vercel.json`:

| Route Pattern | Đích xử lý (Destination) | Mô tả & Trách nhiệm |
|---|---|---|
| `/api/v1/auth/*`, `/api/auth/*` | `api/index.py` | Đăng ký, đăng nhập, phiên session, xác thực |
| `/api/v1/profile/*`, `/api/profile/*` | `api/index.py` | Lấy và cập nhật hồ sơ người dùng |
| `/api/v1/voucher/*`, `/api/voucher/*` | `api/index.py` | Kiểm tra và kích hoạt voucher VIP dùng thử |
| `/api/v1/health`, `/api/health`, `/ready` | `api/index.py` | Healthcheck và trạng thái sẵn sàng của Auth |
| `/api/predict/*`, `/api/diagnose/*` | `api/[...path].js` | Chẩn đoán bệnh lá qua AI Inference Worker |
| `/api/farms/*`, `/api/calendar/*` | `api/[...path].js` | Quản lý nông trại, lịch mùa vụ và vi khí hậu |
| `/api/weather/*` | `api/[...path].js` | Dữ liệu thời tiết Open-Meteo theo tọa độ vườn |
| `/uploads/*` | `api/[...path].js` | Truy cập ảnh thực địa và bản đồ nhiệt Grad-CAM |
| `/frontend2/*`, `/static/frontend2/*` | Static File Server | Tài nguyên HTML, CSS, JS tĩnh |

---

## 2. DANH MỤC API XÁC THỰC (AUTH SERVER — FASTAPI)

- `POST /api/v1/auth/register`: Đăng ký tài khoản mới (hỗ trợ kiểm tra trùng lặp email, hash bcrypt).
- `POST /api/v1/auth/login`: Xác thực thông tin đăng nhập, cấp HttpOnly session cookie `gari_session`.
- `POST /api/v1/auth/logout`: Vô hiệu hóa session trên Neon PostgreSQL và xóa cookie.
- `GET /api/v1/auth/me`: Kiểm tra trạng thái đăng nhập và quyền hạn của session hiện tại.
- `GET /api/v1/profile`: Lấy chi tiết hồ sơ người dùng (họ tên, email, loại tài khoản, VIP status).
- `POST /api/v1/voucher/activate`: Kích hoạt voucher VIP (`Gari-THPTNHD1`) áp dụng thời hạn 7 ngày.
- `GET /api/v1/health`: Kiểm tra kết nối cơ sở dữ liệu Neon.

---

## 3. DANH MỤC API NÔNG NGHIỆP & AI (API SERVER — FASTAPI)

### A. Quản lý Nông trại & Bản đồ số (Farms & GIS)
- `GET /api/farms`: Liệt kê các nông trại của người dùng (hỗ trợ cách ly đa nông hộ).
- `POST /api/farms`: Tạo hồ sơ nông trại mới (tên, tỉnh, tọa độ GPS, độ cao, cây trồng, diện tích).
- `GET /api/farms/{farm_id}`: Xem chi tiết thông số nông trại.
- `PUT /api/farms/{farm_id}`: Cập nhật thông số nông trại.
- `PUT /api/farms/{farm_id}/location`: Cập nhật tọa độ thực địa GPS.

### B. Lịch Canh tác Thông minh & Vi Khí hậu (Calendar & Microclimate)
- `GET /api/calendar/locations/provinces`: Danh mục 63 tỉnh thành Việt Nam với tọa độ trung tâm và phân vùng khí hậu.
- `GET /api/calendar/crops`: Hồ sơ giai đoạn sinh trưởng khoa học của 7 loại cây trồng chủ lực.
- `GET /api/calendar/farms/{farm_id}/schedule`: Lấy lịch mùa vụ cá nhân hóa, vi khí hậu Open-Meteo và cảnh báo thích ứng.
- `POST /api/calendar/farms/{farm_id}/generate-schedule`: Kích hoạt AI tạo mới hoặc tái lập lịch theo giai đoạn cây.
- `GET /api/calendar/tasks`: Lọc công việc theo nông trại, trạng thái, mức độ ưu tiên.
- `POST /api/calendar/tasks`: Tạo công việc canh tác mới gắn với nông trại.
- `POST /api/calendar/tasks/{task_id}/complete`: Đánh dấu hoàn thành công việc và ghi nhật ký thực tế.
- `GET /api/weather/farms/{farm_id}`: Dữ liệu thời tiết tức thời và dự báo 7 ngày theo tọa độ vườn.

### C. Chẩn đoán Bệnh cây AI (AI Inference Pipeline)
- `POST /api/predict`: Nhận diện ảnh lá, kiểm định `is_leaf` gate, dự đoán bệnh, trả về độ tin cậy và Grad-CAM.
- `GET /api/user/quota`: Kiểm tra hạn mức chẩn đoán trong ngày (tối đa 5 lượt/ngày đối với tài khoản cơ bản).
- `GET /api/diagnoses`: Lịch sử các lần chẩn đoán gắn với tài khoản người dùng và nông trại.
