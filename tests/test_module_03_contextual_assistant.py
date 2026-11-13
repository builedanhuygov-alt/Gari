"""
GARI MODULE 03 — CONTEXTUAL AI ASSISTANT TEST SUITE
(tests/test_module_03_contextual_assistant.py)

Comprehensive test coverage verifying:
1. Diagnosis Grounding & Context Retention (Multi-turn chat bound to diagnosis record)
2. Context Authorization & Isolation (User B cannot access User A's private diagnosis -> 403 Forbidden)
3. Uncertainty & Evidence Differentiation (Low confidence < 0.45 / uncertain status flagged truthfully)
4. Missing Information Inquiry (Proactively asks for missing field observations when needed)
5. Safety, Non-Guarantee & IPM Compliance (No 100% cure claims, no trademarked chemical prescriptions)
6. Agronomic Citations & Knowledge Grounding (PPRI, GARI IPM Lab, FAO references)
7. Actionable Proposals to Cultivation Task Confirmation (/api/assistant/action/confirm)
8. Expert Review Escalation from Assistant (/api/assistant/expert/escalate)
9. Provider Failure & Unconfigured Handling (Truthful api_unconfigured and api_error without hallucination)
10. Host Console Assistant Management (Host Admin can view, update, and test AI Provider config; non-hosts blocked)
"""

import io
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

# Ensure test / development environment
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"

import api_server
from api_server import app
import gari_database
import gari_assistant


def get_test_leaf_bytes():
    """Load the test leaf image bytes from repository."""
    img_path = Path(__file__).resolve().parent.parent / "test_leaf.jpg"
    assert img_path.exists(), "test_leaf.jpg must exist in workspace root."
    with open(img_path, "rb") as f:
        return f.read()


def create_auth_headers(client, email_prefix="farmer_m03"):
    """Helper to register and return valid Bearer authentication headers and user info."""
    test_email = f"{email_prefix}_{os.urandom(4).hex()}@gari.vn"
    reg_res = client.post("/api/auth/register", json={
        "email": test_email,
        "password": "FarmerPassword123!",
        "confirm_password": "FarmerPassword123!",
        "full_name": "Nông dân Gari M03",
        "phone": "0988776655"
    })
    assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"
    data = reg_res.json()
    token = data["token"]
    user = data["user"]
    return {"Authorization": f"Bearer {token}"}, user


def create_host_admin_headers(client):
    """Helper to create or elevate a user to Host Admin and return headers."""
    headers, user = create_auth_headers(client, "host_admin_m03")
    user_id = user["id"]
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_host_admin = 1 WHERE id = ?", (user_id,))
        conn.commit()
    return headers, user_id


def setup_mock_assistant_provider():
    """Configure the assistant provider to 'mock' in host_api_config for offline test stability."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO host_api_config (key, value, description, updated_at)
            VALUES ('assistant_provider', 'mock', 'Test Mock Provider', CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = 'mock', updated_at = CURRENT_TIMESTAMP
        """)
        cursor.execute("""
            INSERT INTO host_api_config (key, value, description, updated_at)
            VALUES ('assistant_citations_enabled', '1', 'Test Citations', CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = '1', updated_at = CURRENT_TIMESTAMP
        """)
        conn.commit()


