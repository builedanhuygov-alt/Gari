# CẨM NANG VẬN HÀNH TRIỂN KHAI ORACLE CLOUD (RUNBOOK)
## GARI AgriTech AI Lab — Oracle Cloud Production Operations Runbook

> **Đối tượng sử dụng:** Kỹ sư vận hành hệ thống, DevOps Engineer và Quản trị viên.  
> **Mục tiêu:** Cung cấp hướng dẫn chi tiết từng dòng lệnh để triển khai, giám sát, khắc phục sự cố và bảo trì hệ thống GARI trên máy chủ ảo Oracle Cloud.

---

## 1. QUY TRÌNH TRIỂN KHAI TỪNG BƯỚC (STEP-BY-STEP RUNBOOK)

### Giai đoạn 1: Kết nối SSH vào Máy chủ VM
Sau khi bạn đã tạo VM trên Oracle Cloud Console (theo Checklist cài đặt):
```bash
# Trên máy tính cá nhân (PowerShell hoặc Terminal Linux/macOS)
ssh -i "path/to/your_private_key.key" ubuntu@<VM_PUBLIC_IP>
```

### Giai đoạn 2: Cài đặt Môi trường Hệ thống (Bootstrap)
Trên cửa sổ SSH của máy chủ:
```bash
# 1. Clone repository về máy chủ
git clone https://github.com/<your-repo>/leaf-diseases-detector-main.git gari
cd gari

# 2. Chạy kịch bản bootstrap với quyền sudo
# Script sẽ tự động cài Docker, UFW firewall, mở port iptables OCI và cấu hình 4GB Swapfile
sudo bash deploy/oracle/bootstrap.sh
```

### Giai đoạn 3: Đồng bộ Mô hình AI và Cơ sở Dữ liệu
Mở một cửa sổ Terminal/PowerShell thứ hai trên **máy cá nhân** (nơi có thư mục dự án):

```powershell
# 1. Đồng bộ thư mục models (5.04 GB)
scp -i "path/to/your_private_key.key" -r "D:\leaf-diseases-detector-main\models" ubuntu@<VM_PUBLIC_IP>:~/gari/

# 2. Đồng bộ tệp SQLite hiện tại
scp -i "path/to/your_private_key.key" "D:\leaf-diseases-detector-main\database\disease_detector.db" ubuntu@<VM_PUBLIC_IP>:~/gari/database/
```

### Giai đoạn 4: Cấu hình Biến Môi trường & Khởi chạy Docker
Quay lại cửa sổ SSH trên máy chủ VM:
```bash
cd ~/gari

# 1. Tạo tệp .env
cp .env.example .env

# 2. Khởi tạo JWT Secret ngẫu nhiên an toàn
sed -i "s/replace_with_a_secure_random_string_at_least_32_chars_long/$(openssl rand -hex 32)/" .env

# 3. Phân quyền thư mục cho container user (UID 1000)
sudo chown -R 1000:1000 database logs
chmod -R 775 database logs

# 4. Khởi chạy deployment tự động
bash deploy/oracle/deploy.sh
```

### Giai đoạn 5: Cấu hình Tên miền & Chứng chỉ SSL HTTPS
1. Tạo bản ghi DNS `A` tại nhà cung cấp tên miền của bạn:
   - **Host:** `api` (ví dụ: `api.gari.farm`)
   - **Points to:** `<VM_PUBLIC_IP>`
2. Cấp phát chứng chỉ Let's Encrypt trên máy chủ VM:
```bash
# Tạm dừng Nginx để Certbot dùng port 80
docker compose stop nginx

# Cấp phát chứng chỉ SSL
sudo certbot certonly --standalone -d api.yourdomain.com --agree-tos -m your_email@example.com --non-interactive

# Sao chép chứng chỉ vào thư mục cấu hình Nginx
sudo mkdir -p /etc/letsencrypt/live/gari
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem /etc/letsencrypt/live/gari/
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem /etc/letsencrypt/live/gari/
sudo chmod -R 755 /etc/letsencrypt

# Khởi động lại Nginx
docker compose up -d nginx
```

### Giai đoạn 6: Kiểm tra Sức khỏe Hệ thống (Verification)
```bash
# Kiểm tra nội bộ
bash deploy/oracle/healthcheck.sh http://127.0.0.1:8000

# Kiểm tra qua HTTPS công khai
bash deploy/oracle/healthcheck.sh https://api.yourdomain.com
```
*Kết quả:* Tất cả 5 bước kiểm tra báo **PASS** màu xanh lá.

---

## 2. NHẬT KÝ VẬN HÀNH & GIÁM SÁT THƯỜNG NHẬT (DAY-2 OPERATIONS)

### 2.1. Xem nhật ký thời gian thực (Live Logs)
```bash
# Xem log của FastAPI backend
docker compose logs -f --tail=100 gari-backend

# Xem log của Nginx
docker compose logs -f --tail=100 nginx
```

### 2.2. Kiểm tra tài nguyên và bộ nhớ (Resource Usage)
```bash
# Kiểm tra mức tiêu thụ RAM/CPU của từng container
docker stats --no-stream

# Kiểm tra RAM và dung lượng Swap của máy chủ
free -h

# Kiểm tra dung lượng ổ đĩa
df -h
```

### 2.3. Khởi động lại hoặc cập nhật phiên bản mới
```bash
# Khởi động lại dịch vụ
docker compose restart

# Cập nhật mã nguồn mới từ Git
git pull origin main
docker compose build gari-backend
docker compose up -d
```

### 2.4. Thiết lập Lịch sao lưu Cơ sở dữ liệu tự động (Daily Cronjob)
```bash
crontab -e
```
Dán cấu hình sau vào cuối tệp:
```cron
# Tự động sao lưu SQLite vào 02:00 sáng mỗi ngày, xóa bản lưu cũ hơn 14 ngày
0 2 * * * cd /home/ubuntu/gari && sqlite3 database/disease_detector.db ".backup database/backups/backup_$(date +\%Y\%m\%d_\%H\%M\%S).db" && find database/backups/ -type f -name "*.db" -mtime +14 -delete
```

---

## 3. HƯỚNG DẪN XỬ LÝ SỰ CỐ NHANH (TROUBLESHOOTING RUNBOOK)

| Triệu chứng sự cố | Nguyên nhân khả dĩ | Lệnh xử lý nhanh |
| :--- | :--- | :--- |
| **Không truy cập được port 80/443 từ ngoài** | IPTables của Oracle OS đang chặn | Chạy: `sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT && sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT && sudo netfilter-persistent save` |
| **Lỗi `Permission denied: database/...`** | Container user UID 1000 không có quyền ghi | Chạy: `sudo chown -R 1000:1000 database logs && sudo chmod -R 775 database logs` |
| **Container thoát với mã `137` (OOM Killer)** | Hết RAM hệ thống khi nạp mô hình lớn | Kiểm tra swapfile: `swapon --show`. Nếu chưa có, chạy lại phần Swap trong `bootstrap.sh`. |
| **Nginx trả về lỗi `502 Bad Gateway`** | Container `gari-backend` đang khởi động lại | Chạy: `docker compose ps` để xem trạng thái, kiểm tra log bằng `docker compose logs gari-backend`. |
| **Nginx trả về lỗi `504 Gateway Timeout`** | Model tải chậm lần đầu vượt quá timeout Nginx | Kiểm tra `proxy_read_timeout 90s;` trong `deploy/oracle/nginx/conf.d/gari.conf`. |

