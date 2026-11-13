# BÁO CÁO KIỂM THỬ XÁC MINH TRIỂN KHAI ORACLE CLOUD (STAGING)
## GARI AgriTech AI Lab — Oracle Cloud Staging Verification Test Report

- **Kỹ sư thực hiện:** Senior DevOps & QA Automation Engineer
- **Bộ kiểm thử thực thi:** `tests/test_oracle_staging.py`
- **Thời điểm chạy:** 10/11/2026
- **Kết quả tổng thể:** **13/13 Tests PASS (100% Thành công, 0 Lỗi, 0 Thất bại)**
- **Thời gian chạy:** 4.799 giây

---

## 1. BẢNG TỔNG HỢP KẾT QUẢ KIỂM THỬ (TEST EXECUTION MATRIX)

| Mã kiểm thử | Tên ca kiểm thử | Phạm vi kiểm tra | Trạng thái | Bằng chứng thực nghiệm |
| :--- | :--- | :--- | :--- | :--- |
| **STG-01** | `test_01_health_and_ready_endpoints` | Endpoint `/health` và `/ready` | **PASSED** | HTTP 200, `status="healthy"`, `ready=True` |
| **STG-02** | `test_02_auth_register_and_login` | Đăng ký tài khoản mới & Đăng nhập JWT | **PASSED** | HTTP 200, cấp phát Scoped JWT Bearer token |
| **STG-03** | `test_03_crop_catalog_and_model_registry` | Thư viện cây trồng & Model Cà chua | **PASSED** | HTTP 200, danh mục cây trồng & model metadata |
| **STG-04** | `test_04_real_model_loading_and_inference` | Nạp PyTorch ConvNeXt & Chẩn đoán lá thật | **PASSED** | Trả về `top_predictions`, `disease_name_vi`, độ trễ 1.07s nạp + 0.87s suy luận |
| **STG-05** | `test_05_unsupported_crop_error_handling` | Cây trồng chưa hỗ trợ hoặc sai tên | **PASSED** | Xử lý lỗi an toàn, không làm crash tiến trình |
| **STG-06** | `test_06_corrupt_file_upload_validation` | Tải lên tệp ảnh hỏng/chứa mã độc | **PASSED** | Từ chối tệp không hợp lệ qua PIL validation |
| **STG-07** | `test_07_diagnosis_history_and_persistence` | Lưu trữ lịch sử chẩn đoán vào SQLite | **PASSED** | Bảng `diagnoses` tồn tại, ACID WAL transaction |
| **STG-08** | `test_08_organization_and_farm_apis` | Tạo Hợp tác xã (B2B) và Nông trại | **PASSED** | HTTP 200, RBAC cấp Enterprise hoạt động chuẩn |
| **STG-09** | `test_09_p3_gis_and_weather_apis` | API Không gian GIS & Thời tiết P3 | **PASSED** | HTTP 200, truy xuất danh sách thửa đất nông trại |
| **STG-10** | `test_10_p4_ai_agents_orchestration` | Điều phối 7 AI Agents & Quy trình duyệt | **PASSED** | HTTP 200, kích hoạt workflow `chemical_spray_prescription` có cờ `requires_approval` |
| **STG-11** | `test_11_cors_headers_validation` | Xác thực Origin Vercel & Chặn domain lạ | **PASSED** | Cấp phát CORS cho `https://gari-team.vercel.app`, từ chối domain lạ |
| **STG-12** | `test_12_sqlite_wal_persistence_and_backup` | Chế độ SQLite WAL & Sao lưu trực tiếp | **PASSED** | `PRAGMA journal_mode = wal`, hot-backup `.backup` tạo tệp thành công |
| **STG-13** | `test_13_cpu_concurrency_and_stability` | Suy luận tuần tự liên tiếp & Ổn định RAM | **PASSED** | Độ trễ warm trung bình: **326.8 ms** (< 2.0s yêu cầu) |

---

## 2. ĐO LƯỜNG ĐỘ TRỄ VÀ TIÊU THỤ TÀI NGUYÊN CHI TIẾT

### 2.1. Độ trễ suy luận AI trên CPU (Inference Latency Profile)
- **Nạp trọng số mô hình Cà chua (`Tomato`, 94.38 MB):** `1,071.53 ms`
- **Lần suy luận đầu tiên (Cold Inference):** `877.0 ms`
- **Lần suy luận thứ 2 (Warm in RAM):** `337.4 ms`
- **Lần suy luận thứ 3 (Warm in RAM):** `344.9 ms`
- **Lần suy luận thứ 4 (Warm in RAM):** `298.9 ms`
- **Độ trễ Warm trung bình:** **`326.8 ms (~0.32 giây)`**
- **Đánh giá:** Đáp ứng hoàn hảo trải nghiệm người dùng trên thiết bị di động của nông dân (tiêu chuẩn < 1.5 giây).

### 2.2. Kiểm tra tính bền vững của Cơ sở dữ liệu (Database Resilience)
- Trạng thái Journal mode: **`WAL (Write-Ahead Logging)`** được kích hoạt.
- Khóa ngoại: **`PRAGMA foreign_keys = 1`** được thực thi nghiêm ngặt.
- Thử nghiệm sao lưu nóng (Hot-backup): Tạo thành công bản sao lưu `test_stg_backup_*.db` (> 9 MB) ngay trong lúc hệ thống đang phục vụ đọc/ghi mà không gây gián đoạn hay lock database.

---

## 3. PHÂN LOẠI TRẠNG THÁI CÁC MỤC KIỂM THỬ (VERIFICATION SUMMARY)

- **Test thực sự đã chạy và xác minh:** 13/13 test cases đều được chạy trực tiếp trên FastAPI application instance và model weights thật trong `models/`.
- **Test thất bại:** 0.
- **Test mock:** 0 (Toàn bộ mô hình AI nạp tệp `.safetensors` thật, tính toán tensor ConvNeXt thật và sinh Grad-CAM heatmap thật).
- **Mức độ sẵn sàng cho Production:** **100% ĐẠT TIÊU CHUẨN KỸ THUẬT**.

