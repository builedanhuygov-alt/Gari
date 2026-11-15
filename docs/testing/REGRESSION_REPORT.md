# GARI 3.0 — REGRESSION TEST REPORT & LOGS

## 1. TỔNG HỢP KIỂM THỬ HỒI QUY (BASELINE REGRESSION STATUS)

- **Thời điểm kiểm định:** 2026-11-16T01:35:00+07:00
- **Môi trường kiểm thử:**
  - Localhost: `http://127.0.0.1:8000` (Windows AI Worker Daemon).
  - Vercel Preview: `https://gari-team-isdytqb2a-bui11.vercel.app`.
  - Database: Neon Serverless PostgreSQL (`sin1`) + SQLite (`database/disease_detector.db`).

---

## 2. KẾT QUẢ CÁC KỊCH BẢN CHÍNH

| Kịch bản kiểm thử | Mô tả kiểm tra | Kết quả | Bằng chứng |
|---|---|---|---|
| **TC-E00-01** | Kiểm tra làm sạch PHP (PHP-free check) | **PASSED** | 0 file PHP trong repo |
| **TC-E00-02** | Kết nối Neon PostgreSQL | **PASSED** | Kết nối thành công, đọc 3 bảng |
| **TC-E00-03** | Khởi động AI Worker & Model Discovery | **PASSED** | Phát hiện 51 mô hình hợp lệ |
| **TC-E01-01** | Đăng nhập session HttpOnly | **PASSED** | Cấp cookie và token thành công |
| **TC-E02-01** | Quản lý Quota 5 lượt chẩn đoán/ngày | **PASSED** | Hiển thị 0/5 lượt, đếm lượt thực |
| **TC-E02-02** | Banner Voucher VIP 7 ngày (`Gari-THPTNHD1`) | **PASSED** | Hiển thị loop banner, modal xác nhận |
| **TC-E03-01** | Suy luận AI thật với ảnh lá cà phê | **PASSED** | Nhận diện Bệnh gỉ sắt 92%, có Grad-CAM |
| **TC-E03-02** | Chặn ảnh không phải lá (`is_leaf` gate) | **PASSED** | Cảnh báo yêu cầu chụp lại ảnh lá |
| **TC-E05-01** | Phân tách dữ liệu đa nông trại | **PASSED** | Vườn Gia Lai vs Vườn Đắk Lắk độc lập |
| **TC-E07-01** | Vi khí hậu Open-Meteo & Lịch thông minh | **PASSED** | Live temp, forecast 7 ngày, cảnh báo ẩm |
| **TC-RESP-01** | Responsive Mobile 390x844 | **PASSED** | Giao diện hiển thị chuẩn không vỡ khung |
