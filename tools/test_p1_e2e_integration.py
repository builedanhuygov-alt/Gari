import urllib.request
import urllib.error
import json
import time
import os

BASE = "http://127.0.0.1:8000"

print("======================================================================")
print(" GARI PHASE P1 — FULL END-TO-END INTEGRATION TEST")
print("======================================================================")

# 1. Register a dedicated test user
ts = int(time.time())
user_email = f"p1_e2e_{ts}@gari.vn"
user_pass = "P1_Integration#2026"
reg_payload = json.dumps({
    "email": user_email,
    "password": user_pass,
    "full_name": "Kỹ Sư Nông Nghiệp P1",
    "account_type": "farmer"
}).encode()

req = urllib.request.Request(f"{BASE}/api/auth/register", data=reg_payload, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req) as r:
    reg_data = json.loads(r.read().decode())
    token = reg_data["token"]
    user_id = reg_data["user"]["id"]
    print(f"[PASS] 1. User authenticated: {user_email} (ID: {user_id})")

# 2. Leaf Intelligence & Reliability Engine: Diagnose leaf image
IMG_PATH = r"D:\leaf-diseases-detector-main\data\organized\Tomato\Tomato_Bacterial_spot\00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG"
if not os.path.exists(IMG_PATH):
    IMG_PATH = r"D:\leaf-diseases-detector-main\test_leaf.jpg"

with open(IMG_PATH, "rb") as f:
    img_bytes = f.read()

boundary = "----WebKitP1E2E" + hex(int(time.time()))[2:]
body = bytearray()
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"crop\"\r\n\r\nTomato\r\n".encode())
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"mode\"\r\n\r\nmanual\r\n".encode())
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"growth_stage\"\r\n\r\nvegetative\r\n".encode())
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"user_symptoms\"\r\n\r\nĐốm nâu nhỏ sũng nước trên lá dưới\r\n".encode())
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"leaf.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode())
body.extend(img_bytes)
body.extend(f"\r\n--{boundary}--\r\n".encode())

req = urllib.request.Request(
    f"{BASE}/api/predict",
    data=bytes(body),
    headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}"
    },
    method="POST"
)

with urllib.request.urlopen(req) as r:
    diag_res = json.loads(r.read().decode())
    diag_id = diag_res["saved_diagnosis_id"]
    pred_disease = diag_res["prediction"]
    conf = diag_res["confidence"]
    print(f"[PASS] 2. Leaf Intelligence inference complete:")
    print(f"       Diagnosis ID: {diag_id} | Crop: {diag_res['crop_name_vi']} | Disease: {pred_disease} ({round(conf*100, 2)}%)")
    print(f"       Grad-CAM Attention: {diag_res.get('has_attention_map')} (Type: {diag_res.get('localization_type')})")
    assert diag_id is not None
    assert diag_res["success"] is True

# 3. Diagnosis History: Verify record is persisted and scoped to this user
req = urllib.request.Request(f"{BASE}/api/diagnoses", headers={"Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req) as r:
    hist = json.loads(r.read().decode())
    user_diags = hist["diagnoses"]
    found = [d for d in user_diags if d["id"] == diag_id]
    assert len(found) == 1, "Diagnosis not found in user's history!"
    d_rec = found[0]
    print(f"[PASS] 3. Diagnosis History verified:")
    print(f"       Record ID: {d_rec['id']} | Disease: {d_rec['predicted_disease']} | Status: {d_rec['monitoring_status']}")
    assert d_rec["user_id"] == user_id

# 4. GARI Copilot: Chat grounded with this diagnosis context
chat_payload = json.dumps({
    "diagnosis_id": diag_id,
    "message": "Tôi cần làm gì để ngăn ngừa bệnh này lây lan sang các luống cà chua khác?"
}).encode()

req = urllib.request.Request(
    f"{BASE}/api/assistant/chat",
    data=chat_payload,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    method="POST"
)

with urllib.request.urlopen(req) as r:
    chat_res = json.loads(r.read().decode())
    print(f"[PASS] 4. GARI Copilot replied with agronomic grounding:")
    print(f"       Grounding Crop: {chat_res.get('grounding_crop')} | Disease: {chat_res.get('grounding_disease')}")
    print(f"       Reply preview: {chat_res.get('reply', '')[:120]}...")
    assert chat_res.get("grounding_crop") in ("Tomato", "Cà chua", "tomato")

# 5. Treatment & Follow-up: Record treatment action and scheduled check
followup_payload = json.dumps({
    "monitoring_status": "treated",
    "observation_notes": "Đã cách ly luống bệnh và phun phòng trừ bằng chế phẩm sinh học đồng oxit.",
    "treatment_action": "Phun đồng oxit & cách ly"
}).encode()

req = urllib.request.Request(
    f"{BASE}/api/diagnoses/{diag_id}/follow-up",
    data=followup_payload,
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    method="PATCH"
)

with urllib.request.urlopen(req) as r:
    fu_res = json.loads(r.read().decode())["diagnosis"]
    print(f"[PASS] 5. Treatment & Follow-up recorded:")
    print(f"       Updated Monitoring Status: {fu_res['monitoring_status']} | Treatment Status: {fu_res['treatment_status']}")
    assert fu_res["monitoring_status"] == "treated"
    assert fu_res["treatment_status"] == "in_progress"

print("======================================================================")
print(" ALL 5 END-TO-END P1 INTEGRATION WORKFLOW CHECKS PASSED (100%)")
print("======================================================================")