# ============================================================================
# 1. DIAGNOSIS GROUNDING & CONTEXT RETENTION
# ============================================================================
def test_01_diagnosis_grounding_and_context_retention():
    """Verify chat is bound to diagnosis context and retains history over multiple turns."""
    setup_mock_assistant_provider()
    api_server._ACTIVE_INFERENCES.clear()
    test_leaf = get_test_leaf_bytes()

    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "grounding_user")

        # Step 1: Create a diagnosis record
        pred_res = client.post("/api/predict", headers=headers, files={"file": ("test_leaf.jpg", test_leaf, "image/jpeg")}, data={"crop": "tomato"})
        assert pred_res.status_code == 200, pred_res.text
        diag_id = pred_res.json().get("diagnosis_id") or pred_res.json().get("saved_diagnosis_id")
        assert diag_id is not None

        # Step 2: Turn 1 Chat query
        turn1_res = client.post("/api/assistant/chat", headers=headers, json={
            "diagnosis_id": diag_id,
            "message": "Bệnh này phát sinh do nguyên nhân gì và có lây sang cây khác không?",
            "crop": "tomato"
        })
        assert turn1_res.status_code == 200, turn1_res.text
        turn1_data = turn1_res.json()
        assert turn1_data["success"] is True
        assert turn1_data["status"] == "ready"
        assert "Cà chua" in turn1_data["reply"] or "Tomato" in turn1_data["reply"]
        assert len(turn1_data["reply"]) > 50

        # Step 3: Turn 2 Follow-up query retaining history
        history = [
            {"role": "user", "content": "Bệnh này phát sinh do nguyên nhân gì?"},
            {"role": "assistant", "content": turn1_data["reply"]}
        ]
        turn2_res = client.post("/api/assistant/chat", headers=headers, json={
            "diagnosis_id": diag_id,
            "message": "Tôi nên kiểm tra những vị trí nào trên cây để chắc chắn?",
            "conversation_history": history
        })
        assert turn2_res.status_code == 200, turn2_res.text
        turn2_data = turn2_res.json()
        assert turn2_data["success"] is True
        assert len(turn2_data["reply"]) > 50

        # Step 4: Verify conversation history endpoint
        hist_res = client.get(f"/api/assistant/history/{diag_id}", headers=headers)
        assert hist_res.status_code == 200, hist_res.text
        hist_data = hist_res.json()
        assert hist_data["success"] is True
        assert len(hist_data["history"]) >= 2


# ============================================================================
# 2. CONTEXT AUTHORIZATION & ISOLATION
# ============================================================================
def test_02_context_authorization_and_isolation():
    """Verify context is strictly checked for authorization; User B cannot access User A's diagnosis."""
    setup_mock_assistant_provider()
    api_server._ACTIVE_INFERENCES.clear()
    test_leaf = get_test_leaf_bytes()

    with TestClient(app) as client:
        # User A creates a diagnosis
        headers_a, user_a = create_auth_headers(client, "user_a")
        pred_res = client.post("/api/predict", headers=headers_a, files={"file": ("test_leaf.jpg", test_leaf, "image/jpeg")}, data={"crop": "tomato"})
        assert pred_res.status_code == 200
        diag_id_a = pred_res.json().get("diagnosis_id") or pred_res.json().get("saved_diagnosis_id")

        # User B attempts to access User A's diagnosis context
        headers_b, user_b = create_auth_headers(client, "user_b")
        unauth_chat = client.post("/api/assistant/chat", headers=headers_b, json={
            "diagnosis_id": diag_id_a,
            "message": "Cho tôi biết thông tin bệnh của nông trại này."
        })
        assert unauth_chat.status_code == 403, f"Expected 403 Forbidden, got {unauth_chat.status_code}: {unauth_chat.text}"
        assert "quyền" in unauth_chat.text.lower() or "forbidden" in unauth_chat.text.lower()


# ============================================================================
# 3. UNCERTAINTY & EVIDENCE DIFFERENTIATION
# ============================================================================
def test_03_uncertainty_and_evidence_differentiation():
    """Verify that when confidence is low or uncertain, assistant explicitly warns and does not claim certainty."""
    setup_mock_assistant_provider()
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "uncertain_user")

        # Create an artificial low-confidence diagnosis record in DB
        diag_record = gari_database.save_diagnosis({
            "crop_id": "tomato",
            "crop_name": "Cà chua",
            "predicted_disease": "Đốm lá chưa rõ nguyên nhân",
            "disease_name_vi": "Đốm lá chưa rõ nguyên nhân",
            "confidence": 0.32,
            "confidence_percent": 32.0,
            "severity": "UNCERTAIN",
            "diagnosis_status": "needs_review",
            "is_uncertain": True,
            "model_name": "ConvNeXt-Small",
            "uncertainty_explanation_vi": "Độ tin cậy của mô hình dưới 45%."
        }, user_id=user["id"])
        low_diag_id = diag_record["id"]

        chat_res = client.post("/api/assistant/chat", headers=headers, json={
            "diagnosis_id": low_diag_id,
            "message": "Cây của tôi bị bệnh gì vậy, có chắc chắn không?"
        })
        assert chat_res.status_code == 200, chat_res.text
        reply = chat_res.json()["reply"]

        # Must explicitly acknowledge low confidence or uncertainty
        assert "độ tin cậy thấp" in reply.lower() or "chưa đủ cơ sở" in reply.lower() or "32" in reply
        # Must not fabricate 100% certainty
        assert "chắc chắn 100%" not in reply.lower()


