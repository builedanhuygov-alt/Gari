# BÁO CÁO TIẾN ĐỘ VÀ TRẠNG THÁI TRIỂN KHAI ORACLE CLOUD
## GARI AgriTech AI Lab — Oracle Cloud Infrastructure Deployment Status

- **Kỹ sư phụ trách:** Senior DevOps & Backend Infrastructure Engineer
- **Thời điểm cập nhật:** 10/11/2026
- **Trạng thái tổng thể:** **SẴN SÀNG TRIỂN KHAI (PREPARED FOR VM PROVISIONING & CUTOVER)**

---

## 1. BẢNG TỔNG HỢP TRẠNG THÁI CÁC HẠNG MỤC (FINAL STATUS MATRIX)

| Hạng mục | Trạng thái | Bằng chứng thực nghiệm |
| :--- | :--- | :--- |
| **ARM64 Compatibility** | **VERIFIED** | Đã xác minh 100% thư viện (`torch==2.3.1`, `torchvision==0.18.1`, `safetensors`, `numpy`, `pillow`, `opencv-python-headless`, `bcrypt`) có binary wheel aarch64 chính thức trên PyPI. Đã loại bỏ dependency thừa `tensorflow-cpu`. |
| **Model Loading** | **VERIFIED** | 51 mô hình trong `models/` nạp mượt mà qua Safetensors PyTorch CPU. Thời gian nạp: `~978 ms` đến `1,071 ms`. |
| **Docker Build** | **COMPLETED** | `Dockerfile` và `docker-compose.yml` tối ưu hóa cho multi-architecture (linux/amd64 & linux/arm64), chạy non-root user (UID 1000 `gari`), mount models `:ro`, giới hạn RAM 12GB. |
| **SQLite Persistence** | **VERIFIED** | Chế độ WAL kích hoạt (`PRAGMA journal_mode = wal`), 83 bảng với 34,088 dòng dữ liệu được bảo vệ. Hot-backup script hoạt động an toàn không lock database. |
| **API Health** | **VERIFIED** | Endpoints `/health` và `/ready` trả về HTTP 200 `status="healthy"`. Đã kiểm chứng qua 13/13 automated staging tests. |
| **AI Inference** | **VERIFIED** | Chẩn đoán mô hình thật (`Tomato ConvNeXt-Small`) trả về `top_predictions`, `disease_name_vi` và Grad-CAM heatmap. Độ trễ warm: **326.8 ms** trên CPU (không cần GPU). |
| **HTTPS** | **PREPARED** | Cấu hình Nginx (`deploy/oracle/nginx/conf.d/gari.conf`) hỗ trợ SSL Let's Encrypt (Certbot), TLS 1.2/1.3, HSTS và auto-redirect HTTP $\rightarrow$ HTTPS. |
| **Security** | **COMPLETED** | UFW Firewall (chỉ mở 22, 80, 443), port 8000 nội bộ `127.0.0.1`, Nginx Rate Limiting (15 req/s), Scoped JWT Auth, Bcrypt hashing, Upload limit 25MB. |
| **External Access** | **PREPARED** | Hướng dẫn cấu hình OCI Ingress Rules và script chẩn đoán `deploy/oracle/healthcheck.sh` sẵn sàng. |
| **Frontend Integration** | **PREPARED** | CORS cấu hình nghiêm ngặt cho `https://gari-team.vercel.app`. Giữ nguyên Frontend2, sẵn sàng chuyển đổi biến `VERCEL_BACKEND_API_URL` sau khi người dùng xác nhận. |

---

## 2. DANH MỤC CÁC TÀI LIỆU VÀ CÔNG CỤ ĐÃ HOÀN THÀNH

