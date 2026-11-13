# KIẾN TRÚC HOSTING 0 ĐỒNG / THÁNG — GARI AGRI-TECH AI LAB
## GARI Zero-Cost Cloud Infrastructure Architecture Blueprint

- **Tác giả:** Ban Kiến trúc Đám mây & DevSecOps GARI
- **Thời điểm ban hành:** 10/11/2026
- **Chi phí vận hành:** **0 USD / tháng (Cam kết 100% Zero-Cost vĩnh viễn)**
- **Mục tiêu:** Chấm dứt sự phụ thuộc vào máy trạm cá nhân và đường hầm tạm thời Cloudflare Quick Tunnel mà không làm mất dữ liệu, không làm sập giao diện, không phát sinh chi phí ẩn.

---

## 1. TỔNG QUAN KIẾN TRÚC 0 ĐỒNG (ARCHITECTURE OVERVIEW)

Dự án GARI AgriTech AI Lab sở hữu đặc thù kỹ thuật gồm hai nhóm tải trọng trái ngược:
1. **Nhóm dịch vụ nhẹ (Lightweight Services):** Xác thực JWT, Quản trị tổ chức đa khách thuê, Quản lý nông trại, Lập lịch mùa vụ, Điều phối 7 AI Agents, Mạng lưới chuyên gia. Yêu cầu độ trễ thấp, kết nối cơ sở dữ liệu bền vững.
2. **Nhóm dịch vụ nặng (Heavy AI Services):** 51 mô hình deep learning PyTorch (5.04 GB weights trên đĩa), Vision Transformer (`Model tong`, 327MB), ConvNeXt (`Tomato`, `Rice`, `Maize`... 94MB/mô hình), bản đồ nhiệt Grad-CAM, xử lý ảnh viễn thám Sentinel-2. Yêu cầu **RAM tối thiểu 1.5GB – 2GB** khi chạy suy luận.

### Sơ Đồ Kiến Trúc Phân Tách 0 Đồng (Decoupled Zero-Cost Architecture)

