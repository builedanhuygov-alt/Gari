import urllib.request
import urllib.error
import json
import time
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000"
TOMATO_IMG = r"D:\leaf-diseases-detector-main\data\organized\Tomato\Tomato_Bacterial_spot\00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG"

AUTH_TOKEN = None

def req(url, method="GET", data=None, headers=None):
    global AUTH_TOKEN
    if headers is None:
        headers = {}
    if AUTH_TOKEN and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    if data is not None and isinstance(data, (dict, list)):
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(f"{BASE_URL}{url}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except:
            return e.code, {"error": body}

print("=" * 70)
print(" GARI AI LAB — AGRITECH PLATFORM INTEGRATION TESTS")
print("=" * 70)

# 0. Authenticate
st, auth_res = req("/api/auth/login", method="POST", data={"email": "danhuynh@gari.vn", "password": "Password123!"})
assert st == 200 and "token" in auth_res, f"Authentication failed: {auth_res}"
AUTH_TOKEN = auth_res["token"]
print(f"[OK] 0. Authenticated as: {auth_res.get('user', {}).get('email')}")

# 1. Operational Dashboard Stats
st, res = req("/api/dashboard/stats")
assert st == 200, f"Dashboard failed: {res}"
print(f"[OK] 1. Dashboard Stats: {res.get('farms_total')} farms, {res.get('diagnoses_total')} diagnoses, Health rate: {res.get('healthy_rate_percent')}%")

# 2. List Farms
st, res = req("/api/farms")
assert st == 200 and res.get("success"), f"Farms failed: {res}"
initial_farms_count = res.get("total", 0)
print(f"[OK] 2. Listed Farms: {initial_farms_count} farms found")

# 3. Create a New Farm
new_farm_payload = {
    "name": "Nông Trại Khảo Nghiệm Gari Sơn La",
    "location": "Xã Chiềng Mung, Huyện Mai Sơn",
    "province": "Sơn La",
    "area_hectare": 4.5,
    "primary_crop": "Tomato",
    "variety": "F1 Trang Nông",
    "soil_type": "Đất Feralit nâu đỏ",
    "irrigation_type": "Tưới nhỏ giọt bù áp",
    "notes": "Mô hình thử nghiệm AI ConvNeXt giám sát dịch tễ 2026."
}
st, res = req("/api/farms", method="POST", data=new_farm_payload)
assert st == 200 and res.get("success"), f"Create farm failed: {res}"
created_farm = res.get("farm")
farm_id = created_farm["id"]
print(f"[OK] 3. Created Farm #{farm_id}: '{created_farm['name']}' ({created_farm['province']})")

# 4. Run AI Prediction linked to the new farm
boundary = "----WebKitFormBoundaryGariTest" + hex(int(time.time()))[2:]
body = bytearray()
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"crop\"\r\n\r\nTomato\r\n".encode("utf-8"))
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"farm_id\"\r\n\r\n{farm_id}\r\n".encode("utf-8"))
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"notes\"\r\n\r\nTest diagnosis from automated AgriTech suite\r\n".encode("utf-8"))
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"save_history\"\r\n\r\ntrue\r\n".encode("utf-8"))
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"tomato_leaf.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode("utf-8"))
with open(TOMATO_IMG, "rb") as f:
    body.extend(f.read())
body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

st, pred_res = req("/api/predict", method="POST", data=bytes(body), headers={
    "Content-Type": f"multipart/form-data; boundary={boundary}",
    "Content-Length": str(len(body))
})
assert st == 200 and pred_res.get("success"), f"Prediction failed: {pred_res}"
saved_diag_id = pred_res.get("saved_diagnosis_id")
print(f"[OK] 4. AI Diagnosis: Predicted '{pred_res.get('predicted_disease')}' ({round(pred_res.get('confidence', 0)*100, 2)}%)")
print(f"       Enriched Vietnamese name: '{pred_res.get('disease_name_vi')}'")
print(f"       Scientific name: '{pred_res.get('disease_knowledge', {}).get('scientific_name')}'")
print(f"       Saved to database record #{saved_diag_id} linked to Farm #{farm_id}")

# 5. Check Diagnoses History
st, res = req(f"/api/diagnoses?farm_id={farm_id}")
assert st == 200 and res.get("total", 0) >= 1, f"Diagnosis history failed: {res}"
print(f"[OK] 5. Diagnosis History: Found {res.get('total')} linked records for Farm #{farm_id}")

# 6. Agricultural Knowledge Center
st, res = req("/api/knowledge/crops")
assert st == 200 and res.get("total", 0) >= 40, f"Crops knowledge failed: {res}"
print(f"[OK] 6. Crop Knowledge: Catalog contains {res.get('total')} verified crops")

st, res = req("/api/knowledge/diseases?crop=Tomato&q=Bacterial")
assert st == 200 and len(res.get("diseases", [])) >= 1, f"Disease search failed: {res}"
disease = res["diseases"][0]
print(f"[OK] 7. Disease Knowledge Search: '{disease['disease_vi']}' -> Scientific: {disease['scientific_name']}")

# 7. Risk Monitoring API
st, res = req("/api/risk/monitoring")
assert st == 200 and "observed_weather" in res, f"Risk monitoring failed: {res}"
w = res["observed_weather"]
print(f"[OK] 8. Risk Monitoring: Temp {w['temperature_c']}°C, Humidity {w['humidity_pct']}%, Active Alerts: {len(res['alerts'])}")

# 8. Expert Consultation Support Case
case_payload = {
    "diagnosis_id": saved_diag_id,
    "farm_id": farm_id,
    "farmer_name": "Lò Văn Mười",
    "phone": "0988 123 456",
    "crop_name": "Cà chua",
    "suspected_disease": "Đốm vi khuẩn giai đoạn đậu quả",
    "symptoms_description": "Lá dưới xuất hiện nhiều đốm thâm đen có quầng vàng, lan nhanh sau 2 trận mưa giông.",
    "field_conditions": "Độ ẩm đất cao, nhà lưới thoáng khí vừa phải."
}
st, res = req("/api/expert/cases", method="POST", data=case_payload)
assert st == 200 and res.get("success"), f"Expert case submit failed: {res}"
case_id = res["case"]["id"]
print(f"[OK] 9. Expert Case Submitted: #{case_id} (Status: {res['case']['status']})")

# 9. Update Case Status (Simulate Expert Review)
update_payload = {
    "status": "Under review",
    "assigned_expert": "TS. Lê Minh Hoàng (Viện BVTV)",
    "expert_notes": "Đã xem ảnh tổn thương: đúng triệu chứng vi khuẩn Xanthomonas. Khuyến nghị cách ly luống bệnh và phun phòng gốc đồng."
}
st, res = req(f"/api/expert/cases/{case_id}", method="PATCH", data=update_payload)
assert st == 200 and res.get("case", {}).get("status") == "Under review"
print(f"[OK] 10. Expert Case Reviewed: Assigned to '{res['case']['assigned_expert']}'")

# Clean up test farm
req(f"/api/farms/{farm_id}", method="DELETE")
print(f"[OK] 11. Cleanup: Deleted test farm #{farm_id}")

print("=" * 70)
print(" ALL 11 AGRITECH PLATFORM INTEGRATION CHECKS PASSED!")
print("=" * 70)