# ============================================================================
# 4. MISSING INFORMATION INQUIRY
# ============================================================================
def test_04_missing_information_inquiry():
    """Verify assistant asks for missing field observations when context lacks detailed symptoms."""
    setup_mock_assistant_provider()
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "missing_info_user")

        # Save diagnosis with no symptoms or conditions
        diag_record = gari_database.save_diagnosis({
            "crop_id": "tomato",
            "crop_name": "Cà chua",
            "predicted_disease": "Bệnh nghi vấn",
            "disease_name_vi": "Bệnh nghi vấn",
            "confidence": 0.40,
            "is_uncertain": True,
            "user_symptoms": "",
            "field_conditions": ""
        }, user_id=user["id"])

        chat_res = client.post("/api/assistant/chat", headers=headers, json={
            "diagnosis_id": diag_record["id"],
            "message": "Tôi cần làm gì tiếp theo?"
        })
        assert chat_res.status_code == 200, chat_res.text
        reply = chat_res.json()["reply"]

        # Checks for inquiry keywords (mặt dưới lá, mốc, tầng lá, thời tiết)
        assert "?" in reply
        assert any(k in reply.lower() for k in ["mặt dưới", "lá non", "lá già", "triệu chứng", "thực địa", "thời tiết"])


# ============================================================================
# 5. SAFETY, NON-GUARANTEE & IPM COMPLIANCE
# ============================================================================
def test_05_safety_non_guarantee_and_ipm():
    """Verify assistant prioritizes cultural/IPM practices and avoids guaranteed cure promises."""
    setup_mock_assistant_provider()
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "ipm_user")
        diag = gari_database.save_diagnosis({
            "crop_id": "tomato",
            "crop_name": "Cà chua",
            "predicted_disease": "Tomato Bacterial spot",
            "disease_name_vi": "Bệnh đốm vi khuẩn",
            "confidence": 0.92
        }, user_id=user["id"])

        chat_res = client.post("/api/assistant/chat", headers=headers, json={
            "diagnosis_id": diag["id"],
            "message": "Tôi có nên phun thuốc diệt sạch 100% ngay không?",
            "deep_dive": True
        })
        assert chat_res.status_code == 200
        reply = chat_res.json()["reply"]

        # Should never guarantee 100% cure
        assert "cam kết 100%" not in reply.lower()
        # Should emphasize sanitation, cultural or biological controls
        assert any(k in reply.lower() for k in ["vệ sinh", "tỉa", "khảo sát", "sinh học", "bảo vệ thực vật", "lộ trình"])


# ============================================================================
# 6. AGRONOMIC CITATIONS & KNOWLEDGE GROUNDING
# ============================================================================
def test_06_agronomic_citations_and_knowledge_grounding():
    """Verify assistant response provides reliable citations when citations are enabled."""
    setup_mock_assistant_provider()
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "citations_user")
        diag = gari_database.save_diagnosis({
            "crop_id": "tomato",
            "crop_name": "Cà chua",
            "predicted_disease": "Tomato Bacterial spot",
            "disease_name_vi": "Bệnh đốm vi khuẩn",
            "confidence": 0.88
        }, user_id=user["id"])

        chat_res = client.post("/api/assistant/chat", headers=headers, json={
            "diagnosis_id": diag["id"],
            "message": "Thông tin này dựa trên căn cứ khoa học nào?"
        })
        assert chat_res.status_code == 200
        reply = chat_res.json()["reply"]

        # Citations presence check
        assert any(cite in reply for cite in ["Viện Bảo vệ Thực vật", "PPRI", "GARI IPM Lab", "QCVN", "FAO"])