```
[Người Dùng / Mobile / Web Browser]
                 |
                 v
+---------------------------------------------------------------------------------------------------+
| 1. FRONTEND & REVERSE GATEWAY: Vercel Hobby (0 USD/tháng)                                         |
|    - Địa chỉ: https://gari-team.vercel.app/frontend2                                              |
|    - Phục vụ tĩnh: HTML5 SaaS Shell, CSS Motion, Icons, Logic phân quyền                          |
|    - Edge Proxy: api/[...path].js chuyển tiếp request /api/* với timeout 90 giây                 |
|    - Dự phòng: Edge Auth cục bộ nếu backend đang thức giấc sau chế độ ngủ (Cold-Start)           |
+---------------------------------------------------------------------------------------------------+
                 |
                 | (HTTPS JSON / Multipart Form-Data)
                 v
+---------------------------------------------------------------------------------------------------+
| 2. AI BACKEND & INFERENCE RUNTIME: Hugging Face Spaces CPU Basic (0 USD/tháng)                   |
|    - Tài nguyên: 2 vCPU | 16 GB RAM | 50 GB Disk (Miễn phí vĩnh viễn không cần thẻ tín dụng)     |
|    - Môi trường: Docker Container (Python 3.11, PyTorch CPU, FastAPI, Uvicorn port 7860)         |
|    - Quản lý bộ nhớ: LRU Cache (giới hạn 3-4 mô hình nạp RAM đồng thời, Peak RAM ~1.76 GB)      |
|    - Kho mô hình: 5.04 GB weights nạp an toàn qua Git LFS không giới hạn băng thông             |
|    - Cơ chế giữ ấm: Webhook ping định kỳ 30 phút (cron-job.org) chống Sleep State 48h             |
+---------------------------------------------------------------------------------------------------+
                 |
                 | (TLS / SSL Connection Pool)
                 v
+---------------------------------------------------------------------------------------------------+
| 3. PERSISTENT MANAGED DATABASE: Neon Serverless PostgreSQL Free (0 USD/tháng)                     |
|    - Dung lượng: 1 GB SSD NVMe (Dữ liệu GARI hiện tại: 9.2 MB ~ 0.9% hạn mức)                     |
|    - Compute: 100 CU-hours/tháng (Autoscale 0.25 - 2 CU, scale-to-zero sau 5 phút nhàn rỗi)      |
|    - Độ tin cậy: Không bị pause sau 7 ngày như Supabase, tự động thức giấc trong 500ms           |
|    - Schema: 83 bảng quan hệ, toàn vẹn khóa ngoại, định danh người dùng và lịch sử chẩn đoán     |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. MA TRẬN ĐÁNH GIÁ CÁC NỀN TẢNG FREE TIER HIỆN TẠI (BENCHMARK)

Chúng tôi đã tiến hành khảo sát tài liệu chính thức và đo lường thực tế trên mã nguồn GARI:

| Nhà cung cấp | Dịch vụ & Cấu hình Free | Giới hạn RAM | Tương thích PyTorch GARI | Chi phí vượt hạn mức | Kết luận |
|---|---|---|---|---|---|
| **Hugging Face Spaces** | CPU Basic (2 vCPU) | **16 GB RAM** | **Tương thích 100% (Sử dụng 10.8% RAM)** | $0 (Không có cơ chế tự trừ tiền) | **CHỌN LÀM BACKEND AI** |
| **Render** | Free Web Service | 512 MB RAM | **KHÔNG THỂ CHẠY (Bị SIGKILL OOM tức thì)** | Tạm ngưng dịch vụ | Loại bỏ cho AI backend |
| **Google Cloud Run** | Free tier (2M req/mo) | 1-2 GB RAM | Tương thích nhưng bắt buộc thẻ tín dụng | Tự động tính tiền nếu bị spam | Rủi ro phát sinh chi phí |
| **Neon** | Serverless Postgres | N/A (1 GB DB) | **Tương thích 100% (83 bảng SQLite -> Postgres)**| Chặn ghi khi quá 1GB ($0 phạt) | **CHỌN LÀM DATABASE** |
| **Supabase** | Free Tier (500MB DB) | N/A (500 MB) | Tương thích nhưng **bị pause sau 7 ngày** | Phải khôi phục thủ công | Dự phòng cấp 2 |
| **Vercel** | Hobby Tier | Edge CDN | Tương thích 100% với Frontend2 | $0 (Chặn khi vượt 100GB) | **GIỮ NGUYÊN FRONTEND** |

### Bằng Chứng Thực Nghiệm Bộ Nhớ (Empirical Memory Benchmark)
Kết quả đo lường thực tế qua công cụ `tools/benchmark_zero_cost_inference.py`:
- Bộ nhớ RAM khởi động FastAPI và Registry: **338.8 MB**
- Khi nạp 5 mô hình cây trồng (`Tomato`, `Rice`, `Maize`, `Coffee`, `Black_Pepper`): **1,407.5 MB**
- Khi nạp thêm mô hình toàn cầu Vision Transformer (`Model tong`): **1,766.6 MB (Peak RAM)**
- **Kết luận:** Giới hạn 512 MB của Render Free hoặc 256 MB của micro-container là hoàn toàn bất khả thi cho deep learning. **Hugging Face Spaces với 16 GB RAM là giải pháp 0 đồng duy nhất trên thị trường vận hành ổn định hệ thống AI của GARI.**

---

## 3. PHÂN LOẠI TẢI TRỌNG HỆ THỐNG (WORKLOAD SEGREGATION)

### 3.1. Nhóm Dịch Vụ Nhẹ (Lightweight Services)
- **Tài nguyên tiêu thụ:** RAM ~120MB, CPU < 5%, băng thông ~2-5KB/request.
- **Thành phần:**
  - `gari_auth.py`: Đăng ký, đăng nhập Bcrypt, ký Scoped JWT.
  - `gari_b2b.py`: Quản trị tổ chức, phân quyền thành viên (RBAC).
  - `gari_farm_management.py`: Nông trại, khu vực, thửa đất.
  - `gari_tasks.py`: Nhiệm vụ mùa vụ, lịch canh tác.
  - `gari_agent_orchestrator.py`: Điều phối luồng làm việc của 7 Agent.
- **Hành vi trên Free Tier:** Đáp ứng tức thì (< 35ms), không gây áp lực tài nguyên.

### 3.2. Nhóm Dịch Vụ Nặng (Heavy AI Services)
- **Tài nguyên tiêu thụ:** RAM ~250MB/model, CPU 80-100% trong 350ms suy luận.
- **Thành phần:**
  - `gari_inference_engine.py`: Nạp trọng số `.safetensors` và suy luận ConvNeXt/ViT.
  - `gari_visual_localization.py`: Tính toán bản đồ kích hoạt lớp Grad-CAM và bounding boxes.
- **Biện pháp tối ưu hóa:**
  1. **LRU Model Eviction:** Thiết lập `MAX_CACHED_MODELS=3`. Chỉ lưu tối đa 3 mô hình cây trồng gần nhất trên RAM. Khi có yêu cầu cây trồng thứ tư, mô hình ít dùng nhất được giải phóng bằng `del self.cache[oldest_id]` và thu gom rác bộ nhớ.
  2. **Lazy Loading:** Mô hình chỉ được nạp vào bộ nhớ khi có người dùng gửi ảnh yêu cầu chẩn đoán cây trồng đó.
  3. **Concurrency Limiter:** Giới hạn xử lý tối đa 2 request chẩn đoán đồng thời trên CPU để chống nghẽn hàng đợi.

---

## 4. CHIẾN LƯỢC TOÀN VẸN CƠ SỞ DỮ LIỆU (DATABASE PERSISTENCE)

Hugging Face Spaces hoạt động trên hệ thống tệp cục bộ tạm thời (Ephemeral Filesystem). Nếu lưu `disease_detector.db` trực tiếp trong container, dữ liệu mới sẽ biến mất khi Space khởi động lại.

**Giải pháp triệt để 0 đồng:**
- Di chuyển toàn bộ dữ liệu nghiệp vụ sang **Neon Serverless PostgreSQL**.
- Cơ sở dữ liệu nằm độc lập bên ngoài container, được bảo vệ bằng SSL/TLS.
- Khi Space bị khởi động lại, nâng cấp mã nguồn, hoặc rơi vào trạng thái ngủ: **100% tài khoản người dùng, nông trại, hồ sơ bệnh và nhật ký Agent được bảo toàn nguyên vẹn.**
- Bộ chuyển đổi `tools/migrate_sqlite_to_postgres.py` đảm bảo chuyển giao toàn bộ 83 bảng dữ liệu mà không làm thay đổi ID hay phá vỡ khóa ngoại.

---

## 5. CƠ CHẾ XỬ LÝ TRẠNG THÁI NGỦ VÀ KHỞI ĐỘNG NGUỘI (COLD-START RESILIENCE)

- **Đặc điểm Free Tier:** Hugging Face Spaces chuyển sang trạng thái ngủ (Sleep State) sau 48 giờ không có lượt truy cập (hoặc sau ~1 giờ nhàn rỗi).
- **Thời gian khởi động nguội (Cold Start):** ~30 đến 45 giây để container boot và khởi tạo FastAPI.
- **Cơ chế chịu lỗi 3 tầng của GARI:**
  1. **Tầng 1 — Timeout mở rộng tại Vercel Proxy:** File `api/[...path].js` được cấu hình `VERCEL_BACKEND_TIMEOUT_MS = 90000` (90 giây). Khi người dùng gửi request lúc server đang ngủ, Vercel kiên nhẫn chờ container thức giấc thay vì ngắt kết nối ngay lập tức.
  2. **Tầng 2 — Fallback Edge Authentication:** Nếu backend đang trong quá trình boot, các thao tác đăng nhập, đăng ký và đọc trạng thái sức khỏe `/health` được xử lý tạm thời trực tiếp tại Vercel Edge Serverless, người dùng không bao giờ thấy màn hình trắng hoặc lỗi 502.
  3. **Tầng 3 — Free Uptime Pinger (Tùy chọn):** Sử dụng dịch vụ miễn phí `cron-job.org` gửi một HTTP GET request vào `/ready` mỗi 30 phút. Không gian Hugging Face Space duy trì trạng thái thức 24/7 hoàn toàn **0 USD**.

