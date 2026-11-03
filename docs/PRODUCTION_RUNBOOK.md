# GARI AI LAB — SRE PRODUCTION RUNBOOK (docs/PRODUCTION_RUNBOOK.md)

**Phiên bản:** 2.6.0  
**Đối tượng:** Principal Engineer, SRE, DevOps & On-Call Engineers  
**Phạm vi:** Vận hành, Giám sát, Xử lý Sự cố & Phục hồi Thảm họa cho Nền tảng Gari AI Lab

---

## 1. Kiến trúc Hệ thống & Vị trí Lưu trữ Trọng yếu

| Thành phần | Đường dẫn thực tế / Cấu hình | Mục đích & Lưu ý vận hành |
| :--- | :--- | :--- |
| **Cơ sở dữ liệu (SQLite)** | `database/disease_detector.db` | CSDL duy nhất chạy ở chế độ WAL mode (`PRAGMA journal_mode = WAL;`). Đi kèm các file `disease_detector.db-wal` và `disease_detector.db-shm`. |
| **Thư mục Bản sao lưu** | `database/backups/` | Lưu trữ file `.db` sao lưu trực tuyến và file manifest `.json` kiểm tra mã băm SHA256. |
| **Kho ảnh tải lên (Uploads)** | `database/uploads/` | Lưu ảnh người dùng đã đồng ý lưu trữ (`consent_store_image=True`). Cần gắn persistent volume khi deploy container. |
| **Kho Mô hình AI** | `models/` | 44 mô hình thị giác ConvNeXt-Small & ViT cục bộ. Dung lượng ~4 GB. Chỉ đọc (read-only) trong quá trình phục vụ suy luận. |
| **File cấu hình môi trường** | `.env` (tạo từ `.env.example`) | Chứa secrets mã hóa, allowlist CORS, cấu hình cổng và môi trường. |

---

## 2. Quy trình Xử lý Sự cố Thường gặp (Incident Runbooks)

### 2.1. Sự cố 1: Máy chủ từ chối khởi động (Server Fails to Start)
- **Triệu chứng:** Process thoát với exit code 1 ngay sau khi gọi lệnh khởi động.
- **Nguyên nhân phổ biến:**
  1. `APP_ENV=production` nhưng chưa cấu hình `SESSION_SECRET` hoặc `JWT_SECRET`, hoặc vẫn để giá trị placeholder mặc định.
  2. `ALLOWED_ORIGINS` chứa ký tự đại diện `*` trong môi trường production.
  3. Xung đột cổng mạng (cổng 8000 đã bị chiếm dụng bởi tiến trình khác).
- **Quy trình xử lý:**
  1. Kiểm tra log khởi động:
     ```bash
     # Đọc log lỗi khởi động
     tail -n 30 logs/api_server.log
     ```
  2. Nếu có thông báo `CRITICAL SECURITY: ... SESSION_SECRET must be set`:
     - Tạo secret ngẫu nhiên bảo mật 64 hex characters:
       ```bash
       python -c "import secrets; print(secrets.token_hex(32))"
       ```
     - Cập nhật giá trị vào file `.env` cho cả `SESSION_SECRET` và `JWT_SECRET`.
  3. Nếu bị xung đột cổng mạng (Windows PowerShell):
     ```powershell
     Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
     Stop-Process -Id <PID> -Force
     ```

### 2.2. Sự cố 2: Lỗi khóa cơ sở dữ liệu (`sqlite3.OperationalError: database is locked`)
- **Triệu chứng:** Các request ghi chẩn đoán hoặc đăng nhập trả về HTTP 500 kèm lỗi `database is locked`.
- **Nguyên nhân:** Có tiến trình khác đang giữ transaction ghi quá lâu hoặc checkpoint WAL bị nghẽn.
- **Quy trình xử lý:**
  1. Kiểm tra trạng thái toàn vẹn cấu trúc CSDL:
     ```bash
     .venv\Scripts\python.exe -c "import gari_database; print('Integrity:', gari_database.check_database_integrity())"
     ```
  2. Thực hiện ép checkpoint WAL an toàn:
     ```bash
     .venv\Scripts\python.exe -c "import sqlite3; conn=sqlite3.connect('database/disease_detector.db'); conn.execute('PRAGMA wal_checkpoint(TRUNCATE);'); conn.close(); print('WAL Checkpointed')"
     ```
  3. Xác minh `PRAGMA busy_timeout` đã được đặt thành 5000ms trong `gari_database.py`.

