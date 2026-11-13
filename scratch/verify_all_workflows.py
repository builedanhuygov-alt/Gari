import sys
import json
import time
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gari_auth
import gari_database

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("=" * 70)
    print("GARI AGRITECH AI LAB — COMPREHENSIVE END-TO-END WORKFLOW SUITE")
    print("=" * 70)

    # 1. Prepare session tokens
    user1_id = 1  # Standard Farmer / Farm Owner
    user4_id = 4  # Another user for cross-tenant IDOR tests
    token1 = gari_auth.create_session(user_id=user1_id)
    token4 = gari_auth.create_session(user_id=user4_id)

    session1 = requests.Session()
    session1.headers.update({"Authorization": f"Bearer {token1}"})
    session1.cookies.set("auth_token", token1)

    session4 = requests.Session()
    session4.headers.update({"Authorization": f"Bearer {token4}"})
    session4.cookies.set("auth_token", token4)

    # -------------------------------------------------------------------------
    # WORKFLOW A: AI Diagnosis -> Save to Farm Plot -> Recovery Timeline
    # -------------------------------------------------------------------------
    print("\n--- WORKFLOW A: AI Diagnosis -> Farm Plot -> Recovery Timeline ---")

    test_image_path = Path("test_leaf.jpg")
    if not test_image_path.exists():
        test_image_path = Path("tests/fixtures/test_leaf.jpg")

    with open(test_image_path, "rb") as img_file:
        files = {"image": ("test_leaf.jpg", img_file, "image/jpeg")}
        data = {
            "crop": "Tomato",
            "crop_name": "Tomato",
            "farm_id": "1",
            "plot_id": "12",
            "notes": "Kiểm tra lá cà chua có vết đốm sau mưa",
            "consent_store_image": "true"
        }
        resp = session1.post(f"{BASE_URL}/api/plant/diagnose", files=files, data=data)
        assert resp.status_code == 200, f"AI Diagnosis failed: {resp.status_code} {resp.text}"
        diag_res = resp.json()
        print(f" [PASS] 1. AI LeafLens Diagnosis completed:")
        print(f"         Disease: {diag_res.get('disease')} (Confidence: {diag_res.get('confidence_percent')}%)")
        print(f"         Severity: {diag_res.get('severity')} | Model: {diag_res.get('model_name')}")
        diag_id = diag_res.get("diagnosis_id") or diag_res.get("id")

    # Append recovery timeline event for Plot 12
    tl_payload = {
        "event_type": "observation",
        "diagnosis_id": diag_id,
        "monitoring_status": "monitoring",
        "notes": "Đã tiến hành xử lý cắt tỉa lá gốc bệnh và bổ sung dinh dưỡng tăng lực cho cây."
    }
    resp_tl = session1.post(f"{BASE_URL}/api/plots/12/timeline", json=tl_payload)
    assert resp_tl.status_code == 200, f"Failed to append timeline event: {resp_tl.text}"
    print(" [PASS] 2. Recovery Timeline event appended to Plot #12")

    # Query Plot 12 recovery timeline
    resp_get_tl = session1.get(f"{BASE_URL}/api/plots/12/timeline")
    assert resp_get_tl.status_code == 200, f"Failed to get timeline: {resp_get_tl.text}"
    tl_data = resp_get_tl.json().get("timeline", {})
    feed = tl_data.get("timeline_feed", [])
    assert len(feed) > 0, "Timeline feed should contain items"
    print(f" [PASS] 3. Recovery Timeline verified: {len(feed)} chronological event(s) recorded")

    # -------------------------------------------------------------------------
    # WORKFLOW B: Cultivation Task Engine & Smart Calendar
    # -------------------------------------------------------------------------
    print("\n--- WORKFLOW B: Cultivation Task Engine & Smart Calendar ---")

    # 1. Create task
    task_payload = {
        "farm_id": 1,
        "plot_id": 12,
        "crop_id": "Tomato",
        "title": "Bón phân hữu cơ vi sinh luống số 1",
        "description": "Bón gốc 200g/gốc vào buổi chiều râm mát",
        "due_date": "2026-11-10",
        "priority": "high",
        "task_type": "fertilizing",
        "notes": "Dùng phân ủ hoai mục VietGAP"
    }
    resp_task = session1.post(f"{BASE_URL}/api/calendar/tasks", json=task_payload)
    assert resp_task.status_code == 200, f"Task creation failed: {resp_task.text}"
    task = resp_task.json().get("task")
    task_id = task["id"]
    print(f" [PASS] 1. Created Cultivation Task #{task_id}: '{task['title']}' (Due: {task['due_date']})")

    # 2. List pending tasks
    resp_tasks = session1.get(f"{BASE_URL}/api/calendar/tasks?status=pending")
    assert resp_tasks.status_code == 200
    pending_tasks = resp_tasks.json().get("tasks", [])
    assert any(t["id"] == task_id for t in pending_tasks), "New task should be in pending list"
    print(f" [PASS] 2. Listed pending tasks: Found {len(pending_tasks)} pending tasks in DB")

    # 3. Complete task
    resp_comp = session1.post(f"{BASE_URL}/api/calendar/tasks/{task_id}/complete", json={"notes": "Đã hoàn thành lúc 17:30"})
    assert resp_comp.status_code == 200, f"Complete task failed: {resp_comp.text}"
    completed_task = resp_comp.json().get("task")
    assert completed_task["status"] == "completed"
    assert completed_task["completed_at"] is not None
    print(f" [PASS] 3. Completed Task #{task_id} successfully at {completed_task['completed_at']}")

    # 4. Seasonal recommendations
    resp_rec = session1.get(f"{BASE_URL}/api/calendar/recommendations?crop_id=Tomato")
    assert resp_rec.status_code == 200
    recs = resp_rec.json().get("recommendations", [])
    assert len(recs) > 0
    print(f" [PASS] 4. Seasonal Cultivation Recommendation: {recs[0]['crop_name']} - {recs[0]['stage']}")

    # -------------------------------------------------------------------------
    # WORKFLOW C: Organization Scoping & IDOR Security Isolation
    # -------------------------------------------------------------------------
    print("\n--- WORKFLOW C: Organization Scoping & IDOR Security ---")

    # User 4 tries to access User 1's plot timeline (should return 403)
    resp_idor_plot = session4.get(f"{BASE_URL}/api/plots/12/timeline")
    assert resp_idor_plot.status_code == 403, f"Expected 403 Forbidden for cross-tenant plot access, got {resp_idor_plot.status_code}"
    print(" [PASS] 1. IDOR Prevention: Cross-tenant plot timeline access returns 403 Forbidden")

    # User 4 tries to update User 1's farm (should return 403 or 404 unauthorized)
    resp_idor_farm = session4.put(f"{BASE_URL}/api/farms/1", json={"name": "Hacked Farm Name"})
    assert resp_idor_farm.status_code in (403, 404), f"Expected 403/404 for cross-tenant farm update, got {resp_idor_farm.status_code}"
    print(f" [PASS] 2. IDOR Prevention: Cross-tenant farm update blocked ({resp_idor_farm.status_code})")

    # -------------------------------------------------------------------------
    # WORKFLOW D: Regional Risk Monitoring & User Field Observations
    # -------------------------------------------------------------------------
    print("\n--- WORKFLOW D: Regional Risk Monitoring & User Field Observations ---")

    # 1. Fetch risk alerts
    resp_risk = session1.get(f"{BASE_URL}/api/risk/monitoring")
    assert resp_risk.status_code == 200
    alerts = resp_risk.json().get("alerts", [])
    assert len(alerts) > 0, "Expected risk alerts"
    print(f" [PASS] 1. Risk Alerts fetched: {len(alerts)} alerts active")
    alert_id = alerts[0]["id"]

    # 2. Acknowledge and save observation
    ack_payload = {
        "farm_id": 1,
        "plot_id": 12,
        "status": "inspecting",
        "severity_observed": "Thấp",
        "user_observation": "Đã đi rà soát kỹ các mép lá cà chua sau mưa phùn, chưa thấy nấm thán thư lây lan."
    }
    resp_ack = session1.post(f"{BASE_URL}/api/risk/alerts/{alert_id}/acknowledge", json=ack_payload)
    assert resp_ack.status_code == 200, f"Risk acknowledgment failed: {resp_ack.text}"
    print(f" [PASS] 2. Acknowledged Alert #{alert_id} with farmer's field observation")

    # 3. List acknowledgments
    resp_acks = session1.get(f"{BASE_URL}/api/risk/acknowledgments")
    assert resp_acks.status_code == 200
    acks = resp_acks.json().get("acknowledgments", [])
    assert len(acks) > 0
    print(f" [PASS] 3. Farmer observations retrieved from DB: {len(acks)} record(s)")

    # -------------------------------------------------------------------------
    # WORKFLOW E: Host System & Audit Log Verification
    # -------------------------------------------------------------------------
    print("\n--- WORKFLOW E: Host System & Audit Log Verification ---")

    # Authenticate host session
    resp_hme = session1.get(f"{BASE_URL}/api/host/me")
    assert resp_hme.status_code == 200
    assert resp_hme.json().get("success") is True
    assert resp_hme.json().get("user", {}).get("is_host_admin") is True
    print(f" [PASS] 1. Host identity verified: {resp_hme.json().get('user', {}).get('email')} (is_host_admin=True)")

    # Host overview
    resp_hov = session1.get(f"{BASE_URL}/api/host/overview")
    assert resp_hov.status_code == 200
    hov = resp_hov.json()
    assert hov.get("success") is True
    models_summary = hov.get("ai_models_summary", {})
    assert models_summary.get("total_crop_models", 0) > 0
    print(f" [PASS] 2. Host telemetry verified: {models_summary.get('total_crop_models')} AI models ready ({models_summary.get('status')})")

    # Notification Mark All Read
    resp_notif = session1.post(f"{BASE_URL}/api/notifications/mark-all-read")
    assert resp_notif.status_code == 200
    print(f" [PASS] 3. Notification mark-all-read executed successfully")

    print("\n" + "=" * 70)
    print("ALL 5 END-TO-END WORKFLOWS (A, B, C, D, E) PASSED WITH ZERO ERRORS!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
