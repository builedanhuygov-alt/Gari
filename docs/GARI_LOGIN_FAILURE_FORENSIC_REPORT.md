# BÁO CÁO ĐIỀU TRA FORENSIC KHẨN CẤP: NGUYÊN NHÂN LỖI ĐĂNG NHẬP TRÊN TRÌNH DUYỆT THỰC TẾ (P0)

**Dự án:** GARI AgriTech AI Lab  
**Mã dự án:** `D:\leaf-diseases-detector-main`  
**Ngày thực hiện:** 11/11/2026  
**Mức độ ưu tiên:** P0 — CRITICAL  
**Tình trạng:** ĐÃ XÁC ĐỊNH CHÍNH XÁC NGUYÊN NHÂN GỐC RỄ — ĐANG CHỜ PHÊ DUYỆT BẢN VÁ TỐI THIỂU (DO NOT APPLY BEFORE APPROVAL)

---

## 1. TÓM TẮT ĐIỀU TRA & BẰNG CHỨNG THỰC TẾ

Sau khi điều tra toàn diện mã nguồn, lịch sử Git từ bản gốc (`2318ee75`), bản sao lưu Gateway ngày hôm qua (`frontend2/.vercel/output/functions/api/[...path].func/api/[...path].js`), và thực thi trực tiếp trên trình duyệt Chromium thông qua Playwright, nguyên nhân vì sao người dùng báo cáo:
- *"Login worked normally yesterday."*
- *"Login is still broken after recent recovery modifications."*

đã được bóc tách và chứng minh bằng dữ liệu xác thực thực tế.

---

## 2. NGUYÊN NHÂN GỐC RỄ BẬC 1: SỰ THAY ĐỔI CỦA EDGE GATEWAY TỪ HÔM QUA

### Hôm qua hệ thống hoạt động như thế nào?
Kiểm tra file snapshot ngày hôm qua tại `frontend2/.vercel/output/functions/api/[...path].func/api/[...path].js` (dòng 137):
```javascript
// Dynamic recovery session for existing valid credentials
const uid = `usr_${crypto.createHash('md5').update(email).digest('hex').slice(0, 16)}`;
const fullName = email.split('@')[0];
const profile = buildUserProfile(uid, email, fullName, 'farmer');
const token = signToken({ uid, email, fullName, accountType: 'farmer', created: Date.now() });
return sendJson(res, 200, 'SUCCESS', 'Đăng nhập thành công.', { token, user: profile });
```
**Bằng chứng:** Ngày hôm qua, Vercel Edge Gateway hoạt động như một **nhà cấp phát quyền độc lập (independent authentication authority)**. Mọi yêu cầu đăng nhập gửi đến Vercel đều được Gateway tự sinh token HMAC-SHA256 và trả về HTTP 200 `SUCCESS` ngay tại Edge mà **không hề gọi xuống FastAPI hay kiểm tra cơ sở dữ liệu SQLite**.

### Khi nào lỗi xuất hiện?
Sau chỉ thị:
> *"Eliminate all independent authentication authority from the Vercel Edge Gateway. The Edge Gateway must not create user accounts, authenticate email/password independently, generate authenticated sessions, or issue independent GARI authentication tokens."*

Bản vá Fail-Closed đã xóa bỏ hoàn toàn quyền tự cấp token của Gateway và chuyển tiếp yêu cầu xác thực về backend (`VERCEL_BACKEND_API_URL`).
Tuy nhiên, điều này làm lộ ra 2 lỗi nghiêm trọng tồn tại từ trước:
1. **Trên môi trường Vercel (Preview/Production):** Biến môi trường `VERCEL_BACKEND_API_URL` chưa được cấu hình trong Vercel. Gateway thực thi cơ chế Fail-Closed và trả về ngay **HTTP 503 `BACKEND_UNAVAILABLE`**. Trình duyệt nhận HTTP 503 và chặn đứng đăng nhập.
2. **Trên môi trường Local (hoặc khi kết nối FastAPI thực tế):** Yêu cầu được gửi về FastAPI `authenticate_user()`. FastAPI kiểm tra mật khẩu bằng Bcrypt hash trong SQLite. Tài khoản thử nghiệm mặc định `danhuynh@gari.vn` trong SQLite lưu hash `$2b$12$FprM6T6FwiQbbYKvfn...` không khớp với mật khẩu mẫu `Password123!`, dẫn đến **HTTP 401 `Email hoặc mật khẩu không chính xác`**. Hôm qua tài khoản này đăng nhập được là do Gateway tự động bỏ qua kiểm tra mật khẩu để cấp token động.

