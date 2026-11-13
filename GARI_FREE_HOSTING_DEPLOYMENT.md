# HƯỚNG DẪN TRIỂN KHAI CLOUD HOSTING 0 ĐỒNG — GARI AGRITECH AI LAB
## Hướng dẫn từng bước (Step-by-Step Production Playbook)

> **Mục tiêu:** Đưa toàn bộ hệ thống GARI AgriTech AI Lab lên Cloud với **chi phí chính xác 0 USD / tháng**, vĩnh viễn không yêu cầu thẻ tín dụng, độc lập hoàn toàn khỏi máy cá nhân của lập trình viên và Cloudflare Quick Tunnel tạm thời.

---

## TỔNG QUAN LUỒNG TRIỂN KHAI

```mermaid
flowchart TD
    A["1. Tạo Database Neon PostgreSQL (0 USD)"] --> B["2. Chạy Migration Tool SQLite -> Neon"]
    B --> C["3. Khởi tạo Hugging Face Space (Docker, 16GB RAM)"]
    C --> D["4. Thiết lập Biến Môi trường Space"]
    D --> E["5. Đẩy Source Code & Model Registry lên HF"]
    E --> F["6. Thiết lập Uptime Keep-Alive (cron-job.org)"]
    F --> G["7. Cập nhật VERCEL_BACKEND_API_URL trên Vercel"]
    G --> H["8. Kiểm thử E2E & Chấp nhận Production"]
```

---

## BƯỚC 1: KHỞI TẠO NEON SERVERLESS POSTGRESQL (0 ĐỒNG)

Neon cung cấp PostgreSQL Serverless miễn phí trọn đời (Free Tier), không yêu cầu thẻ tín dụng, 1 GB dung lượng lưu trữ (GARI hiện tại dùng ~9.2 MB, tức < 1%).