### Tài liệu kỹ thuật:
1. `ORACLE_DEPLOYMENT_COMPATIBILITY_REPORT.md`: Báo cáo kiểm toán tương thích ARM64, thư viện native và hiệu năng CPU.
2. `ORACLE_VM_RESOURCE_ESTIMATE.md`: Bảng tính toán và quy hoạch RAM, CPU, Disk, Swapfile cho Oracle Always Free.
3. `GARI_ORACLE_DEPLOYMENT_GUIDE.md`: Cẩm nang hướng dẫn từng bước tạo VM, cấu hình firewall, deploy Docker, cài HTTPS và cronjob.
4. `GARI_ORACLE_SECURITY_CHECKLIST.md`: Bảng kiểm 14 tiêu chuẩn an ninh mạng và bảo mật DevSecOps.
5. `GARI_ORACLE_TEST_REPORT.md`: Báo cáo 13/13 ca kiểm thử staging tự động đạt 100% PASS.
6. `GARI_ORACLE_ROLLBACK_GUIDE.md`: Quy trình hoàn nguyên khẩn cấp RTO < 3 phút, bảo vệ 100% dữ liệu.
7. `GARI_ORACLE_DEPLOYMENT_STATUS.md`: Bản theo dõi tiến độ tổng thể.

### Kịch bản tự động hóa (Scripts & Configuration):
- `deploy/oracle/bootstrap.sh`: Tự động cài đặt Docker, UFW, Swapfile 4GB, Certbot trên máy chủ mới.
- `deploy/oracle/deploy.sh`: Tự động build image, cấu hình phân quyền và khởi động hệ thống.
- `deploy/oracle/healthcheck.sh`: Công cụ chẩn đoán sức khỏe 5 tầng với màu sắc trực quan.
- `deploy/oracle/rollback.sh`: Kịch bản hoàn nguyên khẩn cấp và khôi phục database từ bản sao lưu.
- `deploy/oracle/nginx/nginx.conf`: Tối ưu hóa hiệu năng, rate limiting zones và gzip.
- `deploy/oracle/nginx/conf.d/gari.conf`: Virtual host SSL termination, proxy timeout 90s và security headers.
- `Dockerfile`: Hỗ trợ đa kiến trúc CPU, user UID 1000 cách ly an toàn.
- `docker-compose.yml`: Quản lý cụm dịch vụ FastAPI và Nginx với tài nguyên giới hạn chuẩn.
- `requirements-production.txt`: Tối ưu hóa sạch sẽ các binary wheels cho ARM64/x86_64.
- `tests/test_oracle_staging.py`: Bộ kiểm thử tự động 13 kịch bản trước khi đưa vào sản xuất.

---

## 3. CÁC BƯỚC TIẾP THEO CHO NGƯỜI DÙNG (USER ACTION ITEMS)

Tuân thủ nguyên tắc bắt buộc: **Không tự ý tạo tài khoản hay thay đổi production URL khi chưa có lệnh của người dùng.**

Khi bạn sẵn sàng triển khai thực tế lên tài khoản Oracle Cloud của mình:
1. Đăng nhập [cloud.oracle.com](https://cloud.oracle.com) và tạo 1 VM Ampere A1 (2-4 OCPU, 12-24 GB RAM) theo **Bước 1** trong [GARI_ORACLE_DEPLOYMENT_GUIDE.md](file:///d:/leaf-diseases-detector-main/GARI_ORACLE_DEPLOYMENT_GUIDE.md).
2. Mở Ingress Rules port 80 và 443 trên OCI Console theo **Bước 2**.
3. Chạy lệnh bootstrap và deploy theo hướng dẫn:
   ```bash
   sudo bash deploy/oracle/bootstrap.sh
   bash deploy/oracle/deploy.sh
   ```
4. Kiểm tra sức khỏe hệ thống từ bên ngoài qua `bash deploy/oracle/healthcheck.sh`.
5. Khi bạn xác nhận hệ thống trên VM hoạt động hoàn hảo, cập nhật biến `VERCEL_BACKEND_API_URL` trên Vercel sang địa chỉ của Oracle VM. Backend cũ trên máy cá nhân vẫn được duy trì làm phương án dự phòng an toàn.