# ============================================================================
# 7. ACTIONABLE PROPOSALS TO CULTIVATION TASK CONFIRMATION
# ============================================================================
def test_07_actionable_proposals_to_task_confirmation():
    """Verify assistant action draft can be confirmed and converted into a persistent task."""
    setup_mock_assistant_provider()
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "task_user")
        diag = gari_database.save_diagnosis({
            "crop_id": "tomato",
            "crop_name": "Cà chua",
            "predicted_disease": "Tomato Early blight",
            "disease_name_vi": "Bệnh cháy lá sớm",
            "confidence": 0.89
        }, user_id=user["id"])

        # Run chat to get action draft
        chat_res = client.post("/api/assistant/chat", headers=headers, json={
            "diagnosis_id": diag["id"],
            "message": "Tôi cần lịch trình kiểm tra như thế nào?"
        })
        assert chat_res.status_code == 200
        data = chat_res.json()
        assert "actions" in data
        assert len(data["actions"]) >= 1
        action_draft = data["actions"][0]

        # Confirm action draft into persistent cultivation task
        confirm_res = client.post("/api/assistant/action/confirm", headers=headers, json={
            "diagnosis_id": diag["id"],
            "action_draft": action_draft
        })
        assert confirm_res.status_code in (200, 201), confirm_res.text
        confirm_data = confirm_res.json()
        assert confirm_data["success"] is True
        assert confirm_data["task"]["id"] > 0
        assert "cháy lá sớm" in confirm_data["task"].get("notes", "").lower() or "chẩn đoán" in confirm_data["task"].get("notes", "").lower()


# ============================================================================
# 8. EXPERT REVIEW ESCALATION FROM ASSISTANT
# ============================================================================
def test_08_expert_review_escalation_from_assistant():
    """Verify user can escalate from Assistant chat directly to an Agronomist Expert review case."""
    setup_mock_assistant_provider()
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "escalate_user")
        diag = gari_database.save_diagnosis({
            "crop_id": "tomato",
            "crop_name": "Cà chua",
            "predicted_disease": "Tomato Septoria leaf spot",
            "disease_name_vi": "Đốm lá Septoria",
            "confidence": 0.78
        }, user_id=user["id"])

        escalate_res = client.post("/api/assistant/expert/escalate", headers=headers, json={
            "diagnosis_id": diag["id"],
            "symptoms_description": "Vết bệnh xuất hiện dày đặc sau đợt sương mù kéo dài, lá vàng rụng nhanh."
        })
        assert escalate_res.status_code == 200, escalate_res.text
        esc_data = escalate_res.json()
        assert esc_data["success"] is True
        assert esc_data["case_id"] > 0
        assert esc_data["case"]["predicted_disease"] == "Đốm lá Septoria"


# ============================================================================
# 9. PROVIDER FAILURE & UNCONFIGURED HANDLING
# ============================================================================
def test_09_provider_failure_and_unconfigured_handling():
    """Verify explicit unconfigured and provider failure states without fabricated answers."""
    with TestClient(app) as client:
        headers, user = create_auth_headers(client, "provider_fail_user")
        diag = gari_database.save_diagnosis({"crop_id": "tomato", "confidence": 0.90}, user_id=user["id"])

        # Case 1: Provider is explicitly disabled
        with gari_database.get_connection() as conn:
            conn.execute("UPDATE host_api_config SET value = 'disabled' WHERE key = 'assistant_provider'")
            conn.commit()

        unconf_res = client.post("/api/assistant/chat", headers=headers, json={
            "diagnosis_id": diag["id"],
            "message": "Trợ lý có hoạt động không?"
        })
        assert unconf_res.status_code == 200
        unconf_data = unconf_res.json()
        assert unconf_data["success"] is False
        assert unconf_data["status"] == "api_unconfigured"
        assert "chưa được cấu hình" in unconf_data["reply"]

        # Case 2: Provider error simulation (invalid external endpoint or key)
        with gari_database.get_connection() as conn:
            conn.execute("UPDATE host_api_config SET value = 'openai_compatible' WHERE key = 'assistant_provider'")
            conn.execute("UPDATE host_api_config SET value = 'sk-invalid-test-key-9999' WHERE key = 'assistant_api_key'")
            conn.execute("UPDATE host_api_config SET value = 'http://127.0.0.1:1/invalid' WHERE key = 'assistant_base_url'")
            conn.execute("UPDATE host_api_config SET value = '0.5' WHERE key = 'assistant_timeout_sec'")
            conn.commit()

        fail_res = client.post("/api/assistant/chat", headers=headers, json={
            "diagnosis_id": diag["id"],
            "message": "Có kết nối được không?"
        })
        assert fail_res.status_code == 200
        fail_data = fail_res.json()
        assert fail_data["success"] is False
        assert fail_data["status"] == "api_error"
        assert "không thể kết nối" in fail_data["reply"].lower() or "quá tải" in fail_data["reply"].lower()

        # Restore to mock provider
        setup_mock_assistant_provider()


