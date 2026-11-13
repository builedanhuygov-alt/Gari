# BẢNG KIỂM THIẾT LẬP ORACLE CLOUD CONSOLE
## GARI AgriTech AI Lab — Oracle Cloud Infrastructure Pre-Flight Checklist

> **Hướng dẫn:** Sử dụng bảng kiểm này khi thao tác trực tiếp trên giao diện [Oracle Cloud Console](https://cloud.oracle.com). Hãy tích chọn từng mục để đảm bảo không bỏ sót bất kỳ thông số cấu hình quan trọng nào.

---

## 1. BẢNG KIỂM TRƯỚC KHI TẠO (PRE-REQUISITES)

- [ ] Đã đăng nhập thành công vào [Oracle Cloud Console](https://cloud.oracle.com).
- [ ] Đã chọn đúng Region mong muốn (ví dụ: `ap-singapore-1`, `ap-tokyo-1` hoặc region mặc định của tài khoản).
- [ ] Đã chuẩn bị sẵn một cặp SSH Key trên máy cá nhân (`id_ed25519` hoặc `id_rsa`), hoặc sẵn sàng tải SSH Key do OCI tự sinh về máy.
- [ ] Đã kiểm tra hạn mức Always Free khả dụng trong phần **Governance & Administration** $\rightarrow$ **Limits, Quotas and Usage**.

---

## 2. CẤU HÌNH MẠNG VÀ TƯỜNG LỬA (VCN & INGRESS RULES)

Trong menu $\equiv$ $\rightarrow$ **Networking** $\rightarrow$ **Virtual Cloud Networks**:

- [ ] Đã tạo VCN mới (khuyến nghị dùng tính năng **Start VCN Wizard** $\rightarrow$ *Create VCN with Internet Connectivity*).
- [ ] VCN có một **Public Subnet** hoạt động với Default Route trỏ về Internet Gateway (`0.0.0.0/0`).
- [ ] Đã mở tệp **Default Security List for VCN** và thêm chính xác 3 Ingress Rules:
  - [ ] **Rule 1 — SSH:**
    - Source CIDR: `0.0.0.0/0`
    - Protocol: `TCP`
    - Destination Port: `22`
  - [ ] **Rule 2 — HTTP (Nginx / Certbot):**
    - Source CIDR: `0.0.0.0/0`
    - Protocol: `TCP`
    - Destination Port: `80`
  - [ ] **Rule 3 — HTTPS (Nginx SSL):**
    - Source CIDR: `0.0.0.0/0`
    - Protocol: `TCP`
    - Destination Port: `443`
- [ ] **BẢO MẬT BẮT BUỘC:** Đảm bảo **KHÔNG CÓ** Ingress Rule nào mở port `8000` ra ngoài công khai.

---

## 3. KHỞI TẠO MÁY CHỦ ẢO (COMPUTE INSTANCE SIZING)

Trong menu $\equiv$ $\rightarrow$ **Compute** $\rightarrow$ **Instances** $\rightarrow$ Nhấn **Create instance**:

### 3.1. Thông tin chung & Hệ điều hành
- [ ] **Name:** Đặt tên rõ ràng (ví dụ: `gari-production-vm`).
- [ ] **Placement:** Availability Domain mặc định (AD-1).
- [ ] **Image:** Bấm *Change image* $\rightarrow$ Chọn **Canonical Ubuntu** $\rightarrow$ Chọn phiên bản **Ubuntu 22.04 Minimal LTS** hoặc **Ubuntu 22.04 LTS**.
- [ ] Xác nhận kiến trúc hiển thị là **aarch64 (ARM)**.

### 3.2. Cấu hình phần cứng (Shape & Resources)
- [ ] Bấm *Change shape* $\rightarrow$ Chọn loại **Ampere (ARM-based processor)**.
- [ ] Tích chọn hình dạng: **`VM.Standard.A1.Flex`** (Có nhãn *Always Free Eligible*).
- [ ] Kéo thanh trượt OCPU: **2 OCPUs** (hoặc 4 OCPUs nếu region còn quota).
- [ ] Kéo thanh trượt RAM: **12 GB RAM** (hoặc 24 GB RAM nếu dùng toàn bộ hạn mức).
> [!NOTE]
> *Trường hợp gặp thông báo `Out of capacity`:* Hãy hạ xuống cấu hình **1 OCPU và 6 GB RAM** (vẫn đảm bảo chạy tốt GARI với mức đỉnh 1.76 GB RAM).

### 3.3. Mạng & SSH
- [ ] **Primary VNIC:** Chọn Public Subnet vừa tạo ở Mục 2.
- [ ] **Public IPv4 address:** Chọn **Automatically assign public IPv4 address**.
- [ ] **Add SSH keys:**
  - Tải lên tệp public key của bạn (`.pub`), HOẶC
  - Chọn *Generate a key pair for me* $\rightarrow$ **BẮT BUỘC BẤM "Save private key"** để tải file `.key` về máy.

### 3.4. Ổ đĩa khởi động (Boot Volume)
- [ ] Tích chọn **Specify a custom boot volume size**.
- [ ] Nhập dung lượng: **80 GB** hoặc **100 GB** (Nằm an toàn trong 200 GB miễn phí).
- [ ] Nhấn **Create** để bắt đầu khởi tạo.

---

## 4. BẢNG KIỂM NGAY SAU KHI TẠO XONG (POST-CREATION CHECKLIST)

- [ ] Trạng thái máy chủ chuyển sang **RUNNING** màu xanh lá.
- [ ] Đã ghi lại địa chỉ **Public IP Address** (ví dụ: `129.150.x.x`).
- [ ] Đã thử nghiệm kết nối SSH thành công từ máy cá nhân:
  ```bash
  ssh -i "path/to/private_key.key" ubuntu@<PUBLIC_IP>
  ```
- [ ] Kiểm tra kiến trúc CPU bằng lệnh:
  ```bash
  uname -m
  ```
  *Kết quả phải trả về:* `aarch64`.
- [ ] Máy chủ đã sẵn sàng để thực thi Runbook triển khai (`ORACLE_DEPLOYMENT_RUNBOOK.md`).