1. Truy cập [https://neon.tech](https://neon.tech) và chọn **Sign Up** (đăng nhập bằng GitHub hoặc Google).
2. Tạo dự án mới:
   - **Project name:** `gari-production-db`
   - **Postgres version:** `16` (hoặc mới nhất)
   - **Region:** `ap-southeast-1` (Singapore) hoặc `us-east-1` (khuyến nghị Singapore để tối ưu độ trễ cho người dùng Việt Nam).
3. Sau khi tạo xong, màn hình sẽ hiển thị Connection String dạng:
   ```text
   postgresql://gari_owner:xxxxxx@ep-cool-fog-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Lưu chuỗi này lại cẩn thận. Bạn sẽ sử dụng nó trong Bước 2 và Bước 4.

---

## BƯỚC 2: CHUYỂN DỮ LIỆU SQLITE SANG POSTGRESQL

Dự án đã tích hợp sẵn công cụ tự động chuyển đổi an toàn: `tools/migrate_sqlite_to_postgres.py`. Công cụ này tự động chuyển đổi kiểu dữ liệu, giải quyết khóa ngoại (Foreign Keys) và đồng bộ auto-increment sequences.

### 2.1. Cài đặt thư viện kết nối (nếu chưa có)
```powershell
pip install psycopg2-binary
```

### 2.2. Chạy kiểm tra mô phỏng (Dry-run - Không ghi dữ liệu)
```powershell
python tools/migrate_sqlite_to_postgres.py --target "postgresql://gari_owner:xxxxxx@ep-cool-fog-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require" --dry-run
```
*Kết quả kỳ vọng:* Toàn bộ 83 bảng và ~34.088 dòng dữ liệu được quét thành công với trạng thái `[DRY RUN] Complete: 83 tables evaluated`.

### 2.3. Thực thi chuyển dữ liệu chính thức
```powershell
python tools/migrate_sqlite_to_postgres.py --target "postgresql://gari_owner:xxxxxx@ep-cool-fog-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
```
*Kết quả kỳ vọng:*
- `[SUCCESS] Migration completed safely.`
- `Tables processed: 83`
- `Total rows transferred: ~34,088`
- `Auto-increment sequences reset successfully.`

---

## BƯỚC 3: TẠO HUGGING FACE SPACE (BACKEND & AI INFERENCE)

Hugging Face Spaces cung cấp môi trường Docker CPU Basic hoàn toàn miễn phí:
- **CPU:** 2 vCPU
- **RAM:** 16 GB (dư dả so với mức 1.76 GB peak RAM của GARI)
- **Disk:** 50 GB
- **Chi phí:** 0 USD / tháng, không yêu cầu thẻ tín dụng.

### 3.1. Tạo Space mới
1. Đăng nhập [https://huggingface.co](https://huggingface.co).
2. Nhấn vào Avatar góc trên cùng bên phải $\rightarrow$ Chọn **New Space**.
3. Điền thông tin:
   - **Space name:** `gari-backend` (hoặc tên tùy chọn).
   - **License:** `mit` hoặc `apache-2.0`.
   - **Space SDK:** Chọn **Docker** $\rightarrow$ Chọn **Blank**.
   - **Space Hardware:** Chọn **CPU basic - 2 vCPU - 16 GB RAM - FREE**.
   - **Visibility:** Chọn **Public** (để Vercel proxy có thể truy cập qua HTTPS).
4. Nhấn **Create Space**.

---

## BƯỚC 4: THIẾT LẬP BIẾN MÔI TRƯỜNG TRÊN HUGGING FACE

Vào Space của bạn $\rightarrow$ tab **Settings** $\rightarrow$ mục **Variables and secrets**:

### Secrets (Bảo mật - Click "New secret"):
| Tên Secret | Giá trị |
| :--- | :--- |
| `DATABASE_URL` | Chuỗi kết nối Neon Postgres ở Bước 1 (bắt buộc `sslmode=require`) |
| `JWT_SECRET_KEY` | Mã bí mật JWT của dự án (chuỗi ngẫu nhiên dài 32+ ký tự) |
| `FIREBASE_PROJECT_ID` | `gari-agritech` (hoặc Project ID Firebase của bạn) |
| `FIREBASE_CLIENT_EMAIL` | Email Service Account Firebase |
| `FIREBASE_PRIVATE_KEY` | Private Key Service Account Firebase |

### Variables (Biến công khai - Click "New variable"):
| Tên Variable | Giá trị | Giải thích |
| :--- | :--- | :--- |
| `GARI_ENV` | `production` | Kích hoạt cờ production |
| `GARI_ALLOW_ORIGINS` | `https://gari-team.vercel.app` | CORS bảo vệ API |
| `PORT` | `7860` | Cổng mặc định của Hugging Face Spaces |

---

## BƯỚC 5: ĐẨY MÃ NGUỒN VÀ MODELS LÊN HUGGING FACE SPACE

Repository của dự án đã có sẵn `Dockerfile` chuẩn hóa cho Hugging Face Spaces (UID 1000, cấu hình port `${PORT:-7860}`).

### 5.1. Clone repo Space về máy cục bộ
```bash
git clone https://huggingface.co/spaces/<your-username>/gari-backend hf-gari-backend
```

### 5.2. Sao chép các tệp cần thiết vào `hf-gari-backend`
Sao chép từ thư mục `D:\leaf-diseases-detector-main`:
- `api_server.py`
- `gari_inference_engine.py`
- `gari_knowledge_base.py`
- `gari_satellite_service.py`
- `gari_weather_service.py`
- `gari_risk_engine.py`
- `gari_digital_twin.py`
- `gari_agent_ecosystem.py`
- `gari_p2_modules.py`
- `Dockerfile`
- `requirements.txt`
- Thư mục `models/` (Bao gồm các trọng số `.safetensors` và `registry.json`)

> [!NOTE]
> Hugging Face hỗ trợ Git LFS mặc định cho các tệp lớn. Nếu tệp model > 10MB, hãy bật Git LFS:
> ```bash
> git lfs install
> git lfs track "*.safetensors" "*.onnx" "*.pth"
> ```

### 5.3. Commit và Push lên Hugging Face Space
```bash
cd hf-gari-backend
git add .
git commit -m "Deploy GARI AI Inference Backend to Hugging Face Spaces"
git push
```
Hugging Face sẽ tự động build Docker container. Sau khoảng 2-3 phút, Space sẽ chuyển sang trạng thái **Running** màu xanh lá.
Địa chỉ công khai của Space sẽ có định dạng:
```text
https://<your-username>-gari-backend.hf.space
```

Kiểm tra healthcheck trực tiếp trên trình duyệt:
```text
https://<your-username>-gari-backend.hf.space/health
```
Kết quả phản hồi JSON chuẩn:
```json
{
  "status": "ok",
  "database": "connected",
  "database_type": "postgresql",
  "models_loaded": 51
}
```

---

## BƯỚC 6: THIẾT LẬP KEEP-ALIVE 0 ĐỒNG (CHỐNG COLD START)

Hugging Face Space miễn phí sẽ tạm chuyển sang chế độ ngủ (Idle) sau 48 giờ không có truy cập. Để hệ thống luôn trực chiến 24/7 và sẵn sàng phản hồi trong < 500ms:

1. Truy cập dịch vụ cron miễn phí: [https://cron-job.org](https://cron-job.org).
2. Tạo tài khoản miễn phí (không cần thẻ).
3. Tạo **New Cronjob**:
   - **Title:** `GARI Backend Keep Alive`
   - **URL:** `https://<your-username>-gari-backend.hf.space/health`
   - **Execution schedule:** `Every 30 minutes` (Mỗi 30 phút một lần).
   - **Request method:** `GET`
4. Bấm **Save**. Từ lúc này, backend của bạn sẽ được ping định kỳ, giữ cho RAM và container luôn hoạt động 100% không bao giờ bị rơi vào Cold Start.

---

## BƯỚC 7: CẬP NHẬT VERCEL PROXY SANG CLOUD BACKEND

Đây là bước chuyển giao (cutover) cuối cùng để toàn bộ người dùng tại `https://gari-team.vercel.app/frontend2` kết nối trực tiếp đến backend cloud mới mà không còn phụ thuộc vào máy cá nhân.

1. Đăng nhập [https://vercel.com](https://vercel.com).
2. Chọn dự án `gari-team` $\rightarrow$ **Settings** $\rightarrow$ **Environment Variables**.
3. Tìm biến `VERCEL_BACKEND_API_URL` (hoặc tạo mới nếu chưa có):
   - **Value:** `https://<your-username>-gari-backend.hf.space`
   - **Environments:** Chọn cả 3 mục: `Production`, `Preview`, `Development`.
4. Nhấn **Save**.
5. Vào tab **Deployments** $\rightarrow$ Chọn deployment mới nhất $\rightarrow$ Bấm nút 3 chấm $\rightarrow$ Chọn **Redeploy** (để nạp biến môi trường mới).

---

## BƯỚC 8: KIỂM THỬ XÁC MINH TOÀN DIỆN (E2E VERIFICATION)

Chạy bộ kiểm thử tự động xác minh zero-cost deployment trên máy để đảm bảo mọi luồng hoạt động chuẩn:
```powershell
python -m unittest tests/test_zero_cost_deployment.py
```
*Kết quả:* **15/15 tests PASS**.

Kiểm tra thủ công trên trình duyệt tại `https://gari-team.vercel.app/frontend2`:
1. **Đăng nhập:** Đăng nhập tài khoản kiểm thử hoặc tạo tài khoản mới.
2. **Chẩn đoán bệnh (AI Inference):** Tải ảnh lá cà chua bị đốm lá (Septoria) lên $\rightarrow$ Hệ thống chẩn đoán trả về kết quả tiếng Việt chính xác trong ~1.2 giây.
3. **Thư viện cây trồng:** Kiểm tra hiển thị đầy đủ 51 mô hình và dữ liệu chi tiết.
4. **Bản đồ GIS & Digital Twin:** Tải lớp dữ liệu không gian và trạng thái nông trại.
5. **AI Agents:** Thử nghiệm trợ lý chuyên gia chẩn đoán và khuyến nông.

