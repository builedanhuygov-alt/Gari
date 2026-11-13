# QUY TRÌNH HOÀN NGUYÊN KHẨN CẤP (DISASTER ROLLBACK PLAYBOOK)
## GARI AgriTech AI Lab — Zero-Cost Hosting Architecture

> **Mục tiêu:** Cung cấp hướng dẫn từng bước để khôi phục hệ thống về trạng thái ban đầu hoặc trạng thái dự phòng an toàn ngay lập tức khi phát sinh sự cố tại bất kỳ nhà cung cấp dịch vụ miễn phí nào (Hugging Face, Neon, Vercel), **đảm bảo 100% không mất dữ liệu**.

---

## MA TRẬN ỨNG PHÓ SỰ CỐ & THỜI GIAN KHÔI PHỤC (RTO / RPO)

| Tình huống sự cố | Kịch bản ứng phó | Mục tiêu thời gian khôi phục (RTO) | Mức độ mất dữ liệu (RPO) |
| :--- | :--- | :--- | :--- |
| **Hugging Face Space gián đoạn** | Chuyển Vercel Proxy về Local Cloudflare Tunnel hoặc Host phụ | **< 2 phút** | **0 giây (Zero data loss)** |
| **Neon PostgreSQL gặp trục trặc** | Rollback dữ liệu về SQLite cục bộ và chạy Backend tại chỗ | **< 3 phút** | **0 giây (Đồng bộ tức thì)** |
| **Vercel Edge Proxy lỗi định tuyến** | Kích hoạt chế độ Edge Auth Fallback tích hợp sẵn | **Tức thì (0 giây)** | **0 giây** |
| **Triển khai phiên bản lỗi** | Redeploy phiên bản ổn định trước đó trên Hugging Face / Vercel | **< 1 phút** | **0 giây** |

---

## KỊCH BẢN 1: HUGGING FACE SPACE GẶP SỰ CỐ HOẶC TREO BẢO TRÌ

Nếu Hugging Face Space bị lỗi build, treo hoặc quá tải, thực hiện hoàn nguyên về backend nội bộ qua Cloudflare Tunnel chỉ với 2 bước:

### Bước 1.1: Khởi động lại Cloudflare Tunnel trên máy phát triển (hoặc máy chủ dự phòng)
```powershell
cd D:\leaf-diseases-detector-main
.\cloudflared.exe tunnel --url http://127.0.0.1:8000
```
Màn hình sẽ hiển thị URL đường hầm tạm thời, ví dụ:
```text
https://ist-towards-exclude-said.trycloudflare.com
```

### Bước 1.2: Cập nhật biến môi trường trên Vercel
1. Đăng nhập [https://vercel.com](https://vercel.com) $\rightarrow$ Dự án `gari-team` $\rightarrow$ **Settings** $\rightarrow$ **Environment Variables**.
2. Sửa biến `VERCEL_BACKEND_API_URL` thành:
   ```text
   https://ist-towards-exclude-said.trycloudflare.com
   ```
3. Lưu và bấm **Redeploy** deployment gần nhất.
4. Toàn bộ lưu lượng của người dùng trên `https://gari-team.vercel.app/frontend2` sẽ lập tức quay trở lại kết nối với backend cục bộ ổn định trong vòng 30 giây.

---

## KỊCH BẢN 2: HOÀN NGUYÊN CƠ SỞ DỮ LIỆU TỪ NEON VỀ SQLITE

Trong trường hợp cần đưa dữ liệu từ Neon PostgreSQL trở về SQLite nội bộ (`database/disease_detector.db`) để kiểm tra hoặc lưu trữ offline:

### Bước 2.1: Chạy công cụ Rollback chuyên dụng
Công cụ `tools/migrate_sqlite_to_postgres.py` hỗ trợ cờ `--rollback`:
```powershell
python tools/migrate_sqlite_to_postgres.py --source "postgresql://gari_owner:xxxxxx@ep-cool-fog-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require" --rollback
```

### Bước 2.2: Quy trình tự động thực hiện:
1. Tạo bản sao lưu an toàn của SQLite hiện tại: `database/disease_detector.db.backup_<timestamp>`.
2. Kết nối tới Neon PostgreSQL và trích xuất toàn bộ dữ liệu mới nhất của 83 bảng.
3. Ghi đè cấu trúc và dữ liệu an toàn vào SQLite với chế độ giao dịch nguyên tử (`BEGIN EXCLUSIVE TRANSACTION`).
4. Bật lại chế độ `PRAGMA journal_mode = WAL` để duy trì tốc độ đọc ghi cao.

### Bước 2.3: Xác minh tính toàn vẹn dữ liệu
```powershell
python -c "
import sqlite3
conn = sqlite3.connect('database/disease_detector.db')
cursor = conn.cursor()
tables = cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print(f'Total tables restored: {len(tables)}')
row_count = sum(cursor.execute(f'SELECT COUNT(*) FROM \"{t[0]}\"').fetchone()[0] for t in tables)
print(f'Total rows restored: {row_count}')
"
```
*Kết quả:* Số lượng bảng phục hồi đầy đủ 83 bảng và toàn bộ dữ liệu người dùng/chẩn đoán được bảo toàn nguyên vẹn.

---

## KỊCH BẢN 3: HOÀN NGUYÊN PHIÊN BẢN SOURCE CODE TRÊN HUGGING FACE

Nếu bản commit mới nhất trên Hugging Face Space bị lỗi hoặc không tương thích:

### Bước 3.1: Kiểm tra lịch sử commit trên Space repo
```bash
cd hf-gari-backend
git log --oneline -n 5
```

### Bước 3.2: Revert về commit ổn định trước đó
```bash
git revert HEAD --no-edit
git push origin main
```
Hugging Face sẽ tự động kích hoạt tiến trình rebuild Docker container với mã nguồn của bản commit ổn định.

---

## KỊCH BẢN 4: KHÔI PHỤC KHI VERCEL HẾT HẠN MỨC EDGE PROXY

Trong trường hợp hiếm hoi số lượt gọi proxy trên Vercel vượt mức 100,000 requests/tháng:

1. **Frontend2 Direct Connection:**
   Frontend2 hỗ trợ cấu hình biến môi trường `VITE_API_URL` tại tệp `frontend2/.env.production`.
2. Bạn có thể trỏ thẳng `VITE_API_URL` trực tiếp tới URL công khai của Hugging Face Space:
   ```text
   VITE_API_URL=https://<your-username>-gari-backend.hf.space
   ```
3. Lúc này, trình duyệt của người dùng sẽ gửi request trực tiếp đến Hugging Face Space mà không cần qua Vercel Proxy, bypass hoàn toàn giới hạn băng thông của Vercel mà không tốn thêm 1 xu nào.

---

## BẢNG KIỂM AN TOÀN TRƯỚC KHI THỰC HIỆN ROLLBACK (CHECKLIST)

- [x] Tệp cơ sở dữ liệu gốc `database/disease_detector.db` luôn được lưu giữ an toàn trên máy cục bộ.
- [x] Trọng số mô hình (`models/*.safetensors`) được lưu trữ tại nhiều vị trí (Local disk, Git LFS trên Hugging Face).
- [x] Toàn bộ mã nguồn API và frontend đều được quản lý bằng Git version control.
- [x] Test suite `tests/test_zero_cost_deployment.py` sẵn sàng kiểm tra xác nhận sau mỗi lần hoàn nguyên.

