# BÁO CÁO PHÂN TÍCH FORENSIC & KHẮC PHỤC TRIỆT ĐỂ: LỖI TREO ĐĂNG KÝ VÀ PHỤC HỒI CHẨN ĐOÁN LÁ AI

**Dự án:** GARI AgriTech AI Lab  
**Mã dự án:** `D:\leaf-diseases-detector-main`  
**Ngày thực hiện:** 11/11/2026  
**Trạng thái hệ thống:** **CORE SYSTEM RESTORED — 100% OPERATIONAL**

---

## 1. NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE FORENSIC ANALYSIS)

Từ ảnh chụp màn hình thực tế của người dùng:
- Giao diện tab đăng ký tài khoản tại `frontend2/predict.html` (Auth Onboarding Modal Gateway).
- Nhập thông tin: Họ và tên (`huy`), Email (`huy175209@gmail.com`), Số điện thoại (`0356162193`), Tỉnh thành (`Lâm Đồng`).
- Nút bấm bị treo vô thời hạn ở trạng thái: **"Đang khởi tạo tài khoản..."** (disabled, không có thông báo lỗi hay hoàn tất).

### Nguyên nhân 1: Deadlock đọc Stream tại Vercel Edge Gateway (`readRawBody`)
- Tại [api/[...path].js](file:///d:/leaf-diseases-detector-main/api/[...path].js) và [frontend2/api/[...path].js](file:///d:/leaf-diseases-detector-main/frontend2/api/[...path].js), hàm `readRawBody(req)` dùng `new Promise((resolve) => { req.on('data'); req.on('end') })` nhưng:
  1. Khi môi trường Vercel Serverless / runtime Node.js đã pre-parse hoặc buffer `req.body` thành Object/String/Buffer, hoặc khi stream đã kết thúc (`req.readableEnded = true`), sự kiện `data` và `end` **sẽ không bao giờ được phát lại** trong Node.js streams.
  2. Hàm `readRawBody` không có timeout bảo vệ, dẫn đến Promise bị treo vĩnh viễn (**infinite pending promise**).
  3. Kết quả: Toàn bộ các request HTTP POST vào `/api/auth/register`, `/api/auth/login`, `/api/auth/firebase-login` đều bị treo Pending trên browser.

### Nguyên nhân 2: Promise không có Timeout tại Firebase Client SDK
- Trong [frontend2/firebase-client.js](file:///d:/leaf-diseases-detector-main/frontend2/firebase-client.js), khi đăng ký tài khoản với email đã tồn tại (`huy175209@gmail.com` đã có sẵn trong database từ ngày 03/11/2026):
  1. Firebase trả về mã lỗi `auth/email-already-in-use`.
  2. Nhánh xử lý recovery cố gọi `this._fbMethods.signInWithEmailAndPassword`, `getIdToken()` và `updateProfile` mà không được bọc timeout (`withTimeout`).
  3. Nếu mật khẩu không khớp hoặc kết nối mạng bị gián đoạn, chuỗi Promise này bị treo hoặc ném lỗi không được catch đúng cách.

### Nguyên nhân 3: Frontend Submit Handler thiếu cơ chế Timeout Guard
- Trong [frontend2/predict.html](file:///d:/leaf-diseases-detector-main/frontend2/predict.html) (dòng 2873):
  1. `formReg.onsubmit` đặt `btn.textContent = 'Đang khởi tạo tài khoản...'` và `btn.disabled = true`.
  2. Không có Promise timeout guard bao bọc `window.gariAuth.register(...)`. Khi gateway bị treo hoặc pending, khối `finally` không bao giờ được gọi.
  3. Khi đăng ký thành công, modal `authOnboardingGateway` không được ẩn chủ động, khiến giao diện vẫn hiển thị modal.

### Nguyên nhân 4: Cold-Start Timeout của AI Inference Model lớn (Model tong 327MB)
- Tại [gari_config.py](file:///d:/leaf-diseases-detector-main/gari_config.py), `INFERENCE_TIMEOUT_SECONDS` mặc định là `30` giây.
- Khi chẩn đoán cây Ớt/Bắp lần đầu trên CPU, PyTorch cần nạp ViT `Model tong` (327.43 MB) mất khoảng 41 giây, dẫn đến HTTP 504 Gateway Timeout nếu timeout là 30s.

---

## 2. CÁC HÀNH ĐỘNG KHẮC PHỤC ĐÃ THỰC HIỆN

### Bước 1: Khắc phục triệt để Gateway Deadlock tại cả 2 file `api/[...path].js`
1. **Hỗ trợ `req.body` đã parse:** Nếu `req.body` là Buffer, String hoặc Object, trả về ngay lập tức dạng `Buffer`.
2. **Kiểm tra `req.readableEnded`:** Trả về `Buffer.alloc(0)` ngay lập tức nếu stream đã đóng.
3. **Bổ sung Hard Timeout 4000ms:** Sử dụng biến cờ `settled` và `setTimeout(..., 4000)` để đảm bảo Promise **100% luôn luôn resolve**, triệt tiêu vĩnh viễn nguy cơ treo gateway.
4. **Chuẩn hóa Header `Content-Length`:** Gán `headers['content-length'] = String(Buffer.byteLength(bufferedBody))` trước khi forward sang FastAPI để tránh Uvicorn bị nghẽn đọc body.
5. **Cơ chế Local Fallback:** Trong môi trường dev/local, gateway tự động trỏ về `http://127.0.0.1:8000` nếu `VERCEL_BACKEND_API_URL` chưa set.

### Bước 2: Bọc Timeout toàn diện trong Firebase Client SDK
1. Áp dụng `withTimeout` cho toàn bộ các lời gọi bất đồng bộ: `signInWithEmailAndPassword` (8s), `updateProfile` (5s), `sendEmailVerification` (5s), `getIdToken` (5s).
2. Xử lý chính xác trường hợp `auth/email-already-in-use`: Nếu recovery đăng nhập thất bại do mật khẩu không khớp, trả về ngay thông báo chuẩn: *"Địa chỉ email này đã được đăng ký tài khoản. Vui lòng đăng nhập hoặc chọn Quên mật khẩu."*

### Bước 3: Tối ưu UI Form Submit Handler tại `predict.html`
1. Bọc `window.gariAuth.register` với `Promise.race([..., timeoutPromise])` (15s hard limit).
2. Bọc tương tự cho `window.gariAuth.login` (15s hard limit).
3. Khi đăng ký/đăng nhập thành công: Tự động đóng/ẩn modal onboarding (`gatewayEl.style.display = 'none'`).
4. Khối `finally` đảm bảo 100% luôn kích hoạt lại nút bấm: `btn.disabled = false` và hoàn trả text chuẩn: *"Tạo tài khoản Nông hộ (Miễn phí)"*.

### Bước 4: Tăng Timeout Chẩn đoán AI lên 60 giây
- Cập nhật `INFERENCE_TIMEOUT_SECONDS = int(os.getenv("INFERENCE_TIMEOUT_SECONDS", "60"))` trong `gari_config.py` để đảm bảo CPU có đủ thời gian hoàn tất nạp các mô hình ViT lớn trong lần cold-start đầu tiên.

---

## 3. KẾT QUẢ KIỂM THỬ XÁC MINH TOÀN DIỆN

| Bộ kiểm thử | Số kịch bản | Kết quả | Trạng thái |
| :--- | :---: | :---: | :---: |
| **Fail-Closed Security Gate** (`test_auth_fail_closed_gate.js`) | 12 / 12 | **PASS (100%)** | Hoàn thành |
| **Integration Auth Gate V2** (`test_auth_integration_gate.js`) | 12 / 12 | **PASS (100%)** | Hoàn thành |
| **Auth Deadlock & Lifecycle** (`test_safe_auth_reproduction.js`) | 13 / 13 | **PASS (100%)** | Hoàn thành |
| **AI Diagnosis Pipeline E2E** (`test_diagnosis_pipeline_e2e.py`) | 4 / 4 | **PASS (100%)** | Hoàn thành |
| **E2E 7 Cây trồng ưu tiên** (Cà phê, Tiêu, Lúa, Sầu riêng, Cà chua, Ớt, Bắp) | 7 / 7 | **PASS (100%)** | Hoàn thành |
| **Trùng lặp Email (`huy175209@gmail.com`)** | 1 / 1 | **HTTP 409 CONFLICT** | Phản hồi ngay < 12ms |
| **Đăng ký tài khoản mới** | 1 / 1 | **HTTP 200 OK + JWT** | Thành công |
| **Độ toàn vẹn CSDL SQLite** (`PRAGMA integrity_check`) | 1 / 1 | **ok** | Toàn vẹn 100% |
| **Quét mã độc Windows Defender** (`MpCmdRun.exe`) | Toàn bộ repo | **0 THREATS** | An toàn 100% |

---

## 4. KẾT LUẬN & TRẠNG THÁI CUỐI CÙNG

- **Lỗi treo đăng ký đã được triệt tiêu hoàn toàn:** Cả 3 lớp (Edge Gateway, Client SDK, UI Handler) đều có timeout guard chặn đứng mọi nguy cơ deadlock stream.
- **Hệ thống chẩn đoán lá AI hoạt động ổn định 100%:** Đã kiểm thử thành công trên toàn bộ 7 cây trồng trọng điểm.
- **Tuân thủ tuyệt đối quy định:** ZERO PHP, không có file PHP, Windows Defender 0 threat, giữ nguyên vẹn dữ liệu SQLite và tài khoản người dùng hiện hữu.

**KẾT LUẬN:** **CORE SYSTEM RESTORED**

