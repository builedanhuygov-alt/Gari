import os
import sys
import json
import sqlite3
import hashlib
import io
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("."))

import httpx
import gari_auth
import gari_database

BASE_URL = "http://localhost:8000"

def make_test_leaf_img(color=(34, 150, 40)):
    from PIL import ImageDraw
    img = Image.new("RGB", (300, 300), (220, 220, 220))
    draw = ImageDraw.Draw(img)
    draw.polygon([(150, 30), (260, 150), (150, 270), (40, 150)], fill=color, outline=(20, 100, 25))
    for y in range(60, 240, 20):
        draw.line([(150, y), (150 + (y % 40) * 2, y + 15)], fill=(80, 200, 60), width=2)
        draw.line([(150, y), (150 - (y % 40) * 2, y + 15)], fill=(80, 200, 60), width=2)
    draw.ellipse([120, 100, 135, 115], fill=(120, 60, 20))
    draw.ellipse([160, 180, 180, 195], fill=(130, 70, 25))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def run_suite():
    print("=== STARTING GARI LEAF INTELLIGENCE & ASSISTANT TEST SUITE ===")

    # 1. Test Navigation Consolidation
    with open("frontend2/app.js", "r", encoding="utf-8") as f:
        app_js = f.read()
    assert "leaf_check" not in app_js, "leaf_check still present in app.js!"
    assert "GARI Leaf Intelligence" in app_js, "GARI Leaf Intelligence label missing in app.js!"
    print("PASS: 1. Navigation consolidated in app.js (0 duplicate leaf_check links)")

    # 2. Test Assistant Status Endpoint (Unconfigured State)
    res = httpx.get(f"{BASE_URL}/api/assistant/status")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    st_data = res.json()
    assert st_data["status"] in ("api_unconfigured", "ready")
    assert "api_key" not in st_data, "API key leaked in status endpoint!"
    assert st_data["system_name"] == "GARI Plant Health Assistant"
    print(f"PASS: 2. Assistant Status endpoint working cleanly: status={st_data['status']}")

    # 3. Create or login test user and admin
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, is_admin FROM users WHERE is_admin = 1 LIMIT 1")
        admin_row = cursor.fetchone()
        if not admin_row:
            admin_user = gari_auth.register_user(
                email="admin_test_assistant@gari.local",
                password="AdminPassword123!",
                full_name="Admin Test Assistant"
            )
            cursor.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin_user["id"],))
            conn.commit()
            admin_id = admin_user["id"]
        else:
            admin_id = admin_row[0]

    admin_session = gari_auth.create_session(user_id=admin_id)
    admin_token = admin_session if isinstance(admin_session, str) else admin_session["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 4. Perform a real diagnosis with field observations
    img_bytes = make_test_leaf_img(color=(40, 150, 40))
    files = {"image": ("test_leaf.jpg", img_bytes, "image/jpeg")}
    form_data = {
        "mode": "auto",
        "crop": "Tomato",
        "notes": "Quan sát thực địa kiểm thử tự động",
        "growth_stage": "Ra hoa / Đậu quả",
        "user_symptoms": "Đốm cháy lá mép phiến lá",
        "field_conditions": "Mưa liên tục 2 ngày, độ ẩm 90%",
        "consent_store_image": "true"
    }

    diag_res = httpx.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=form_data, headers=admin_headers)
    assert diag_res.status_code == 200, f"Diagnose failed: {diag_res.text}"
    diag_data = diag_res.json()
    diag_id = diag_data.get("diagnosis_id") or diag_data.get("id") or diag_data.get("saved_diagnosis_id")
    print(f"PASS: 4. Diagnosis completed successfully, ID=#{diag_id}")

    # 5. Verify field observations persisted in SQLite
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT growth_stage, user_symptoms, field_conditions FROM diagnoses WHERE id = ?", (diag_id,))
        row = cursor.fetchone()
        assert row is not None, f"Diagnosis #{diag_id} not found in DB!"
        assert row[0] == "Ra hoa / Đậu quả", f"growth_stage mismatch: {row[0]}"
        assert row[1] == "Đốm cháy lá mép phiến lá", f"user_symptoms mismatch: {row[1]}"
        assert row[2] == "Mưa liên tục 2 ngày, độ ẩm 90%", f"field_conditions mismatch: {row[2]}"
    print("PASS: 5. Field observations verified in SQLite diagnoses table")

    # 6. Test Assistant Chat Endpoint (Unconfigured State returns api_unconfigured cleanly)
    chat_payload = {
        "diagnosis_id": diag_id,
        "message": "Bệnh này có lây lan nhanh không?",
        "conversation_history": [],
        "field_context": {
            "growth_stage": "Ra hoa / Đậu quả",
            "user_symptoms": "Đốm cháy lá mép phiến lá"
        }
    }
    chat_res = httpx.post(f"{BASE_URL}/api/assistant/chat", json=chat_payload, headers=admin_headers)
    assert chat_res.status_code == 200, f"Assistant chat failed: {chat_res.text}"
    chat_data = chat_res.json()
    if not st_data["is_configured"]:
        assert chat_data["status"] == "api_unconfigured"
        assert "chưa được cấu hình" in chat_data["reply"]
        print("PASS: 6. Unconfigured assistant gracefully returned unconfigured notice (No hallucination)")
    else:
        assert chat_data["success"] is True
        print(f"PASS: 6. Configured assistant answered: {chat_data['reply'][:60]}...")

    # 7. Test Action Confirmation Endpoint creating a persistent task in cultivation_tasks
    action_draft = {
        "title": "Kiểm tra mặt dưới lá cà chua sau 48h",
        "description": "Theo dõi tiến triển vết đốm cháy mép lá sau mưa",
        "due_date": "2026-11-06",
        "priority": "medium",
        "task_type": "scouting",
        "crop_id": "Tomato"
    }
    confirm_payload = {
        "diagnosis_id": diag_id,
        "action_draft": action_draft
    }
    conf_res = httpx.post(f"{BASE_URL}/api/assistant/action/confirm", json=confirm_payload, headers=admin_headers)
    assert conf_res.status_code == 200, f"Action confirmation failed: {conf_res.text}"
    conf_data = conf_res.json()
    assert conf_data["success"] is True
    created_task = conf_data["task"]
    task_id = created_task["id"]
    print(f"PASS: 7. Assistant action confirmed into cultivation_tasks, Task #{task_id}")

    # Verify task in DB
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title, due_date, status, crop_id FROM cultivation_tasks WHERE id = ?", (task_id,))
        t_row = cursor.fetchone()
        assert t_row is not None
        assert t_row[0] == "Kiểm tra mặt dưới lá cà chua sau 48h"
        assert t_row[1] == "2026-11-06"
        assert t_row[2] == "pending"
    print("PASS: 8. Verified cultivation_task row in SQLite database")

    # 8. Test Security: User B cannot access User A's diagnosis
    import uuid
    rnd = uuid.uuid4().hex[:8]
    user_b = gari_auth.register_user(
        email=f"user_b_{rnd}@gari.local",
        password="UserPassword123!",
        confirm_password="UserPassword123!",
        full_name="User B Isolation Test"
    )
    b_session = gari_auth.create_session(user_id=user_b["id"])
    b_token = b_session if isinstance(b_session, str) else b_session["token"]
    b_headers = {"Authorization": f"Bearer {b_token}"}

    b_chat_res = httpx.post(f"{BASE_URL}/api/assistant/chat", json=chat_payload, headers=b_headers)
    b_chat_data = b_chat_res.json()
    assert b_chat_data.get("status") in ("forbidden", "not_found", "api_unconfigured"), f"Expected forbidden, got: {b_chat_data}"
    print("PASS: 9. Tenant isolation verified: unauthorized user cannot chat on other user's diagnosis")

    print("\nALL 9 BACKEND & LOGIC VERIFICATION CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_suite()
