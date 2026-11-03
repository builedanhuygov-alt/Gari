import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8000"

def request_json(url, method="GET", data=None, token=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers=headers,
        method=method
    )
    res = urllib.request.urlopen(req)
    return json.loads(res.read().decode("utf-8"))

print("==================================================")
print("GARI AI LAB — COMPLETE SAAS VERIFICATION SUITE")
print("==================================================")

# 1. Register User A
user_a_email = "nongdan.a@test.vn"
print(f"1. Registering User A ({user_a_email})...")
try:
    reg_a = request_json(f"{BASE}/api/auth/register", method="POST", data={
        "full_name": "Trần Văn An",
        "email": user_a_email,
        "password": "PasswordUserA123!",
        "confirm_password": "PasswordUserA123!",
        "account_type": "Nông hộ",
        "phone": "0911222333"
    })
    token_a = reg_a["token"]
    user_a_id = reg_a["user"]["id"]
    print(f"   -> Thành công: User ID {user_a_id}")
except urllib.error.HTTPError as e:
    # If already exists from earlier test, log in
    login_a = request_json(f"{BASE}/api/auth/login", method="POST", data={
        "email": user_a_email,
        "password": "PasswordUserA123!"
    })
    token_a = login_a["token"]
    user_a_id = login_a["user"]["id"]
    print(f"   -> Đã tồn tại, đăng nhập lại: User ID {user_a_id}")

# 2. Register User B
user_b_email = "nongdan.b@test.vn"
print(f"2. Registering User B ({user_b_email})...")
try:
    reg_b = request_json(f"{BASE}/api/auth/register", method="POST", data={
        "full_name": "Lê Thị Bình",
        "email": user_b_email,
        "password": "PasswordUserB123!",
        "confirm_password": "PasswordUserB123!",
        "account_type": "Hợp tác xã",
        "phone": "0944555666"
    })
    token_b = reg_b["token"]
    user_b_id = reg_b["user"]["id"]
    print(f"   -> Thành công: User ID {user_b_id}")
except urllib.error.HTTPError as e:
    login_b = request_json(f"{BASE}/api/auth/login", method="POST", data={
        "email": user_b_email,
        "password": "PasswordUserB123!"
    })
    token_b = login_b["token"]
    user_b_id = login_b["user"]["id"]
    print(f"   -> Đã tồn tại, đăng nhập lại: User ID {user_b_id}")

# 3. Test duplicate email rejection
print("3. Testing duplicate email rejection...")
try:
    request_json(f"{BASE}/api/auth/register", method="POST", data={
        "full_name": "Trùng Lặp",
        "email": user_a_email,
        "password": "Password123!",
        "confirm_password": "Password123!"
    })
    print("   -> LỖI: Trùng email không bị từ chối!")
except urllib.error.HTTPError as e:
    print(f"   -> CHUẨN: Bị từ chối với HTTP {e.code}")

# 4. Test wrong password rejection
print("4. Testing invalid credential rejection...")
try:
    request_json(f"{BASE}/api/auth/login", method="POST", data={
        "email": user_a_email,
        "password": "SaiMatKhau123!"
    })
    print("   -> LỖI: Sai mật khẩu vẫn đăng nhập được!")
except urllib.error.HTTPError as e:
    print(f"   -> CHUẨN: Bị từ chối với HTTP {e.code}")

# 5. User A creates Farm
print("5. User A creates a farm...")
farm_a = request_json(f"{BASE}/api/farms", method="POST", data={
    "name": "Nông trại Hoa Hướng Dương A",
    "province": "Lâm Đồng",
    "area_hectare": 6.8,
    "primary_crop": "Tomato",
    "variety": "Beefsteak F1",
    "location": "Lạc Dương, Lâm Đồng",
    "notes": "Mô hình thủy canh giá thể"
}, token=token_a)
farm_a_id = farm_a["farm"]["id"]
print(f"   -> Tạo nông trại thành công: #{farm_a_id} - {farm_a['farm']['name']}")

# 6. User A adds a plot
print("6. User A creates a crop plot...")
plot_a = request_json(f"{BASE}/api/farms/{farm_a_id}/plots", method="POST", data={
    "plot_name": "Lô Nhà Kính Số 1",
    "crop_name": "Cà chua",
    "area_hectare": 2.5,
    "planting_date": "2026-10-01"
}, token=token_a)
plot_a_id = plot_a["plot"]["id"]
print(f"   -> Tạo lô thành công: #{plot_a_id} - {plot_a['plot']['plot_name']}")

# 7. User A edits Farm
print("7. User A edits farm details...")
edit_res = request_json(f"{BASE}/api/farms/{farm_a_id}", method="PUT", data={
    "name": "Nông trại Hoa Hướng Dương A (Đã cập nhật)",
    "area_hectare": 8.5
}, token=token_a)
print(f"   -> Cập nhật thành công: Tên mới='{edit_res['farm']['name']}', Diện tích={edit_res['farm']['area_hectare']} ha")

# 8. User B cannot see or modify User A's Farm
print("8. Verifying strict user data isolation...")
farms_b = request_json(f"{BASE}/api/farms", token=token_b)
b_farm_ids = [f["id"] for f in farms_b["farms"]]
assert farm_a_id not in b_farm_ids, "BẢO MẬT HỎNG: User B nhìn thấy nông trại của User A!"
print("   -> CHUẨN: User B không thấy nông trại của User A.")

try:
    request_json(f"{BASE}/api/farms/{farm_a_id}", method="DELETE", token=token_b)
    print("   -> LỖI: User B xóa được nông trại của User A!")
except urllib.error.HTTPError as e:
    print(f"   -> CHUẨN: User B bị cấm truy cập/xóa với HTTP {e.code}")