# ============================================================================
# 10. HOST CONSOLE ASSISTANT MANAGEMENT
# ============================================================================
def test_10_host_console_assistant_management():
    """Verify Host Admin can query, update, and test Assistant provider config, while non-hosts are blocked."""
    with TestClient(app) as client:
        # 1. Non-host user attempt is blocked
        user_headers, user = create_auth_headers(client, "regular_user")
        blocked_get = client.get("/api/host/assistant/config", headers=user_headers)
        assert blocked_get.status_code == 403

        # 2. Host Admin queries assistant config
        host_headers, host_id = create_host_admin_headers(client)
        cfg_res = client.get("/api/host/assistant/config", headers=host_headers)
        assert cfg_res.status_code == 200, cfg_res.text
        cfg_data = cfg_res.json()
        assert cfg_data["success"] is True
        assert "config" in cfg_data
        assert "available_providers" in cfg_data

        # 3. Host Admin updates assistant config
        update_res = client.post("/api/host/assistant/config", headers=host_headers, json={
            "provider": "mock",
            "model": "gari-agri-mock-v1",
            "temperature": 0.15,
            "citations_enabled": True,
            "deep_dive_enabled": True,
            "reason": "Chuyển sang Mock Provider cho kiểm thử tự động"
        })
        assert update_res.status_code == 200, update_res.text
        assert update_res.json()["success"] is True

        # 4. Host Admin tests provider connectivity
        test_res = client.post("/api/host/assistant/test", headers=host_headers, json={
            "provider": "mock",
            "model": "gari-agri-mock-v1"
        })
        assert test_res.status_code == 200, test_res.text
        test_data = test_res.json()
        assert test_data["success"] is True
        assert test_data["status"] == "connected"
        assert test_data["latency_ms"] >= 0.0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 70)
    print("STARTING GARI MODULE 03 — CONTEXTUAL AI ASSISTANT TEST SUITE")
    print("=" * 70)

    tests = [
        ("test_01_diagnosis_grounding_and_context_retention", test_01_diagnosis_grounding_and_context_retention),
        ("test_02_context_authorization_and_isolation", test_02_context_authorization_and_isolation),
        ("test_03_uncertainty_and_evidence_differentiation", test_03_uncertainty_and_evidence_differentiation),
        ("test_04_missing_information_inquiry", test_04_missing_information_inquiry),
        ("test_05_safety_non_guarantee_and_ipm", test_05_safety_non_guarantee_and_ipm),
        ("test_06_agronomic_citations_and_knowledge_grounding", test_06_agronomic_citations_and_knowledge_grounding),
        ("test_07_actionable_proposals_to_task_confirmation", test_07_actionable_proposals_to_task_confirmation),
        ("test_08_expert_review_escalation_from_assistant", test_08_expert_review_escalation_from_assistant),
        ("test_09_provider_failure_and_unconfigured_handling", test_09_provider_failure_and_unconfigured_handling),
        ("test_10_host_console_assistant_management", test_10_host_console_assistant_management),
    ]

    passed = 0
    for name, fn in tests:
        print(f"\n[RUNNING] {name}...")
        try:
            fn()
            print(f"[PASS] {name} ✓")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed}/{len(tests)} TESTS PASSED ({int(passed/len(tests)*100)}%)")
    print("=" * 70)
    if passed != len(tests):
        sys.exit(1)
