# GARI AI LAB — CONTROLLED LAUNCH & DEPLOYMENT CHECKLIST (docs/DEPLOYMENT_CHECKLIST.md)

**Phiên bản:** 2.6.0  
**Giai đoạn:** Controlled Pilot & Production Readiness  
**Chính sách an toàn:** Bắt buộc tuân thủ 100% các hạng mục trước khi kích hoạt môi trường Controlled Pilot hoặc Production.

---

## 1. Môi trường & Phân tách Cấu hình (Environment Segregation)

- [ ] **Tách biệt môi trường:** Đã cấu hình biến `APP_ENV=production` hoặc `APP_ENV=staging`. Không bao giờ chạy production với `APP_ENV=development`.
- [ ] **Khóa tuyệt đối Dev Pro Bypass:** Xác nhận `GARI_ALLOW_DEV_PRO=0`. Trong production, hệ thống sẽ tự động khóa mọi nỗ lực bypass qua header `X-Gari-Dev-Pro`.
- [ ] **Bảo vệ Secrets:** `SESSION_SECRET` và `JWT_SECRET` đã được sinh ngẫu nhiên độc lập (tối thiểu 32 ký tự), không dùng lại các giá trị mẫu trong `.env.example`.
- [ ] **Allowlist CORS:** Cấu hình chính xác domain của frontend (ví dụ: `https://gari.vn,https://app.gari.vn`). Tuyệt đối không dùng `*` kèm credentials.
- [ ] **Vô hiệu hóa Debug:** Biến `DEBUG=false` được áp dụng, đảm bảo không có chi tiết lỗi hoặc stack trace bị lộ ra ngoài.

---

## 2. Lưu trữ Bền vững & Quản lý Tài nguyên (Storage & Persistence)

- [ ] **Gắn kết Persistent Volume cho Cơ sở dữ liệu:** Thư mục `database/` phải được mount vào ổ đĩa bền vững (SSD/Block storage), không dùng bộ nhớ tạm (ephemeral container filesystem).
- [ ] **Gắn kết Persistent Volume cho Ảnh người dùng:** Thư mục `database/uploads/` phải được mount vào volume bền vững để đảm bảo ảnh có sự đồng ý (`consent_store_image=True`) không bị mất khi restart container.
- [ ] **Kho Mô hình AI (Model Weights):** Thư mục `models/` (khoảng 4 GB) được đóng gói sẵn hoặc mount read-only. Đảm bảo đầy đủ 44 mô hình cục bộ.
- [ ] **Kiểm tra File .gitignore:** Xác nhận `database/disease_detector.db`, `database/uploads/`, `database/backups/`, `.env` nằm trong danh sách ignore và chưa từng bị commit vào Git.

---

## 3. Quy trình Triển khai Chuẩn (Standard Deployment Workflow)

### Bước 1: Sao lưu trước triển khai (Pre-deployment Backup)
Trước khi cập nhật code hoặc chạy bất kỳ migration nào:
```bash
.venv\Scripts\python.exe tools/backup_restore.py backup --tag pre_deploy_$(Get-Date -Format "yyyyMMdd_HHmm")
```

### Bước 2: Kiểm tra di chuyển CSDL (Database Migration)
Nếu có migration schema mới, chạy trong transaction an toàn:
```bash
.venv\Scripts\python.exe -c "import gari_database; gari_database.init_database(); print('Schema up to date')"
```

### Bước 3: Khởi động dịch vụ trên môi trường Staging
Khởi động backend trên staging port (ví dụ 8080) và xác minh liveness:
```bash
curl -I http://localhost:8080/health
```

### Bước 4: Chạy kiểm thử khói (Smoke Test Suite)
Thực hiện smoke test tự động trên staging:
- [ ] Liveness probe trả về HTTP 200: `GET /health`
- [ ] Readiness probe trả về HTTP 200: `GET /ready`
- [ ] Đăng nhập tài khoản quản trị viên và thành viên thử nghiệm thành công.
- [ ] Chạy 1 ca chẩn đoán mẫu (ví dụ ảnh lá cà chua) và kiểm tra action guidance.
- [ ] Gửi 1 đơn đăng ký pilot mẫu và kiểm tra lead xuất hiện trong dashboard Admin.
- [ ] Tải xuất CSV danh sách lead và kiểm tra không có ký tự formula injection.

### Bước 5: Chuyển đổi lưu lượng (Traffic Cutover)
Chuyển đổi reverse proxy (Nginx / Cloudflare / Load Balancer) sang phiên bản mới sau khi smoke test đạt 100%.

---

## 4. Kế hoạch Hoàn nguyên Khẩn cấp (Rollback Plan)

Nếu phát hiện lỗi nghiêm trọng trong vòng 60 phút sau khi triển khai:
1. **Dừng tiến trình hiện tại:** Hạ container hoặc dừng dịch vụ backend mới.
2. **Khôi phục Cơ sở dữ liệu:**
   ```bash
   .venv\Scripts\python.exe tools/backup_restore.py restore database/backups/<FILE_BACKUP_TRƯỚC_DEPLOY>.db --force
   ```
3. **Rollback Code/Container:** Kích hoạt lại image container hoặc git commit của phiên bản trước đó đã hoạt động ổn định.
4. **Khởi động lại và kiểm tra lại:**
   ```bash
   curl http://localhost:8000/ready
   ```
5. **Ghi nhận Post-Mortem:** Lập báo cáo nguyên nhân sự cố trong vòng 24 giờ.
