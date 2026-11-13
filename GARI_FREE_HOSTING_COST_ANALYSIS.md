# PHÂN TÍCH TÀI CHÍNH & ĐỊNH LƯỢNG CHI PHÍ HOSTING 0 ĐỒNG — GARI AGRITECH AI LAB
## Báo cáo Kiểm toán Chi phí Trọn đời (Exhaustive Zero-Cost Financial Audit)

> **Khẳng định kiến trúc:** Toàn bộ giải pháp hạ tầng được thiết kế để duy trì **chính xác 0.00 USD / tháng**, vĩnh viễn không cần thẻ tín dụng, không dùng "trial period" giả lập, và có cơ chế bảo vệ vật lý ngăn chặn hoàn toàn rủi ro phát sinh cước ngoài ý muốn.

---

## 1. BẢNG TỔNG HỢP CHI PHÍ CÁC THÀNH PHẦN

| Thành phần | Dịch vụ được chọn | Cấu hình & Tài nguyên | Giới hạn Free Tier | Mức tiêu thụ thực tế của GARI | Chi phí hàng tháng |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Frontend & Gateway** | **Vercel Hobby** | Edge Proxy, Static Assets, Global CDN | 100 GB Bandwidth / tháng<br>100k Function executions | ~1.5 GB Bandwidth / tháng<br>~12,000 requests | **0.00 USD** |
| **Backend & AI Inference** | **Hugging Face Spaces** | Docker Container CPU Basic | 2 vCPU, 16 GB RAM<br>50 GB Storage, Free HTTPS | 1.76 GB RAM đỉnh (11%)<br>5.04 GB Disk models | **0.00 USD** |
| **Cơ sở dữ liệu** | **Neon Serverless PostgreSQL** | Cloud Postgres v16, Scale-to-Zero | 1 GB Storage<br>100 Compute Unit-hours | 9.2 MB Storage (< 1%)<br>~8.5 CU-hours / tháng | **0.00 USD** |
| **Keep-Alive Uptime** | **cron-job.org** | HTTP Periodic Ping | Unlimited jobs, 1-min interval | 1 job ping mỗi 30 phút (~1,440 pings/mo) | **0.00 USD** |
| **Bảo mật & Chứng chỉ SSL** | **Let's Encrypt / Cloudflare** | Tự động gia hạn SSL wildcard | Không giới hạn | 100% tự động | **0.00 USD** |
| **TỔNG CỘNG** | | | | | **0.00 USD / tháng** |

---

## 2. PHÂN TÍCH CHI TIẾT TỪNG DỊCH VỤ

### 2.1. Frontend & API Gateway (Vercel Hobby Tier)
- **Hạn mức miễn phí:**
  - Băng thông ra (Fast Data Transfer): 100 GB / tháng.
  - Số lần gọi Function: 100,000 lần / tháng.
  - Thời gian chạy Function: 100 GB-hours.
- **Tiêu thụ của GARI:**
  - Frontend2 được build tĩnh (Vite React), các tài nguyên JS/CSS/Assets có tổng kích thước ~4.2 MB và được cache toàn cầu trên Edge CDN.
  - API proxy (`/api/[...path].js`) chỉ đóng vai trò forward header và body giữa client và Hugging Face Space.
  - Với 3,000 lượt chẩn đoán ảnh/tháng (mỗi ảnh tải lên trung bình ~400 KB), băng thông tiêu tốn xấp xỉ: $3000 \times 400\text{ KB} \approx 1.2\text{ GB} \ll 100\text{ GB}$.
- **Rủi ro vượt ngưỡng:** Gần như bằng 0.

### 2.2. AI Inference Engine & Backend (Hugging Face Spaces)
- **Hạn mức miễn phí:**
  - 100% miễn phí vĩnh viễn cho cấu hình **CPU Basic**.
  - Phần cứng: 2 vCPU, **16 GB RAM hệ thống**, 50 GB dung lượng ổ đĩa.
  - **Không yêu cầu nhập thẻ tín dụng** để khởi tạo Space CPU Basic.
- **Tiêu thụ của GARI:**
  - Benchmark thực tế trên 51 models với cơ chế LRU Cache (giữ tối đa 5 mô hình trên bộ nhớ cùng Global ViT Router):
    - RAM hệ điều hành & Python: ~338 MB.
    - RAM khi nạp 5 mô hình PyTorch ConvNeXt-Small: ~1,408 MB.
    - RAM đỉnh điểm khi chạy suy luận song song: **1,766 MB (~1.76 GB)**.
  - Tỷ lệ chiếm dụng RAM: $1.76\text{ GB} / 16\text{ GB} = \mathbf{11\%}$.
  - Hugging Face Spaces hoàn toàn không bị tràn RAM (OOM), hoạt động ổn định và bền vững.
- **Cơ chế bảo vệ chi phí:** Hugging Face không tự động nâng cấp phần cứng. Nếu muốn phần cứng GPU/RAM cao hơn, người dùng bắt buộc phải vào cài đặt và chủ động thanh toán. Do đó, tài khoản **không thể bị trừ tiền ngoài ý muốn**.

