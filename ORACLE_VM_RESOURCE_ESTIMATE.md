# ĐỊNH LƯỢNG TÀI NGUYÊN VÀ QUY HOẠCH MÁY CHỦ ORACLE CLOUD
## GARI AgriTech AI Lab — Oracle Cloud VM Resource Sizing & Capacity Planning

- **Tác giả:** Senior DevOps & Cloud Infrastructure Engineer
- **Thời điểm lập kế hoạch:** 10/11/2026
- **Đối tượng:** Máy chủ ảo Oracle Cloud Infrastructure (OCI) Compute Instance

---

## 1. KHUNG TÀI NGUYÊN ORACLE CLOUD ALWAYS FREE

Chính sách Always Free của Oracle Cloud cung cấp cho mỗi tài khoản:
- **Ampere A1 Compute (ARM64):** Tối đa **4 OCPUs** và **24 GB RAM** (có thể gộp thành 1 VM lớn hoặc chia nhỏ thành 2 VM).
- **Lưu trữ khối (Block Volumes):** Tối đa **200 GB** dung lượng lưu trữ phân bổ cho Boot Volumes và Block Volumes.
- **Băng thông mạng ra (Egress):** **10 TB / tháng** miễn phí.
- **Địa chỉ IP:** 1 IPv4 Public cố định hoặc tạm thời miễn phí.

> [!WARNING]
> **Thực tế phân bổ tài nguyên OCI (Capacity Availability):**
> Tại một số Region của Oracle Cloud (ví dụ Singapore `ap-singapore-1`, Tokyo `ap-tokyo-1`), đôi khi người dùng gặp thông báo `Out of capacity for shape VM.Standard.A1.Flex`. Do đó, kế hoạch tài nguyên cần phân tách rõ **Cấu hình tối thiểu khả thi** (để tạo được ngay khi tài nguyên hạn chế) và **Cấu hình tối ưu khuyến nghị**.

---

## 2. BẢNG PHÂN RÃ TIÊU THỤ BỘ NHỚ RAM THỰC TẾ

Dựa trên kết quả đo đạc thực nghiệm từ tiến trình Python và tải trọng thực tế:

| Phân vùng tài nguyên | Mức tiêu thụ tối thiểu | Mức tiêu thụ bình thường | Mức tiêu thụ đỉnh (Peak Load) | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- | :--- |
| **Hệ điều hành (Linux Ubuntu 22.04 LTS / OL9)** | 350 MB | 450 MB | 600 MB | Kernel, Systemd, SSH, UFW, Network stack |
| **Nginx Reverse Proxy** | 20 MB | 35 MB | 60 MB | SSL Termination, Rate Limiting, Proxy Buffers |
| **GARI FastAPI Base & Services** | 280 MB | 340 MB | 420 MB | 83 tables SQLite, Auth, RBAC, 7 AI Agents |
| **Model Registry Metadata (51 mô hình)** | 40 MB | 45 MB | 50 MB | Danh mục cây trồng, bệnh, nhãn classes |
| **Model PyTorch Cache (LRU = 3)** | 280 MB | 850 MB | 1,150 MB | 3 mô hình ConvNeXt-Small thường trực |
| **ViT Global Router (`Model tong`)** | 0 MB | 327 MB | 350 MB | Kích hoạt khi phân loại tổng quan |
| **Đệm xử lý Concurrency (5-10 requests đồng thời)** | 150 MB | 400 MB | 800 MB | Tensor allocations, Grad-CAM heatmap buffers |
| **Hệ điều hành Disk Cache & Buffers** | 300 MB | 800 MB | 1,500 MB | Tối ưu hóa đọc file weights và database |
| **TỔNG CỘNG RAM YÊU CẦU** | **1,420 MB (~1.4 GB)** | **3,247 MB (~3.2 GB)** | **4,930 MB (~4.9 GB)** | |

---

## 3. BẢNG TÍNH DUNG LƯỢNG Ổ ĐĨA (DISK SPACE ESTIMATION)

