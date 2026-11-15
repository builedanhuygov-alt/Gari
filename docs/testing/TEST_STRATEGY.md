# GARI 3.0 — TESTING STRATEGY & QUALITY GATES

## 1. NGUYÊN TẮC KIỂM THỬ ĐA TẦNG

Mọi chức năng trong GARI 3.0 trước khi nghiệm thu phải vượt qua 3 tầng kiểm thử:

1. **Unit & Integrity Tests (Mức Đơn vị & CSDL):**
   - Kiểm tra cú pháp, biên dịch Python (`py_compile`), kiểm tra schema CSDL và các hàm xử lý logic nội bộ.
2. **Integration Tests (Mức Tích hợp Dịch vụ):**
   - Kiểm tra gọi chéo API giữa Vercel Edge Gateway, Auth Server và AI Worker.
   - Kiểm tra tính toàn vẹn của kết nối Neon PostgreSQL và SQLite.
3. **End-to-End Browser Automation Tests (Playwright):**
   - Tự động hóa trải nghiệm thực tế của người dùng trên trình duyệt (Desktop 1366x850 và Mobile 390x844).
   - Kiểm tra console errors, network requests, render layout, tương tác modal và chụp ảnh bằng chứng lưu vào artifact.

---

## 2. TIÊU CHÍ NGHIỆM THU TỪNG CỔNG (QUALITY GATES)

- **Gate E00:** Báo cáo Baseline Audit đầy đủ, không có mã PHP, không có lỗi phá hủy dữ liệu.
- **Gate E01:** Đăng ký và đăng nhập thành công với dữ liệu thực tế, session HttpOnly an toàn, đồng bộ trạng thái tài khoản trên toàn trang.
- **Gate E02:** Hạn mức 5 lượt/ngày chính xác, không trừ trùng lặp, voucher VIP 7 ngày kích hoạt đúng hạn.
- **Gate E03:** Chẩn đoán ảnh thực tế bằng model thật, kiểm định `is_leaf` hoạt động, trả về Grad-CAM chính xác.
- **Gate E05 & E07:** Hai khu vườn độc lập có lịch canh tác và thời tiết Open-Meteo riêng biệt, không rò rỉ dữ liệu.