### 2.3. Sự cố 3: Lỗi nạp mô hình AI hoặc Tràn bộ nhớ (OOM / Model Load Failure)
- **Triệu chứng:** Endpoint `/predict` hoặc `/api/v1/diagnose` báo lỗi 500 hoặc server bị kill bởi OS.
- **Nguyên nhân:** Bộ nhớ RAM vật lý dưới 2GB hoặc file weights `.safetensors` bị thiếu / hỏng.
- **Quy trình xử lý:**
  1. Kiểm tra sự tồn tại của thư mục mô hình qua endpoint readiness:
     ```bash
     curl -s http://localhost:8000/ready
     ```
  2. Xác minh file mô hình trọng tâm (ví dụ `models/Tomato/model.safetensors`):
     ```powershell
     Test-Path models/Tomato/model.safetensors
     ```
  3. Nếu bộ nhớ thấp, giảm tham số `MAX_CACHED_MODELS=2` trong file `.env` để giải phóng RAM cho các mô hình không dùng thường xuyên.

### 2.4. Sự cố 4: Ổ đĩa gần đầy (Disk Space > 85%)
- **Triệu chứng:** Không thể lưu ảnh upload mới hoặc ghi log audit.
- **Quy trình xử lý:**
  1. Kiểm tra dung lượng thư mục uploads và backups:
     ```powershell
     Get-ChildItem -Recurse database/uploads | Measure-Object -Property Length -Sum
     Get-ChildItem -Recurse database/backups | Measure-Object -Property Length -Sum
     ```
  2. Thực thi dọn dẹp các bản sao lưu cũ vượt quá thời gian lưu trữ (30 ngày / tối đa 14 bản):
     ```bash
     .venv\Scripts\python.exe tools/backup_restore.py retention --max-backups 10 --max-age-days 14
     ```
  3. Rà soát các ca xóa dữ liệu theo yêu cầu người dùng (DSR) để un-link các ảnh đã được đánh dấu xóa.

---

## 3. Quy trình Sao lưu & Phục hồi Thảm họa (Backup & Disaster Recovery)

### 3.1. Tạo bản sao lưu trực tuyến (Online Backup)
> **Lưu ý tối quan trọng:** KHÔNG BAO GIỜ dùng lệnh sao chép file trực tiếp (`cp` hoặc `copy`) trên file SQLite đang chạy vì sẽ gây hỏng trang dữ liệu (corrupted page). Sử dụng công cụ chuẩn:

```bash
# 1. Sao lưu CSDL có gắn nhãn
.venv\Scripts\python.exe tools/backup_restore.py backup --tag scheduled_daily

# 2. Sao lưu CSDL kèm đóng gói thư mục ảnh uploads
.venv\Scripts\python.exe tools/backup_restore.py backup --include-uploads --tag full_archive
```

### 3.2. Kiểm tra tính toàn vẹn của bản sao lưu (Verification)
```bash
.venv\Scripts\python.exe tools/backup_restore.py verify database/backups/<TÊN_FILE_BACKUP>.db
```

### 3.3. Quy trình Khôi phục Thảm họa (Disaster Recovery Restore)
Khi cơ sở dữ liệu hiện tại bị hỏng hoặc cần rollback dữ liệu về mốc thời gian trước:
1. Dừng tiến trình web server đang chạy để ngắt các kết nối ghi mới.
2. Thực thi lệnh khôi phục (công cụ sẽ tự động sao lưu dự phòng CSDL hiện tại trước khi ghi đè):
   ```bash
   .venv\Scripts\python.exe tools/backup_restore.py restore database/backups/<TÊN_FILE_BACKUP>.db
   ```
3. Chạy kiểm tra cấu trúc sau khôi phục:
   ```bash
   .venv\Scripts\python.exe -c "import gari_database; assert gari_database.check_database_integrity(), 'Integrity Error!'"
   ```
4. Khởi động lại máy chủ và kiểm tra endpoint `/ready`.

---

## 4. Danh mục Kiểm tra Giám sát Hằng ngày (Daily SRE Health Check)

- [ ] Liveness probe: `GET /health` trả về HTTP 200 `{"status": "ok"}`.
- [ ] Readiness probe: `GET /ready` trả về HTTP 200 `{"ready": true, "database": "healthy"}`.
- [ ] Kiểm tra dung lượng đĩa: Đảm bảo phân vùng chứa `database/` còn trống tối thiểu 20%.
- [ ] Rà soát log bất thường: Kiểm tra xem có cảnh báo tấn công brute-force hoặc rate limit trên `/api/auth/login`.
- [ ] Kiểm tra backup: Đảm bảo có ít nhất 1 bản sao lưu trong 24 giờ qua với checksum hợp lệ.
