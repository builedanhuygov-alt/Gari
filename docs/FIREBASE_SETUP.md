# GARI 2.0 — Hướng Dẫn Cấu Hình Firebase (Firebase Setup Guide)

Tài liệu hướng dẫn thiết lập và tích hợp Firebase Authentication, Cloud Firestore và Firebase Storage cho nền tảng GARI AgriTech 2.0.

---

## 1. Tổng Quan Cấu Trúc Firebase trong GARI

Trong kiến trúc GARI 2.0:
- **Firebase chịu trách nhiệm:**
  1. Quản lý định danh người dùng và phiên đăng nhập (Firebase Authentication).
  2. Lưu trữ hồ sơ định danh xã hội, phân quyền tổ chức và dữ liệu cấu hình phi cấu trúc (Firestore).
  3. Lưu trữ tệp tin người dùng: Ảnh đại diện, ảnh trang trại, chứng nhận tiêu chuẩn VietGAP/GlobalGAP (Firebase Storage).
- **Máy chủ Host GARI chịu trách nhiệm:**
  1. Quản trị máy chủ, tải/bỏ tải mô hình AI, thực hiện suy luận nông học (Inference Engine).
  2. Quản lý hạn ngạch nguyên tử, sổ cái thanh toán, voucher và duyệt kiểm duyệt vi phạm.

---

## 2. Các Bước Thiết Lập Dự Án Firebase

### Bước 1: Khởi tạo Project trên Firebase Console
1. Truy cập [Firebase Console](https://console.firebase.google.com/).
2. Chọn **Add project** và đặt tên dự án: `gari-ai-lab` (hoặc project ID khả dụng tương ứng).
3. Bật hoặc tắt Google Analytics theo nhu cầu.

### Bước 2: Bật Firebase Authentication
1. Vào **Build** → **Authentication** → **Get Started**.
2. Trong tab **Sign-in method**, kích hoạt:
   - **Email/Password:** Bật tùy chọn đầu tiên (Email/Password).
   - *(Tùy chọn)* **Google:** Thêm tài khoản hỗ trợ.
3. Trong tab **Templates**, tùy chỉnh thư gửi kích hoạt email và lấy lại mật khẩu với tên hiển thị **GARI AgriTech**.

### Bước 3: Khởi tạo Cloud Firestore
1. Vào **Build** → **Firestore Database** → **Create database**.
2. Chọn vị trí lưu trữ: `asia-southeast1` (Singapore) hoặc `asia-east1` (Taiwan) để tối ưu độ trễ cho người dùng tại Việt Nam.
3. Chọn chế độ bảo mật: **Start in production mode** (các quy tắc trong `firestore.rules` sẽ được triển khai).
4. Áp dụng quy tắc và chỉ mục:
   ```bash
   npx firebase deploy --only firestore:rules,firestore:indexes
   ```

### Bước 4: Khởi tạo Firebase Storage
1. Vào **Build** → **Storage** → **Get Started**.
2. Chọn vị trí lưu trữ cùng khu vực với Firestore.
3. Áp dụng quy tắc lưu trữ:
   ```bash
   npx firebase deploy --only storage
   ```

---

## 3. Cấu Hình Firebase Admin SDK trên Máy Chủ Host

1. Trên Firebase Console, vào **Project Settings** (biểu tượng bánh răng) → **Service accounts**.
2. Bấm **Generate new private key** và tải tệp JSON về.
3. Lưu tệp JSON này vào máy chủ tại đường dẫn an toàn (KHÔNG commit lên Git):
   ```
   config/firebase-service-account.json
   ```
4. Cấu hình biến môi trường trong file `.env`:
   ```ini
   FIREBASE_PROJECT_ID=gari-ai-lab
   FIREBASE_CREDENTIALS_PATH=config/firebase-service-account.json
   ```

---

## 4. Tệp Tin Cấu Hình & Quy Tắc Bảo Mật Đã Triển Khai Trong Kho Mã Nguồn

- `firebase.json`: Khai báo dịch vụ Firestore, Storage và cấu hình Emulator cục bộ.
- `firestore.rules`: Quy tắc bảo mật Firestore (Default Deny, chỉ cho phép chủ sở hữu đọc/ghi hồ sơ của mình, cấm người dùng tự sửa vai trò hoặc hạn ngạch).
- `storage.rules`: Quy tắc bảo mật tệp tin (giới hạn dung lượng ảnh < 15MB, kiểm tra định dạng ảnh).
- `firestore.indexes.json`: Khai báo các composite index phục vụ truy vấn thành viên tổ chức và thông báo.
- `gari_firebase.py`: Module backend xác thực Firebase ID Token với Firebase Admin SDK và đồng bộ dữ liệu người dùng.

---

## 5. Sử Dụng Firebase Emulators để Kiểm Thử Cục Bộ

Khi phát triển mà không muốn kết nối trực tiếp đến Cloud Firebase:
```bash
npx firebase emulators:start
```
Các cổng giả lập cục bộ:
- **Emulator UI:** `http://localhost:4000`
- **Auth Emulator:** `http://localhost:9099`
- **Firestore Emulator:** `http://localhost:8080`
- **Storage Emulator:** `http://localhost:9199`
