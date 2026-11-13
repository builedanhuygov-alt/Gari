# BẢNG KIỂM CHUYỂN GIAO PRODUCTION (CUTOVER CHECKLIST)
## GARI AgriTech AI Lab — Zero-Downtime Production Cutover Playbook

> **Mục tiêu:** Chuyển giao toàn bộ lưu lượng của người dùng từ hệ thống backend tạm thời (Cloudflare Tunnel trên máy cá nhân) sang máy chủ chính thức Oracle Cloud VM, **đảm bảo 0% gián đoạn dịch vụ (Zero-Downtime) và có kế hoạch hoàn nguyên tức thì trong 60 giây**.

---

## 1. ĐIỀU KIỆN TIÊN QUYẾT BẮT BUỘC TRƯỚC KHI CHUYỂN GIAO (GATE CHECK)

Chỉ được phép tiến hành chuyển giao khi **TẤT CẢ** các mục sau đây được xác nhận:

- [ ] Máy chủ Oracle VM đã khởi chạy cả 2 container `gari-backend` và `gari-nginx` ở trạng thái **Healthy**.
- [ ] Tên miền phụ (ví dụ: `api.gari.farm`) đã trỏ DNS A record thành công về Public IP của Oracle VM.
- [ ] Chứng chỉ SSL Let's Encrypt đã cấp phát thành công và HTTPS hoạt động không lỗi cảnh báo trình duyệt.
- [ ] Lệnh kiểm tra từ máy bên ngoài trả về 100% PASS:
  ```bash
  curl -I https://api.yourdomain.com/health
  # Phải trả về: HTTP/2 200 OK với đầy đủ security headers
  ```
- [ ] Đã chạy thử nghiệm gửi một ảnh lá bệnh lên endpoint chẩn đoán qua HTTPS và nhận được kết quả JSON tiếng Việt chính xác.
- [ ] Backend cũ trên máy cá nhân (`task-2629` chạy FastAPI port 8000 và `task-1310` chạy Cloudflare Tunnel) **VẪN ĐANG HOẠT ĐỘNG BÌNH THƯỜNG** làm phương án dự phòng khẩn cấp.

---

## 2. QUY TRÌNH THỰC HIỆN CHUYỂN GIAO (CUTOVER STEPS)

Thực hiện lần lượt các bước sau:

### Bước 1: Sao lưu trạng thái Cơ sở Dữ liệu trước giờ G
Trên máy tính cá nhân:
```powershell
cd D:\leaf-diseases-detector-main
python -c "
import sqlite3, time
conn = sqlite3.connect('database/disease_detector.db')
bck = sqlite3.connect(f'database/backups/pre_cutover_backup_{int(time.time())}.db')
conn.backup(bck)
bck.close()
conn.close()
print('Hot backup created successfully!')
"
```
- [ ] Đã xác nhận tệp sao lưu trước chuyển giao tồn tại trong `database/backups/`.

### Bước 2: Cập nhật Biến Môi trường trên Vercel
1. Đăng nhập vào [Vercel Dashboard](https://vercel.com).
2. Chọn dự án: **`gari-team`**.
3. Vào tab **Settings** $\rightarrow$ chọn **Environment Variables**.
4. Tìm biến: **`VERCEL_BACKEND_API_URL`**:
   - **Ghi lại giá trị cũ để dự phòng:** (ví dụ `https://ist-towards-exclude-said.trycloudflare.com`).
   - **Nhập giá trị mới:** `https://api.yourdomain.com` (Địa chỉ Oracle VM qua HTTPS).
   - **Môi trường áp dụng:** Tích chọn cả 3 mục: `Production`, `Preview`, `Development`.
5. Nhấn **Save**.
- [ ] Đã lưu biến môi trường mới trên Vercel.

### Bước 3: Kích hoạt Triển khai Cấu hình Mới (Redeploy)
1. Trên Vercel, vào tab **Deployments**.
2. Tìm bản build gần nhất đang chạy Production.
3. Bấm vào nút 3 chấm (`...`) ở góc bên phải $\rightarrow$ Chọn **Redeploy**.
4. Chờ khoảng **30 - 45 giây** cho quá trình build và phân phối edge proxy hoàn tất.
- [ ] Trạng thái Deployment trên Vercel báo **Ready** màu xanh lá.

---

## 3. KIỂM THỬ KHÓI SAU CHUYỂN GIAO (POST-CUTOVER SMOKE TEST)

Truy cập trực tiếp bằng trình duyệt vào `https://gari-team.vercel.app/frontend2`:

- [ ] **1. Tải trang chính:** Trang tổng quan tải nhanh, không xuất hiện thông báo lỗi máy chủ.
- [ ] **2. Kiểm tra Đăng nhập:** Đăng nhập vào tài khoản người dùng bình thường và tài khoản quản trị.
- [ ] **3. Chẩn đoán hình ảnh (AI Inference):** Tải lên một ảnh lá cây thật và kiểm tra kết quả chẩn đoán trả về trong < 1.5 giây.
- [ ] **4. Thư viện cây trồng:** Mở mục Cây trồng kiểm tra 51 mô hình hiển thị đầy đủ thông tin.
- [ ] **5. Lịch sử chẩn đoán:** Kiểm tra nhật ký chẩn đoán mới nhất được lưu vào database.
- [ ] **6. Không gian GIS & Nông trại:** Mở bản đồ nông trại và danh sách thửa đất.
- [ ] **7. Trợ lý AI Agents:** Đặt câu hỏi và thử nghiệm quy trình trợ lý khuyến nông.

---

## 4. QUY TRÌNH ROLLBACK KHẨN CẤP (NẾU PHÁT SINH SỰ CỐ)

Nếu sau khi chuyển giao phát sinh lỗi (ví dụ: HTTP 502, 504 hoặc giao diện không gọi được API):

1. **Khôi phục ngay lập tức trên Vercel:**
   - Vào Vercel $\rightarrow$ **Settings** $\rightarrow$ **Environment Variables**.
   - Sửa biến `VERCEL_BACKEND_API_URL` trở lại URL Cloudflare Tunnel cũ.
   - Bấm **Save** và bấm **Redeploy**.
2. **Thời gian phục hồi:** Toàn bộ người dùng sẽ quay trở lại kết nối với backend máy cá nhân trong vòng **dưới 60 giây**, hoàn toàn không làm gián đoạn người dùng.
- [ ] Đã nắm rõ quy trình rollback khẩn cấp.

---

## 5. THỜI GIAN THEO DÕI ỔN ĐỊNH (OBSERVATION WINDOW)

- Duy trì backend máy cá nhân và Cloudflare Tunnel hoạt động song song trong **24 đến 48 giờ**.
- Thường xuyên kiểm tra nhật ký máy chủ qua lệnh: `docker compose logs -f --tail=50 gari-backend`.
- Chỉ tắt backend máy cá nhân khi hệ thống trên Oracle Cloud VM đạt tỷ lệ phản hồi 100% ổn định sau 48 giờ.

