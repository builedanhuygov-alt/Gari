# BẢNG KIỂM AN TOÀN VÀ BẢO MẬT MÁY CHỦ ORACLE CLOUD
## GARI AgriTech AI Lab — Oracle Cloud Security & Hardening Checklist

- **Mục tiêu:** Đảm bảo toàn diện an ninh mạng, bảo mật dữ liệu khách hàng, an toàn mô hình AI và tuân thủ các nguyên tắc DevSecOps trong môi trường máy chủ đám mây Oracle Cloud Infrastructure.

---

## 1. BẢNG KIỂM CHI TIẾT (SECURITY AUDIT MATRIX)

| Hạng mục kiểm tra | Tiêu chuẩn kỹ thuật | Trạng thái | Bằng chứng / Cơ chế bảo vệ |
| :--- | :--- | :--- | :--- |
| **1. Mã hóa đường truyền (HTTPS)** | TLS 1.2 & TLS 1.3, Let's Encrypt | **PASSED** | Đã cấu hình ciphers mạnh, tự động chuyển hướng HTTP sang HTTPS trên port 443. |
| **2. Kiểm soát nguồn gốc (CORS)** | Chỉ cho phép frontend production | **PASSED** | FastAPI `CORSMiddleware` cấu hình biến `GARI_ALLOW_ORIGINS=https://gari-team.vercel.app`. Không dùng `*`. |
| **3. Xác thực & Phân quyền (Auth & RBAC)** | JWT Token + Bcrypt (Cost 12) | **PASSED** | `gari_auth.py` xác thực qua Scoped JWT, mật khẩu hash bằng Bcrypt an toàn. |
| **4. Cách ly Container (Non-root)** | UID 1000 `gari` | **PASSED** | `Dockerfile` tạo user `gari` (UID 1000), loại bỏ hoàn toàn đặc quyền root trong container. |
| **5. Bảo vệ Cổng dịch vụ (Port Isolation)** | Port 8000 nội bộ | **PASSED** | `docker-compose.yml` bind port `127.0.0.1:8000:8000`. OCI Security List chỉ mở port 22, 80, 443. |
| **6. Chống từ chối dịch vụ (Rate Limiting)** | Nginx Leaky Bucket | **PASSED** | Giới hạn 15 req/s (burst 30) cho mỗi IP tại Nginx, ngăn chặn brute-force và spam request. |
| **7. Giới hạn dung lượng tải lên (Upload Limit)** | Tối đa 25 MB | **PASSED** | `client_max_body_size 25M` trong Nginx và xác thực kích thước file trong FastAPI. |
| **8. Xác thực tệp tải lên (File Validation)** | MIME & Magic Bytes Validation | **PASSED** | `gari_inference_engine.py` giải mã ảnh bằng `PIL.Image.open()` và bắt lỗi `UnidentifiedImageError`, từ chối file độc hại. |
| **9. Quản trị Bí mật (Secrets Management)** | Environment Variables | **PASSED** | Không commit `.env`, private keys hay mật khẩu vào Git. Sử dụng `.env.example` làm mẫu. |
| **10. Tiêu đề Bảo mật HTTP (Security Headers)** | HSTS, CSP, X-Frame-Options | **PASSED** | Nginx chèn tự động `nosniff`, `SAMEORIGIN`, `1; mode=block`, `strict-origin-when-cross-origin` và `HSTS`. |
| **11. Bảo vệ SSH Máy chủ** | Khóa công khai (Public Key Only) | **PASSED** | Ubuntu trên OCI tắt đăng nhập bằng mật khẩu SSH (`PasswordAuthentication no`), chỉ chấp nhận SSH Key. |
| **12. Chế độ Vận hành (Debug Flag)** | `DEBUG=False` | **PASSED** | Tắt toàn bộ stacktrace lộ thông tin hệ thống khi gặp lỗi nghiệp vụ (`APP_ENV=production`). |
| **13. Toàn vẹn Dữ liệu (Database Persistence)** | SQLite WAL + Hot Backup | **PASSED** | Bật WAL mode, volume mount độc lập, thiết lập cronjob tự động backup vào 02:00 mỗi ngày. |
| **14. Bảo vệ Mô hình AI (Read-Only Mount)** | Volume Read-Only `:ro` | **PASSED** | Thư mục `models/` được mount ở chế độ `:ro` (`./models:/app/models:ro`), ngăn chặn chỉnh sửa hoặc xóa mô hình từ container. |

---

## 2. QUY TRÌNH XÁC MINH AN TOÀN TRƯỚC KHI PUBLIC

1. **Kiểm tra Port Scanning:**
   Từ máy bên ngoài, chạy lệnh quét cổng:
   ```bash
   nmap -p 22,80,443,8000 <PUBLIC_IP_ADDRESS>
   ```
   *Yêu cầu kết quả:*
   - Port 22, 80, 443: **OPEN**
   - Port 8000: **FILTERED** hoặc **CLOSED** (Không được phép mở công khai).

2. **Kiểm tra Header HTTPS:**
   ```bash
   curl -I https://api.yourdomain.com/health
   ```
   *Yêu cầu kết quả:* Có đầy đủ các trường `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Strict-Transport-Security`.

3. **Kiểm tra CORS Header:**
   ```bash
   curl -I -X OPTIONS https://api.yourdomain.com/health \
     -H "Origin: https://malicious-website.com" \
     -H "Access-Control-Request-Method: GET"
   ```
   *Yêu cầu kết quả:* Server từ chối cấp phát `Access-Control-Allow-Origin: https://malicious-website.com`.