### 2.3. Cơ sở dữ liệu bền vững (Neon Serverless PostgreSQL)
- **Hạn mức miễn phí:**
  - Lưu trữ: **1.0 GB dữ liệu**.
  - Năng lực tính toán: **100 Compute Unit (CU) hours / tháng**.
  - Tính năng Scale-to-Zero: Tự động đưa compute về trạng thái ngủ sau 5 phút không hoạt động để tiết kiệm CU. Thời gian đánh thức chỉ mất ~500ms.
- **Tiêu thụ của GARI:**
  - SQLite hiện tại có 83 bảng với tổng cộng 34,088 dòng dữ liệu $\rightarrow$ Dung lượng thực tế là **9.2 MB**.
  - Tỷ lệ chiếm dụng ổ đĩa: $9.2\text{ MB} / 1024\text{ MB} = \mathbf{0.89\%}$ (dư hơn 99% dung lượng cho dữ liệu phát sinh trong tương lai).
  - Với lượng truy cập nông trại thông thường kết hợp cron-job ping mỗi 30 phút, lượng compute tiêu hao ước tính chỉ khoảng 8.5 đến 12 CU-hours / tháng, nằm sâu bên dưới hạn mức 100 CU-hours.
- **So sánh với Supabase Free Tier:**
  - Supabase có nhược điểm chí mạng: tự động tạm dừng (pause) toàn bộ dự án nếu không có truy cập trong 7 ngày liên tục và phải vào dashboard kích hoạt lại thủ công.
  - Neon **không xóa hay pause dự án**, compute tự động thức dậy ngay khi có truy vấn SQL đầu tiên (cold start ~500ms).

### 2.4. Trực ban & Giữ nhiệt hệ thống (cron-job.org)
- Dịch vụ hoàn toàn miễn phí, độc lập.
- Gửi 1 request GET nhẹ nhàng vào endpoint `/health` mỗi 30 phút để giữ cho container Hugging Face luôn sẵn sàng phục vụ người nông dân tức thì mà không cần đợi nạp container.

---

## 3. SO SÁNH VỚI KIẾN TRÚC ĐÁM MÂY THƯƠNG MẠI TRẢ PHÍ

Nếu sử dụng các nhà cung cấp đám mây phổ thông, chi phí tối thiểu hàng tháng của GARI sẽ như sau:

| Dịch vụ / Nền tảng | Cấu hình tương đương | Chi phí tối thiểu hàng tháng | Chi phí hàng năm |
| :--- | :--- | :--- | :--- |
| **AWS (Amazon Web Services)** | EC2 `t4g.xlarge` (16GB RAM) + RDS Postgres `db.t4g.micro` | **$85.50 / tháng** | **$1,026.00 / năm** |
| **GCP (Google Cloud Platform)** | Compute Engine `e2-standard-4` (16GB RAM) + Cloud SQL | **$96.80 / tháng** | **$1,161.60 / năm** |
| **DigitalOcean / Linode** | Droplet Memory-Optimized (16GB RAM) + Managed DB | **$84.00 / tháng** | **$1,008.00 / năm** |
| **Render.com (Paid Tier)** | Standard Instance (4GB RAM) + Render Postgres | **$32.00 / tháng** | **$384.00 / năm** |
| **GARI Zero-Cost Stack** | **HF Spaces (16GB RAM) + Neon Postgres (1GB) + Vercel** | **$0.00 / tháng** | **$0.00 / năm** |

> [!TIP]
> **Khoản tiền tiết kiệm thực tế:** Dự án tiết kiệm từ **$384 đến $1,160 USD mỗi năm** (~9.5 đến 29 triệu VNĐ/năm) mà vẫn đảm bảo độ tin cậy, an toàn dữ liệu và hiệu năng suy luận AI đỉnh cao.

---

## 4. BẢO ĐẢM KHÔNG BAO GIỜ PHÁT SINH CƯỚC (ZERO INADVERTENT BILLING GUARANTEE)

1. **Không liên kết thẻ thanh toán:**
   - Cả 3 nền tảng chính (Hugging Face, Neon, Vercel) đều cho phép tạo tài khoản và kích hoạt gói Free Tier mà **không bắt buộc nhập thẻ Visa/MasterCard**.
   - Việc không lưu thông tin thẻ đồng nghĩa với việc về mặt toán học và vật lý, nhà cung cấp không thể tự động trừ tiền.
2. **Cơ chế Hard-Cap:**
   - Nếu chạm ngưỡng tối đa của gói miễn phí, hệ thống sẽ tự động giới hạn (rate-limit hoặc sleep) chứ không tự động nâng cấp gói trả phí.
3. **Cơ chế sao lưu dữ liệu tự trị:**
   - Dữ liệu luôn được sao lưu về bản sao SQLite cục bộ qua script `tools/migrate_sqlite_to_postgres.py --rollback`, đảm bảo không bao giờ bị khóa dữ liệu (vendor lock-in).