| Thành phần dữ liệu | Dung lượng hiện tại | Dự phòng tăng trưởng (12 tháng) | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Hệ điều hành + Docker Engine** | 8.5 GB | 15.0 GB | Ubuntu 22.04, Docker CE, Nginx, Packages |
| **Docker Images (GARI Production)** | 2.8 GB | 6.0 GB | Python slim, PyTorch CPU, Dependencies |
| **AI Model Weights (`models/`)** | 5.04 GB | 8.0 GB | 51 mô hình `.safetensors`, định tuyến ViT |
| **Cơ sở dữ liệu SQLite (`database/`)** | 9.2 MB | 2.0 GB | 83 bảng, lịch sử chẩn đoán, nhiệm vụ |
| **Ảnh tải lên (`database/uploads/`)** | 15 MB | 10.0 GB | Ảnh lá bệnh nông dân gửi lên kiểm tra |
| **Nhật ký hệ thống & Docker Logs** | 100 MB | 5.0 GB | Cấu hình log-rotation tối đa 50MB x 3 files |
| **Khu vực đệm hệ thống (Swapfile)** | 4.0 GB | 4.0 GB | Phân vùng hoán đổi RAM an toàn |
| **TỔNG DUNG LƯỢNG Ổ ĐĨA** | **~20.5 GB** | **~50.0 GB** | |

---

## 4. ĐỀ XUẤT CẤU HÌNH MÁY CHỦ (VM SIZING RECOMMENDATIONS)

### 4.1. Cấu hình Khuyến nghị Tối ưu (Always Free Maximum)
Dành cho trường hợp Region của Oracle còn đủ dung lượng Ampere A1:
- **Shape:** `VM.Standard.A1.Flex`
- **Kiến trúc:** Ampere Altra (ARM64)
- **OCPU:** **4 OCPU** (tương đương 4 vCPU chuyên dụng)
- **RAM:** **24 GB RAM**
- **Boot Volume:** **100 GB** (Sử dụng 50% hạn mức 200GB miễn phí)
- **Khả năng chịu tải:**
  - Xử lý 30-50 yêu cầu chẩn đoán ảnh/phút mà không suy giảm hiệu năng.
  - Có thể nạp đồng thời 10+ mô hình vào RAM mà không cần evict.
  - Dư thừa tài nguyên để chạy thêm Redis cache hoặc dịch vụ nền trong tương lai.

### 4.2. Cấu hình Cân bằng (Balanced Deployment)
Khuyến nghị chia nhỏ tài nguyên để dự phòng hoặc khi cần 2 môi trường (Staging + Production):
- **Shape:** `VM.Standard.A1.Flex`
- **OCPU:** **2 OCPU**
- **RAM:** **12 GB RAM**
- **Boot Volume:** **60 GB**
- **Khả năng chịu tải:**
  - Hoạt động ổn định liên tục 24/7 với mức RAM tiêu thụ chỉ ~25-35%.
  - Giữ lại 2 OCPU và 12 GB RAM để tạo thêm 1 VM Staging hoặc dịch vụ khác.

### 4.3. Cấu hình Tối thiểu Tuyệt đối (Absolute Minimum Viable)
Áp dụng khi tạo VM trong điều kiện Region bị khan hiếm tài nguyên Ampere:
- **Shape:** `VM.Standard.A1.Flex`
- **OCPU:** **1 OCPU** (hoặc 2 OCPU nếu có thể)
- **RAM:** **6 GB RAM** (Tuyệt đối không dưới 4 GB)
- **Boot Volume:** **50 GB**
- **Cấu hình bổ sung bắt buộc:** Kích hoạt **4 GB Swapfile** trên đĩa để chống tràn bộ nhớ đột ngột.
- **Giới hạn tham số ứng dụng:**
  - Thiết lập biến môi trường `MAX_CACHED_MODELS=2`.
  - Giới hạn concurrency của Uvicorn: `--workers 1 --limit-concurrency 10`.

---

## 5. DỰ TOÁN BĂNG THÔNG MẠNG (NETWORK EGRESS CAPACITY)

- Hạn mức miễn phí OCI: **10,000 GB (10 TB) / tháng**.
- Mỗi lượt chẩn đoán trả về JSON kết quả + Grad-CAM heatmap nén: `~250 KB`.
- Với 10,000 lượt chẩn đoán/tháng: Băng thông tiêu hao $\approx 2.5\text{ GB} \ll 10,000\text{ GB}$ (chỉ chiếm **0.025%** hạn mức).
- Hệ thống hoàn toàn không có nguy cơ vượt ngưỡng băng thông.

