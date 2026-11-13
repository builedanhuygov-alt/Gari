"""
GARI AgriTech Platform Expansion - Comprehensive Integration & Verification Test Suite
Tests:
1. Backend & Server Health Check
2. Auth & RBAC (Personal User, Host Admin, Certified Expert)
3. Notifications API (/api/notifications)
4. Host Console Expansion APIs (/api/host/subscriptions/overview, /api/host/ai/test, /api/host/experts)
5. Expert Network Lifecycle (Apply -> Admin Review -> Claim Case -> Message Thread -> Resolve with IPM Prescription)
6. Mobile Parity Endpoints (Diagnosis /api/predict, Explainer /api/assistant/chat, Farms /api/farms)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import uuid
import json
import io
import urllib.request
import urllib.parse
from PIL import Image

BASE_URL = "http://127.0.0.1:8000"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def request(method, path, data=None, token=None, files=None):
    url = f"{BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = None
    if files:
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body_parts = []
        if data:
            for k, v in data.items():
                body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
        for field_name, (filename, file_bytes, content_type) in files.items():
            header = f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field_name}\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n"
            body_parts.append(header.encode() + file_bytes + b"\r\n")
        body_parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(body_parts)
    elif data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except:
            return e.code, {"error": err_body}
    except Exception as e:
        return 500, {"error": str(e)}

def run_tests():
    log("=== STARTING GARI PLATFORM EXPANSION TEST SUITE ===")
    passed = 0
    total = 0

    def assert_test(cond, name, detail=""):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
            log(f"PASS: {name} {detail}", "SUCCESS")
        else:
            log(f"FAIL: {name} - {detail}", "ERROR")
            raise AssertionError(f"Test failed: {name}")

    # 1. Health check
    code, res = request("GET", "/api/health")
    assert_test(code == 200 and res.get("status") == "ok", "Server Health Check", f"version: {res.get('version')}")

    # 2. Setup Host Admin
    # Create or update host admin in DB
    import gari_database, gari_auth
    admin_email = f"host_admin_{uuid.uuid4().hex[:6]}@gari.local"
    admin_pw = "HostAdmin@123456"
    admin_pw_hash = gari_auth.hash_password(admin_pw)
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (full_name, name, email, password_hash, account_type, is_admin, is_host_admin, is_active)
            VALUES (?, ?, ?, ?, 'admin', 1, 1, 1)
        """, ("Chủ Tọa Máy Chủ", "Chủ Tọa", admin_email, admin_pw_hash))
        host_admin_id = cursor.lastrowid
        conn.commit()

    code, login_res = request("POST", "/api/auth/login", {"email": admin_email, "password": admin_pw})
    assert_test(code == 200 and "token" in login_res, "Host Admin Login", f"Email: {admin_email}")
    host_token = login_res["token"]

    # 3. Host Overview & AI Diagnostic Test
    code, host_ai_test = request("POST", "/api/host/ai/test", token=host_token)
    assert_test(code == 200 and host_ai_test.get("success") == True, "Host Realtime AI Diagnostic Test", 
                f"Latency: {host_ai_test.get('diagnostics', {}).get('latency_ms')}ms")

    code, sub_res = request("GET", "/api/host/subscriptions/overview", token=host_token)
    assert_test(code == 200 and "plan_breakdown" in sub_res, "Host Subscriptions & MRR Overview",
                f"Total Users: {sub_res.get('total_users')}")

    # 4. Farmer User & Leaf Diagnosis
    farmer_email = f"farmer_{uuid.uuid4().hex[:6]}@gari.local"
    farmer_pw = "Farmer@123456"
    farmer_pw_hash = gari_auth.hash_password(farmer_pw)
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (full_name, name, email, password_hash, account_type, is_active)
            VALUES (?, ?, ?, ?, 'free', 1)
        """, ("Nông Dân Ba Tri", "Ba Tri", farmer_email, farmer_pw_hash))
        farmer_id = cursor.lastrowid
        conn.commit()

    code, farmer_login = request("POST", "/api/auth/login", {"email": farmer_email, "password": farmer_pw})
    assert_test(code == 200, "Farmer User Login")
    farmer_token = farmer_login["token"]

    # Test Mobile Parity: Predict Leaf
    if os.path.exists("test_leaf.jpg"):
        with open("test_leaf.jpg", "rb") as f:
            leaf_bytes = f.read()
    elif os.path.exists("tests/fixtures/test_leaf.jpg"):
        with open("tests/fixtures/test_leaf.jpg", "rb") as f:
            leaf_bytes = f.read()
    else:
        dummy_img = Image.new("RGB", (224, 224), color=(34, 139, 34))
        buf = io.BytesIO()
        dummy_img.save(buf, format="JPEG")
        leaf_bytes = buf.getvalue()

    code, predict_res = request(
        "POST", "/api/predict",
        data={"crop_filter": "Tomato"},
        token=farmer_token,
        files={"file": ("leaf.jpg", leaf_bytes, "image/jpeg")}
    )
    assert_test(code == 200 and predict_res.get("success") == True, "Mobile Leaf Diagnosis API (/api/predict)",
                f"Primary: {predict_res.get('primary_disease')}")

    # Test Explainer Chatbot (/api/assistant/chat)
    code, chat_res = request(
        "POST", "/api/assistant/chat",
        data={
            "message": "Thuốc nào phun trị đốm lá cà chua an toàn?",
            "diagnosis_id": predict_res.get("diagnosis_id") or predict_res.get("id"),
            "crop": "Tomato",
            "disease": predict_res.get("primary_disease", "Đốm lá")
        },
        token=farmer_token
    )
    assert_test(code == 200 and ("response" in chat_res or "reply" in chat_res), "AI Explainer Chatbot (/api/assistant/chat)")

    # 5. Expert Application & Review Lifecycle
    expert_candidate_email = f"candidate_exp_{uuid.uuid4().hex[:6]}@gari.local"
    candidate_pw = "Candidate@123456"
    cand_hash = gari_auth.hash_password(candidate_pw)
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (full_name, name, email, password_hash, account_type, is_active)
            VALUES (?, ?, ?, ?, 'free', 1)
        """, ("KS. Trần Đình Trọng", "Trần Đình Trọng", expert_candidate_email, cand_hash))
        cand_id = cursor.lastrowid
        conn.commit()

    code, cand_login = request("POST", "/api/auth/login", {"email": expert_candidate_email, "password": candidate_pw})
    cand_token = cand_login["token"]

    # Submit Expert Application
    code, app_res = request(
        "POST", "/api/expert/apply",
        data={
            "full_name": "KS. Trần Đình Trọng",
            "phone": "0987654321",
            "title": "Kỹ sư BVTV Trưởng",
            "organization": "Viện KHKT Nông nghiệp Miền Nam",
            "specialties": ["Tomato", "Rice", "Corn"],
            "years_experience": 7,
            "degree_details": "Kỹ sư Nông học xuất sắc 2017"
        },
        token=cand_token
    )
    assert_test(code == 200 and "application_id" in app_res, "Submit Expert Application (/api/expert/apply)")
    application_id = app_res["application_id"]

    # Host Admin inspects applications
    code, apps_list = request("GET", "/api/host/experts/applications?status=pending", token=host_token)
    assert_test(code == 200 and any(a["id"] == application_id for a in apps_list.get("applications", [])),
                "Host Inspect Pending Applications")

    # Host Admin approves expert application
    code, review_res = request(
        "POST", f"/api/host/experts/applications/{application_id}/review",
        data={"action": "approve", "admin_notes": "Bằng cấp & kinh nghiệm thực tế rất tốt.", "commission_rate": 0.15},
        token=host_token
    )
    assert_test(code == 200 and review_res.get("success") == True, "Host Approve Expert Application")

    # Re-login expert candidate to get updated session with is_expert=1
    code, expert_login = request("POST", "/api/auth/login", {"email": expert_candidate_email, "password": candidate_pw})
    expert_token = expert_login["token"]
    assert_test(expert_login.get("user", {}).get("is_expert") == True, "Verify User Granted is_expert=1")

    # 6. Farmer submits consultation case & Expert claims/resolves it
    code, case_submit = request(
        "POST", "/api/expert/cases",
        data={
            "crop": "Tomato",
            "symptoms_description": "Lá cà chua có đốm nâu tròn quầng vàng, lan nhanh từ lá già lên ngọn.",
            "urgency": "high"
        },
        token=farmer_token
    )
    assert_test(code == 200 and "case" in case_submit, "Farmer Submit Expert Case")
    case_id = case_submit["case"]["id"]

    # Expert lists portal cases
    code, portal_cases = request("GET", "/api/expert/portal/cases?filter_type=unassigned", token=expert_token)
    assert_test(code == 200 and any(c["id"] == case_id for c in portal_cases.get("cases", [])), "Expert View Unassigned Queue")

    # Expert claims case
    code, claim_res = request("POST", f"/api/expert/cases/{case_id}/claim", token=expert_token)
    assert_test(code == 200 and claim_res.get("success") == True, "Expert Claim Case")

    # Exchange messages in case
    code, msg_1 = request(
        "POST", f"/api/expert/cases/{case_id}/messages",
        data={"message": "Chào bác, mật độ đốm bệnh trên cây đã xuất hiện bao nhiêu ngày rồi ạ?"},
        token=expert_token
    )
    assert_test(code == 200, "Expert Send Chat Message")

    code, msg_2 = request(
        "POST", f"/api/expert/cases/{case_id}/messages",
        data={"message": "Dạ khoảng 3 ngày nay sau đợt mưa rào đêm bác sĩ ạ."},
        token=farmer_token
    )
    assert_test(code == 200, "Farmer Reply Chat Message")

    # Expert resolves case with IPM prescription
    code, resolve_res = request(
        "POST", f"/api/expert/cases/{case_id}/resolve",
        data={
            "resolution_notes": "Bệnh Đốm Mắt Cua (Cercospora). Cần tỉa thông thoáng gốc, ngừng bón đạm, phun ướt đều 2 mặt lá.",
            "diagnosis_correction": "Đốm mắt cua (Cercospora leaf spot)",
            "prescription_data": {
                "active_ingredients": "Difenoconazole 150g/l + Azoxystrobin 250g/l",
                "dosage": "20ml / bình 25L",
                "phi_days": 7
            }
        },
        token=expert_token
    )
    assert_test(code == 200 and resolve_res.get("success") == True, "Expert Resolve Case with Prescription")

    # 7. Check Farmer In-App Notification
    code, notif_res = request("GET", "/api/notifications", token=farmer_token)
    assert_test(code == 200 and notif_res.get("total", 0) > 0, "Farmer In-App Notifications Delivery",
                f"Count: {notif_res.get('total')}")

    # Mark notification read
    notif_id = notif_res["notifications"][0]["id"]
    code, read_res = request("PATCH", f"/api/notifications/{notif_id}/read", token=farmer_token)
    assert_test(code == 200, "Mark Notification Read")

    log(f"=== ALL TESTS PASSED: {passed}/{total} ===")
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
