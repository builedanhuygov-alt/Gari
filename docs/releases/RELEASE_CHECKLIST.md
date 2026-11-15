# GARI 3.0 — PRODUCTION RELEASE CHECKLIST

Mọi đợt phát hành lên môi trường Production (`https://gari-team.vercel.app`) bắt buộc phải đáp ứng toàn bộ các tiêu chí dưới đây:

## 1. YÊU CẦU TRƯỚC PHÁT HÀNH (PRE-RELEASE GATE)

- [ ] Toàn bộ mã nguồn trên nhánh `gari-2.0-redesign` đã được kiểm thử và nghiệm thu trên Vercel Preview.
- [ ] Không chứa tệp tin hoặc phụ thuộc PHP ở bất kỳ đâu.
- [ ] Không có migrations mang tính chất phá hủy (destructive drop/truncate) trên Neon PostgreSQL hoặc SQLite.
- [ ] Windows AI Worker daemon đang hoạt động ổn định trên cổng 8000 và kết nối Cloudflare Tunnel thông suốt.
- [ ] Toàn bộ 51 checkpoints mô hình AI trong thư mục `models/` nguyên vẹn.
- [ ] Đã chạy kiểm thử tự động Playwright trên cả Desktop (1366x850) và Mobile (390x844).
- [ ] Có sự phê duyệt chính thức bằng văn bản của người dùng đối với bản phát hành Production.

## 2. QUY TRÌNH THỰC HIỆN TRIỂN KHAI

1. Tạo commit chuẩn mực và đẩy lên nhánh `gari-2.0-redesign`.
2. Kiểm tra log build trên Vercel Dashboard (`bui11 / gari-team`).
3. Chạy smoke test trên Production URL:
   - Thử nghiệm đăng ký/đăng nhập người dùng mới.
   - Thử nghiệm tải ảnh chẩn đoán bệnh lá thật.
   - Kiểm tra hiển thị hạn mức chẩn đoán (Quota 5 lượt/ngày).
   - Kiểm tra chuyển đổi nông trại và xem lịch canh tác theo thời tiết.
4. Ghi nhận thời điểm phát hành và lưu trữ bản ghi kiểm thử.