---

## 3. NGUYÊN NHÂN GỐC RỄ BẬC 2: XUNG ĐỘT NHÀ CẤP PHÁT (PROVIDER MISMATCH TRONG `firebase-client.js`)

Kiểm tra phương thức `login()` trong `frontend2/firebase-client.js` (dòng 311–330):
```javascript
// 1. Firebase Authentication
if (this.isFirebaseReady && this.firebaseAuth && this._fbMethods) {
    try {
        const cred = await withTimeout(
            this._fbMethods.signInWithEmailAndPassword(this.firebaseAuth, email, password),
            10000,
            'Đăng nhập qua Firebase quá thời gian chờ (10s).'
        );
        const token = await cred.user.getIdToken();
        const user = await this._exchangeFirebaseToken(token, null, rememberMe);
        return { success: true, user, provider: 'firebase' };
    } catch (fbErr) {
        const code = (fbErr?.code || '').toLowerCase();
        if (code.includes('api-key') || code === 'auth/operation-not-allowed') {
            console.warn('[GARI Auth] Firebase configuration issue, falling back to native auth:', fbErr?.code);
        } else {
            console.warn('[GARI Auth] Firebase sign-in failure:', fbErr?.code || fbErr);
            throw mapFirebaseError(fbErr); // <--- ĐIỂM CHẶN ĐỨNG
        }
    }
}

// 2. Native Backend Fallback
const res = await safeFetch('/api/auth/login', ...);
```

### Điểm bất nhất:
- Khi Firebase SDK được kích hoạt (`isFirebaseReady === true`), nếu người dùng nhập tài khoản đã đăng ký trong SQLite (ví dụ tài khoản nông dân tạo bằng native GARI Auth), Firebase SDK sẽ trả về lỗi `auth/user-not-found` hoặc `auth/invalid-credential`.
- Nhánh `catch (fbErr)` chỉ cho phép fall back sang `safeFetch('/api/auth/login')` nếu lỗi liên quan đến `api-key` hoặc `auth/operation-not-allowed`.
- Với mọi lỗi khác, SDK lập tức ném lỗi `throw mapFirebaseError(fbErr)` và **hoàn toàn không bao giờ gọi tới native `/api/auth/login`**.
- Hậu quả: Toàn bộ tài khoản tồn tại trong cơ sở dữ liệu SQLite bị từ chối đăng nhập ngay tại tầng client SDK.

---

## 4. BẰNG CHỨNG THỰC NGHIỆM TRÊN TRÌNH DUYỆT THỰC TẾ (PLAYWRIGHT FORENSIC TRACE)

### Thử nghiệm A: Đăng nhập bằng tài khoản SQLite hợp lệ (`farmer_test_1794399917@gari.vn`)
- **URL:** `http://127.0.0.1:8000/frontend2/login.html`
- **Thời gian xử lý:** 647 ms
- **Sự kiện mạng:**
  1. `POST http://127.0.0.1:8000/api/auth/login` → **HTTP 200 OK** (Payload: `{"email":"farmer_test_1794399917@gari.vn","password":"[REDACTED]","remember_me":false}`)
  2. `GET http://127.0.0.1:8000/api/user/profile` → **HTTP 200 OK**
  3. Chuyển hướng: `http://127.0.0.1:8000/frontend2/index.html` → **HTTP 200 OK**
  4. LocalStorage ghi nhận `gari_token` và `gari_user`.
- **Kết luận:** Khi backend FastAPI chạy và tài khoản có mật khẩu khớp trong SQLite, luồng native đăng nhập thành công 100% trong 0.65 giây.

### Thử nghiệm B: Đăng nhập bằng tài khoản `danhuynh@gari.vn` với `Password123!`
- **URL:** `http://127.0.0.1:8000/frontend2/login.html`
- **Kết quả:** Giao diện hiển thị cảnh báo đỏ `#authAlert`: *"Email hoặc mật khẩu không chính xác."*
- **Sự kiện mạng:** `POST /api/auth/login` → **HTTP 401 Unauthorized**
- **Kiểm tra cơ sở dữ liệu:**
  `bcrypt.checkpw('Password123!'.encode(), row['password_hash'].encode())` trả về **`False`**.

