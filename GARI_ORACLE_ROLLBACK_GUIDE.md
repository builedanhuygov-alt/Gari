# QUY TRÌNH HOÀN NGUYÊN KHẨN CẤP MÁY CHỦ ORACLE CLOUD
## GARI AgriTech AI Lab — Oracle Cloud Disaster Recovery & Rollback Playbook

> **Mục tiêu:** Cung cấp hướng dẫn từng bước chi tiết để khôi phục hệ thống về trạng thái ổn định ngay lập tức khi phát sinh sự cố tại máy chủ Oracle Cloud VM hoặc trong quá trình triển khai phiên bản mới, **đảm bảo 100% không mất dữ liệu và RTO < 3 phút**.

---

## 1. MA TRẬN ỨNG PHÓ SỰ CỐ & THỜI GIAN KHÔI PHỤC

| Kịch bản sự cố | Hành động xử lý | RTO (Thời gian khôi phục) | RPO (Mức độ mất dữ liệu) |
| :--- | :--- | :--- | :--- |
| **Bản cập nhật Docker bị lỗi/crash** | Chạy `rollback.sh` khôi phục container và database | **< 1 phút** | **0 giây** |
| **Cơ sở dữ liệu SQLite bị lỗi logic** | Khôi phục từ bản sao lưu nóng gần nhất trong `database/backups/` | **< 2 phút** | **Tối đa đến lần backup gần nhất** |
| **Máy chủ Oracle VM mất kết nối/sập nguồn** | Chuyển Vercel Proxy về Local Cloudflare Tunnel | **< 2 phút** | **0 giây** |
| **Chứng chỉ SSL hết hạn/lỗi Nginx** | Kích hoạt chứng chỉ fallback hoặc gia hạn khẩn cấp Certbot | **< 3 phút** | **0 giây** |

---

## 2. KỊCH BẢN 1: HOÀN NGUYÊN CONTAINER VÀ PHIÊN BẢN MÃ NGUỒN

Nếu bạn vừa deploy bản cập nhật mới trên Oracle Cloud VM bằng `deploy.sh` nhưng container bị lỗi khởi động hoặc trả về lỗi 500:

### Bước 1.1: Thực thi script hoàn nguyên tự động
Trên terminal SSH của máy chủ VM:
```bash
cd ~/gari
bash deploy/oracle/rollback.sh
```
Script sẽ tự động:
1. Tạm dừng các container bị lỗi (`docker compose down`).
2. Nhắc bạn chọn khôi phục cơ sở dữ liệu nếu có bản sao lưu trước khi cập nhật.
3. Khởi động lại các container ở trạng thái ổn định.
4. Chạy bộ kiểm tra sức khỏe tự động `healthcheck.sh`.

### Bước 1.2: Revert mã nguồn Git về commit ổn định (nếu cần)
```bash
git log --oneline -n 5
git reset --hard <COMMIT_HASH_ỔN_ĐỊNH>
docker compose build gari-backend
docker compose up -d
```

---

## 3. KỊCH BẢN 2: KHÔI PHỤC CƠ SỞ DỮ LIỆU SQLITE TỪ BẢN SAO LƯU

Nếu dữ liệu bị xóa nhầm hoặc file SQLite bị lỗi cấu trúc:

### Bước 2.1: Liệt kê các bản sao lưu khả dụng
```bash
ls -lh database/backups/
```
Ví dụ hiển thị:
```text
backup_20261110_020000.db (9.2 MB)
backup_20261109_020000.db (9.1 MB)
```

### Bước 2.2: Thực hiện khôi phục an toàn
```bash
# 1. Dừng backend để tránh ghi đè đồng thời
docker compose stop gari-backend

# 2. Tạo bản lưu tệp lỗi để đối chiếu sau này
cp database/disease_detector.db database/disease_detector.db.corrupted_$(date +%s)

# 3. Sao chép tệp backup đè vào tệp chính
cp database/backups/backup_20261110_020000.db database/disease_detector.db

# 4. Xóa tệp nhật ký WAL cũ nếu có
rm -f database/disease_detector.db-wal database/disease_detector.db-shm

# 5. Phân quyền chuẩn cho container UID 1000
chown -R 1000:1000 database/

# 6. Khởi động lại backend
docker compose start gari-backend
```

### Bước 2.3: Kiểm tra tính toàn vẹn (Integrity Check)
```bash
sqlite3 database/disease_detector.db "PRAGMA integrity_check;"
```
*Kết quả kỳ vọng:* Trả về dòng chữ `ok`.

---

## 4. KỊCH BẢN 3: HOÀN NGUYÊN VERCEL PROXY VỀ MÁY CÁ NHÂN (FAILOVER)

Nếu toàn bộ máy chủ Oracle Cloud VM gặp sự cố mạng phần cứng kéo dài hoặc bảo trì của nhà cung cấp:

1. **Khởi động Cloudflare Tunnel trên máy phát triển cá nhân:**
   ```powershell
   cd D:\leaf-diseases-detector-main
   .\cloudflared.exe tunnel --url http://127.0.0.1:8000
   ```
   Lấy URL tạm thời (ví dụ: `https://ist-towards-exclude-said.trycloudflare.com`).

2. **Cập nhật Vercel Environment Variables:**
   - Vào [https://vercel.com](https://vercel.com) $\rightarrow$ Dự án `gari-team` $\rightarrow$ **Settings** $\rightarrow$ **Environment Variables**.
   - Đổi `VERCEL_BACKEND_API_URL` thành:
     ```text
     https://ist-towards-exclude-said.trycloudflare.com
     ```
   - Nhấn **Save** và **Redeploy**.
3. Toàn bộ người dùng trên giao diện Production `https://gari-team.vercel.app/frontend2` sẽ được chuyển hướng về backend máy cá nhân trong vòng **30 giây**, không có người dùng nào bị gián đoạn dịch vụ chẩn đoán bệnh.

---

## 5. BẢNG KIỂM XÁC MINH SAU KHI HOÀN NGUYÊN (POST-ROLLBACK CHECKLIST)

- [ ] Lệnh `bash deploy/oracle/healthcheck.sh` báo **PASS** cho toàn bộ 5/5 bài kiểm tra.
- [ ] Lệnh `docker compose ps` xác nhận cả `gari-backend` và `gari-nginx` đều ở trạng thái `Up (healthy)`.
- [ ] Thư viện cây trồng trên giao diện Web tải đầy đủ thông tin và danh mục bệnh.
- [ ] Gửi thử nghiệm một ảnh lá cây lên chẩn đoán để xác nhận mạng nơ-ron ConvNeXt hoạt động bình thường.
- [ ] Kiểm tra dung lượng RAM qua lệnh `free -h` và `docker stats --no-stream` đảm bảo RAM dưới 50%.