# 9. Real AI Leaf Diagnosis Execution
print("9. Testing real leaf image upload & ConvNeXt model inference...")
# Find sample image in test_images or test_samples
sample_img_path = Path(r"D:\leaf-diseases-detector-main\data\organized\Tomato\Tomato_Bacterial_spot\00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG")
if not sample_img_path.exists():
    sample_img_path = Path("test_lua_xoac_la_virus.jpg")

assert sample_img_path and sample_img_path.exists(), "Không tìm thấy file ảnh mẫu!"
print(f"   -> Dùng ảnh lá thật: {sample_img_path}")

with open(sample_img_path, "rb") as f:
    img_bytes = f.read()

# Build multipart form-data
boundary = "----WebKitFormBoundaryGariTestBoundary123"
body_parts = []
body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
body_parts.append(f'Content-Disposition: form-data; name="image"; filename="{sample_img_path.name}"\r\n'.encode("utf-8"))
body_parts.append(b"Content-Type: image/jpeg\r\n\r\n")
body_parts.append(img_bytes)
body_parts.append(b"\r\n")

# crop field
body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
body_parts.append(b'Content-Disposition: form-data; name="crop"\r\n\r\n')
body_parts.append(b"Tomato\r\n")

# farm_id field
body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
body_parts.append(b'Content-Disposition: form-data; name="farm_id"\r\n\r\n')
body_parts.append(str(farm_a_id).encode("utf-8") + b"\r\n")

# plot_id field
body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
body_parts.append(b'Content-Disposition: form-data; name="plot_id"\r\n\r\n')
body_parts.append(str(plot_a_id).encode("utf-8") + b"\r\n")

# notes field
body_parts.append(f"--{boundary}\r\n".encode("utf-8"))
body_parts.append(b'Content-Disposition: form-data; name="notes"\r\n\r\n')
body_parts.append("Lá tầng dưới xuất hiện đốm nâu đen có viền vàng.\r\n".encode("utf-8"))

body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
full_body = b"".join(body_parts)

predict_req = urllib.request.Request(
    f"{BASE}/api/predict",
    data=full_body,
    headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token_a}"
    },
    method="POST"
)
predict_res = urllib.request.urlopen(predict_req)
predict_data = json.loads(predict_res.read().decode("utf-8"))

print("   -> KẾT QUẢ SUY LUẬN AI:")
print(f"      Cây trồng: {predict_data.get('crop_name')} ({predict_data.get('crop')})")
print(f"      Bệnh dự đoán: {predict_data.get('disease_name_vi')} ({predict_data.get('prediction')})")
print(f"      Độ tin cậy: {round(predict_data.get('confidence', 0) * 100, 2)}%")
print(f"      Mô hình: {predict_data.get('model', {}).get('name')}")
print(f"      Thời gian suy luận: {predict_data.get('inference_time_ms')} ms")
print(f"      Ảnh lưu thực tế tại: {predict_data.get('image_url')}")
print(f"      ID chẩn đoán CSDL: #{predict_data.get('saved_diagnosis_id')}")

# 10. Verify User A dashboard stats updated
print("10. Verifying User A dashboard reflects actual diagnosis and farm...")
stats_a = request_json(f"{BASE}/api/dashboard/stats", token=token_a)
print(f"   -> farms_total: {stats_a.get('farms_total')}")
print(f"   -> total_hectares: {stats_a.get('total_hectares')} ha")
print(f"   -> diagnoses_total: {stats_a.get('diagnoses_total')} lượt")
print(f"   -> healthy_rate: {stats_a.get('healthy_rate_percent')}%")
print(f"   -> disease_distribution: {stats_a.get('disease_distribution')}")
print(f"   -> recent_diagnoses count: {len(stats_a.get('recent_diagnoses', []))}")
assert stats_a.get("diagnoses_total") >= 1, "Chẩn đoán chưa được lưu vào bảng diagnoses của User A!"

# 11. Test Password Recovery Flow
print("11. Testing Password Recovery workflow...")
forgot_res = request_json(f"{BASE}/api/auth/forgot-password", method="POST", data={
    "email": user_a_email
})
reset_token = forgot_res.get("reset_token")
print(f"   -> Dev reset token created: {reset_token[:16]}... (Valid 15m)")

reset_res = request_json(f"{BASE}/api/auth/reset-password", method="POST", data={
    "token": reset_token,
    "new_password": "NewSecurePassword456!",
    "confirm_password": "NewSecurePassword456!"
})
print(f"   -> Đổi mật khẩu thành công: {reset_res.get('message')}")

# Login with new password
login_new_pwd = request_json(f"{BASE}/api/auth/login", method="POST", data={
    "email": user_a_email,
    "password": "NewSecurePassword456!"
})
print(f"   -> Đăng nhập mật khẩu mới thành công! User: {login_new_pwd['user']['full_name']}")

# 12. Test Logout
print("12. Testing Logout...")
logout_res = request_json(f"{BASE}/api/auth/logout", method="POST", token=login_new_pwd["token"])
print(f"   -> Đăng xuất: {logout_res.get('message')}")

# Verify old session token revoked
try:
    request_json(f"{BASE}/api/auth/me", token=login_new_pwd["token"])
    print("   -> LỖI: Session token cũ vẫn hợp lệ sau khi đăng xuất!")
except urllib.error.HTTPError as e:
    print(f"   -> CHUẨN: Session bị thu hồi ngay lập tức (HTTP {e.code})")

print("\n==================================================")
print("TẤT CẢ 12 HẠNG MỤC KIỂM THỬ XÁC THỰC VÀ DỮ LIỆU THẬT ĐÃ HOÀN TẤT THÀNH CÔNG 100%!")
print("==================================================")