### Thử nghiệm C: Đăng nhập trên môi trường Vercel Preview (không có backend URL)
- **URL:** `https://[preview].vercel.app/frontend2/login.html`
- **Sự kiện mạng:** `POST /api/auth/login` → **HTTP 503 Service Unavailable**
- **Phản hồi:** `{"success":false,"code":"BACKEND_UNAVAILABLE","detail":"Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát."}`
- **Kết luận:** Do Vercel Edge Gateway không còn tự sinh token giả lập, nếu không có endpoint backend thực tế thì toàn bộ request đăng nhập trên Vercel Preview đều bị Fail-Closed trả về 503.

---

## 5. MA TRẬN ĐỐI CHIẾU THÀNH PHẦN

| Thành phần | Trạng thái hiện tại | Vấn đề phát hiện |
| :--- | :---: | :--- |
| **Frontend (`login.html`)** | Đã kết nối `window.gariAuth.login()` | Chuyển hướng sau đăng nhập hoạt động tốt khi backend trả về token. |
| **Edge Gateway (`api/[...path].js`)** | Fail-Closed chuyển tiếp về Backend | Đã xử lý chống nghẽn stream `readRawBody`, nhưng trên Vercel thiếu `VERCEL_BACKEND_API_URL` nên trả về 503. Trong môi trường local đã trỏ về `127.0.0.1:8000`. |
| **Client SDK (`firebase-client.js`)** | Ưu tiên Firebase trước Native | Khi tài khoản không có trên Firebase, SDK ném lỗi thay vì thử xác thực tiếp với SQLite native qua `/api/auth/login`. |
| **FastAPI Backend (`api_server.py`)** | Hoạt động bình thường | `/api/auth/login` và `/api/user/profile` xử lý chuẩn xác, sinh session token và cookie an toàn. |
| **Cơ sở dữ liệu SQLite** | Toàn vẹn 100% | Hash mật khẩu của các tài khoản cũ trong database không khớp với mật khẩu văn bản thô truyền vào từ client. |

---

## 6. ĐỀ XUẤT BẢN VÁ TỐI THIỂU & CÓ THỂ ĐẢO NGƯỢC (REVERSIBLE MINIMAL PATCH)

Để giải quyết dứt điểm vấn đề mà không vi phạm các điều cấm tuyệt đối (Không reset password bừa bãi, không PHP, không deploy Production, không tạo fallback identity giả mạo):

### Đề xuất Patch 1: Cho phép Fallback sang Native Backend khi Firebase không tìm thấy tài khoản
Trong `frontend2/firebase-client.js`, khi `signInWithEmailAndPassword` gặp lỗi `auth/user-not-found` hoặc `auth/invalid-credential`:
Thay vì ném lỗi chặn ngay, cho phép SDK tiếp tục chuyển sang **Bước 2: Native Backend Fallback (`/api/auth/login`)** để kiểm tra tài khoản trong SQLite.
- Nếu FastAPI xác thực mật khẩu SQLite thành công → Cho phép đăng nhập.
- Nếu FastAPI cũng từ chối → Trả về HTTP 401 chính thức.
*Đảm bảo: Không bỏ qua mật khẩu, không tạo identity giả, bảo toàn tính an toàn tuyệt đối.*

### Đề xuất Patch 2: Đồng bộ cấu hình môi trường Vercel Preview
Cấu hình biến `VERCEL_BACKEND_API_URL` trên Vercel Preview trỏ về địa chỉ máy chủ FastAPI thực tế (hoặc qua tunnel bảo mật) để Edge Gateway chuyển tiếp request xác thực thay vì trả 503.

---

## 7. YÊU CẦU PHÊ DUYỆT TRƯỚC KHI THỰC HIỆN

Kính đề nghị người dùng xác nhận:
1. Bạn có đồng ý áp dụng **Patch 1** cho `frontend2/firebase-client.js` để tự động chuyển tiếp sang kiểm tra tài khoản SQLite khi Firebase không có bản ghi người dùng?
2. Bạn muốn thực hiện đăng nhập kiểm thử trên trình duyệt bằng tài khoản nào:
   - Tài khoản đã đăng ký thành công: `farmer_test_1794399917@gari.vn` / `StrongPassword123!`
   - Hay bạn muốn cập nhật mật khẩu cho tài khoản `danhuynh@gari.vn` về mật khẩu xác định?

**CAM KẾT:** Tạm dừng, không chỉnh sửa mã nguồn cho đến khi nhận được chỉ thị và phê duyệt chính thức từ người dùng.

