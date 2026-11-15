# GARI 3.0 — SECURITY BASELINE & POLICY

## 1. NGUYÊN TẮC BẢO MẬT BẮT BUỘC (MANDATORY SECURITY POLICIES)

1. **Tuân thủ Tuyệt đối Không sử dụng PHP (Zero PHP Policy):**
   - Không chứa bất kỳ tệp tin hoặc mã nguồn `.php` nào trong toàn bộ dự án.
   - Toàn bộ backend sử dụng Python (FastAPI) và Node.js Edge Proxy.
2. **Bảo vệ Cookie & Phiên Session:**
   - Phiên đăng nhập được quản lý bằng HttpOnly Cookie `gari_session` với các cờ `SameSite=Lax` và `Secure` trên môi trường Production.
   - Ngăn chặn triệt để tấn công XSS đánh cắp session.
3. **Phòng chống Tấn công CSRF:**
   - Mọi phương thức thay đổi trạng thái (`POST`, `PUT`, `DELETE`, `PATCH`) trong Auth Server đều yêu cầu token `X-CSRF-Token` hợp lệ được sinh ngẫu nhiên theo phiên.
4. **Bảo mật Đăng ký & Hash Mật khẩu:**
   - Mật khẩu người dùng được băm bằng thuật toán Bcrypt / Argon2id với độ phức tạp cao, không bao giờ lưu trữ plain text.
5. **Cách ly Dữ liệu & Chống IDOR (Insecure Direct Object References):**
   - Mọi API truy cập nông trại (`/api/farms/{id}`), công việc (`/api/calendar/tasks/{id}`) hay lịch sử chẩn đoán đều bắt buộc kiểm tra quyền sở hữu (`user_id == current_user.id`).
6. **Bảo vệ Bí mật (Secrets Management):**
   - Mọi biến môi trường nhạy cảm (`DATABASE_URL`, `JWT_SECRET`, `SESSION_SECRET`, `VERCEL_OIDC_TOKEN`) được quản lý qua Vercel Environment Variables, tuyệt đối không hardcode trong mã nguồn hoặc đưa vào frontend.
