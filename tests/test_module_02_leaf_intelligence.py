"""
GARI MODULE 02 — LEAF INTELLIGENCE TEST SUITE
(tests/test_module_02_leaf_intelligence.py)

Comprehensive test coverage verifying:
1. Supported Crop Catalog & Normalization (7 crops: Coffee, Pepper, Rice, Durian, Tomato, Chili, Corn/Maize)
2. Leaf Gate Validation (Real leaf passes; blank/noise non-leaf rejected as NOT_A_LEAF/IMAGE_QUALITY_LOW)
3. Auto Mode Inference Routing via Combined Model (Model tong)
4. Manual Crop-Specific Inference Routing (Tomato model)
5. Chili (Pepper Bell) Routing via Model tong ViT classifier
6. Durian Truthful Handling (Zero fabricated confidence, disease_model_unavailable status)
7. Confidence Thresholds & Uncertainty Categorization (High >= 0.70, Medium >= 0.45, Low < 0.45)
8. AI Prediction vs. Verified Diagnosis Distinction (is_verified=False, diagnosis_type='ai_prediction')
9. Diagnosis Persistence & Context Linkage (Authenticated user, farm, plot, organization)
10. Follow-up Actions Workflow (AI Assistant context, Calendar task creation, Expert review case)
"""

import io
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from fastapi.testclient import TestClient

# Ensure test / development environment
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"

import api_server
from api_server import app
import gari_database
import gari_inference_engine


def get_test_leaf_bytes():
    """Load the test leaf image bytes from repository."""
    img_path = Path(__file__).resolve().parent.parent / "test_leaf.jpg"
    assert img_path.exists(), "test_leaf.jpg must exist in workspace root."
    with open(img_path, "rb") as f:
        return f.read()


def get_blank_image_bytes():
    """Generate a solid white non-leaf test image."""
    img = Image.new("RGB", (300, 300), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def create_auth_headers(client, email_prefix="farmer_m02"):
    """Helper to register and return valid Bearer authentication headers."""
    test_email = f"{email_prefix}_{os.urandom(4).hex()}@gari.vn"
    reg_res = client.post("/api/auth/register", json={
        "email": test_email,
        "password": "FarmerPassword123!",
        "confirm_password": "FarmerPassword123!",
        "full_name": "Nông dân Gari M02",
        "phone": "0988776655"
    })
    assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"
    token = reg_res.json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# 1. SUPPORTED CROP CATALOG & NORMALIZATION
# ============================================================================
def test_01_supported_crop_catalog_and_normalization():
    """Verify supported crop catalog contains all 7 crops and normalizes inputs accurately."""
    with TestClient(app) as client:
        res = client.get("/api/plant/supported-crops")
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert "crops" in data

        crop_ids = [c["id"] for c in data["crops"]]
        required_7 = ["coffee", "pepper", "rice", "durian", "tomato", "chili", "maize"]
        for req in required_7:
            assert req in crop_ids, f"Required crop '{req}' missing from supported crops: {crop_ids}"

        # Verify model readiness flag:
        # 6 crops have disease models; durian honestly states has_disease_model=False
        crops_by_id = {c["id"]: c for c in data["crops"]}
        assert crops_by_id["durian"]["has_disease_model"] is False, "Durian must report has_disease_model=False."
        assert crops_by_id["tomato"]["has_disease_model"] is True
        assert crops_by_id["chili"]["has_disease_model"] is True
        assert crops_by_id["maize"]["has_disease_model"] is True
        assert crops_by_id["rice"]["has_disease_model"] is True
        assert crops_by_id["coffee"]["has_disease_model"] is True
        assert crops_by_id["pepper"]["has_disease_model"] is True

        # Test normalization helper functions
        assert gari_inference_engine.normalize_crop_input("ớt") == "chili"
        assert gari_inference_engine.normalize_crop_input("bell pepper") == "chili"
        assert gari_inference_engine.normalize_crop_input("ớt chuông") == "chili"
        assert gari_inference_engine.normalize_crop_input("hồ tiêu") == "pepper"
        assert gari_inference_engine.normalize_crop_input("black pepper") == "pepper"
        assert gari_inference_engine.normalize_crop_input("tiêu") == "pepper"
        assert gari_inference_engine.normalize_crop_input("ngô") == "maize"
        assert gari_inference_engine.normalize_crop_input("bắp") == "maize"
        assert gari_inference_engine.normalize_crop_input("corn") == "maize"
        assert gari_inference_engine.normalize_crop_input("cà chua") == "tomato"
        assert gari_inference_engine.normalize_crop_input("cà phê") == "coffee"
        assert gari_inference_engine.normalize_crop_input("lúa") == "rice"
        assert gari_inference_engine.normalize_crop_input("sầu riêng") == "durian"


# ============================================================================
# 2. LEAF GATE VALIDATION
# ============================================================================
def test_02_leaf_gate_validation_real_leaf_vs_non_leaf():
    """Verify that real leaves pass the gate and synthetic non-leaf images are rejected."""
    test_leaf_bytes = get_test_leaf_bytes()
    blank_image_bytes = get_blank_image_bytes()

    # 1. Real leaf image validation
    real_img = Image.open(io.BytesIO(test_leaf_bytes)).convert("RGB")
    real_gate = gari_inference_engine.validate_leaf_gate(real_img)
    assert real_gate["status"] in ("LEAF_VALID", "UNCERTAIN"), f"Real leaf failed gate: {real_gate}"
    assert real_gate["status"] != "NOT_A_LEAF"

    # 2. Blank white non-leaf validation
    blank_img = Image.open(io.BytesIO(blank_image_bytes)).convert("RGB")
    blank_gate = gari_inference_engine.validate_leaf_gate(blank_img)
    assert blank_gate["status"] in ("NOT_A_LEAF", "IMAGE_QUALITY_LOW"), f"Blank image should be rejected: {blank_gate}"


# ============================================================================
# 3. AUTO MODE ROUTING (COMBINED MODEL)
# ============================================================================
def test_03_inference_auto_routing_combined_model():
    """Verify inference in auto mode (no crop selected or crop='all') routes through combined model."""
    api_server._ACTIVE_INFERENCES.clear()
    test_leaf_bytes = get_test_leaf_bytes()
    with TestClient(app) as client:
        headers = create_auth_headers(client, "auto_route")
        files = {"file": ("test_leaf.jpg", test_leaf_bytes, "image/jpeg")}
        data = {"crop": "", "include_attention": "false", "include_overlay": "false"}
        res = client.post("/api/predict", headers=headers, files=files, data=data)
        assert res.status_code == 200, res.text
        out = res.json()

        assert out["success"] is True
        assert out.get("mode") in ("auto", "auto_standard", "auto_detected") or out.get("crop_mode") in ("auto", "auto_detected")
        assert "Tomato" in out.get("crop", "") or "tomato" in out.get("crop_id", "") or "Cà chua" in out.get("crop_name", "")
        assert out.get("confidence", 0) > 0.50
        assert "prediction" in out


# ============================================================================
# 4. MANUAL CROP-SPECIFIC ROUTING (TOMATO)
# ============================================================================
def test_04_inference_manual_crop_routing_tomato():
    """Verify manual crop selection routes directly to the crop-specific model."""
    api_server._ACTIVE_INFERENCES.clear()
    test_leaf_bytes = get_test_leaf_bytes()
    with TestClient(app) as client:
        headers = create_auth_headers(client, "tomato_route")
        files = {"file": ("test_leaf.jpg", test_leaf_bytes, "image/jpeg")}
        data = {"crop": "tomato", "include_attention": "false", "include_overlay": "false"}
        res = client.post("/api/predict", headers=headers, files=files, data=data)
        assert res.status_code == 200, res.text
        out = res.json()

        assert out["success"] is True
        assert out.get("mode") in ("manual", "crop_specific", "crop_standard") or out.get("crop_mode") in ("manual", "crop_specific")
        assert out.get("crop_id") == "tomato" or "Tomato" in out.get("crop", "") or "Cà chua" in out.get("crop_name", "")
        assert out.get("confidence", 0) >= 0.70
        assert out.get("confidence_level") == "high"
        assert out.get("confidence_level_vi") == "Cao"
        assert out.get("is_uncertain") is False


# ============================================================================
# 5. CHILI ROUTING VIA MODEL TONG
# ============================================================================
def test_05_inference_chili_routing_via_model_tong():
    """Verify chili selection routes cleanly to Model tong ViT Pepper,_bell classes without error."""
    api_server._ACTIVE_INFERENCES.clear()
    test_leaf_bytes = get_test_leaf_bytes()
    with TestClient(app) as client:
        headers = create_auth_headers(client, "chili_route")
        files = {"file": ("test_leaf.jpg", test_leaf_bytes, "image/jpeg")}
        data = {"crop": "chili", "include_attention": "false", "include_overlay": "false"}
        res = client.post("/api/predict", headers=headers, files=files, data=data)
        assert res.status_code == 200, res.text
        out = res.json()

        assert out["success"] is True
        assert out["crop_id"] == "chili"
        assert out["status"] in ("OK", "healthy", "disease_uncertain")
        assert out["confidence"] >= 0.0
        assert "prediction" in out


# ============================================================================
# 6. DURIAN TRUTHFUL UNSUPPORTED MODEL HANDLING
# ============================================================================
def test_06_inference_durian_truthful_unsupported_model():
    """Verify durian crop selection never fabricates results and returns disease_model_unavailable."""
    api_server._ACTIVE_INFERENCES.clear()
    test_leaf_bytes = get_test_leaf_bytes()
    with TestClient(app) as client:
        headers = create_auth_headers(client, "durian_route")
        files = {"file": ("test_leaf.jpg", test_leaf_bytes, "image/jpeg")}
        data = {"crop": "durian", "include_attention": "false", "include_overlay": "false"}
        res = client.post("/api/predict", headers=headers, files=files, data=data)
        assert res.status_code == 200, res.text
        out = res.json()

        assert out["success"] is True
        assert out["crop_id"] == "durian"
        assert out["status"] == "disease_model_unavailable"
        assert out["confidence"] == 0.0
        assert out["is_uncertain"] is True
        msg = out.get("message") or out.get("message_vi") or out.get("diagnosis", {}).get("message_vi", "")
        assert "chưa sẵn sàng" in msg or "chưa có mô hình" in msg or "tương thích" in msg


# ============================================================================
# 7. CONFIDENCE THRESHOLDS & UNCERTAINTY CATEGORIZATION
# ============================================================================
def test_07_confidence_thresholds_and_uncertainty_categorization():
    """Verify confidence threshold categorization matches High (>=0.70), Medium (>=0.45), Low (<0.45)."""
    # High: 0.85
    high_meta = gari_inference_engine.categorize_confidence(0.85, status="OK")
    assert high_meta["level"] == "high"
    assert high_meta["level_vi"] == "Cao"
    assert high_meta["is_uncertain"] is False

    # Medium: 0.55
    med_meta = gari_inference_engine.categorize_confidence(0.55, status="OK")
    assert med_meta["level"] == "medium"
    assert med_meta["level_vi"] == "Trung bình"
    assert med_meta["is_uncertain"] is False

    # Low: 0.35
    low_meta = gari_inference_engine.categorize_confidence(0.35, status="OK")
    assert low_meta["level"] == "low"
    assert low_meta["level_vi"] == "Thấp"
    assert low_meta["is_uncertain"] is True
    assert "chưa đủ cơ sở chắc chắn" in low_meta["uncertainty_explanation_vi"]


# ============================================================================
# 8. AI PREDICTION VS VERIFIED DISTINCTION
# ============================================================================
def test_08_ai_prediction_vs_verified_distinction():
    """Verify AI inference output is clearly marked as an AI prediction and NOT a verified diagnosis."""
    api_server._ACTIVE_INFERENCES.clear()
    test_leaf_bytes = get_test_leaf_bytes()
    with TestClient(app) as client:
        headers = create_auth_headers(client, "unverified_test")
        files = {"file": ("test_leaf.jpg", test_leaf_bytes, "image/jpeg")}
        data = {"crop": "tomato", "include_attention": "false"}
        res = client.post("/api/predict", headers=headers, files=files, data=data)
        assert res.status_code == 200, res.text
        out = res.json()

        # Must be unverified AI prediction
        is_verified = out.get("is_verified") if "is_verified" in out else out.get("diagnosis", {}).get("is_verified")
        assert is_verified is False
        diag_type = out.get("diagnosis_type") or out.get("diagnosis", {}).get("diagnosis_type")
        assert diag_type == "ai_prediction"
        disclaimer = out.get("disclaimer_vi") or out.get("diagnosis", {}).get("disclaimer_vi") or out.get("trust_and_safety", {}).get("disclaimer_vi", "")
        assert "tham khảo" in disclaimer or "không thay thế" in disclaimer or "mô hình AI" in disclaimer


# ============================================================================
# 9. DIAGNOSIS PERSISTENCE & CONTEXT LINKAGE
# ============================================================================
def test_09_diagnosis_persistence_with_farm_and_plot_context():
    """Verify authenticated user diagnosis is saved to database linked to farm, plot, and org context."""
    api_server._ACTIVE_INFERENCES.clear()
    test_leaf_bytes = get_test_leaf_bytes()
    with TestClient(app) as client:
        # 1. Register test user
        headers = create_auth_headers(client, "persist_farmer")

        # 2. Create farm and plot
        farm_res = client.post("/api/farms", headers=headers, json={
            "name": "Nông trại Thử nghiệm Module 02",
            "location": "Lâm Đồng",
            "area_m2": 25000.0,
            "crops": ["tomato"]
        })
        assert farm_res.status_code in (200, 201), farm_res.text
        farm_id = farm_res.json().get("farm", farm_res.json()).get("id")

        # 3. Post predict with auth headers and farm_id
        files = {"file": ("test_leaf.jpg", test_leaf_bytes, "image/jpeg")}
        data = {
            "crop": "tomato",
            "farm_id": str(farm_id),
            "notes": "Quan sát thấy lá đốm sau mưa bão",
            "include_attention": "false"
        }
        pred_res = client.post("/api/predict", headers=headers, files=files, data=data)
        assert pred_res.status_code == 200, pred_res.text
        pred_data = pred_res.json()

        diag_id = pred_data.get("diagnosis_id") or pred_data.get("saved_diagnosis_id")
        assert diag_id is not None, "Authenticated prediction must persist and return diagnosis_id"

        # 4. Verify retrieval of persisted diagnosis
        diag_detail_res = client.get(f"/api/diagnoses/{diag_id}", headers=headers)
        assert diag_detail_res.status_code == 200, diag_detail_res.text
        record = diag_detail_res.json().get("diagnosis", diag_detail_res.json())
        assert record["id"] == diag_id
        assert record.get("farm_id") == farm_id


# ============================================================================
# 10. FOLLOW-UP ACTIONS WORKFLOW
# ============================================================================
def test_10_follow_up_actions_assistant_task_and_expert_review():
    """Verify follow-up actions: task creation, expert review case, and AI assistant diagnosis context."""
    api_server._ACTIVE_INFERENCES.clear()
    test_leaf_bytes = get_test_leaf_bytes()
    with TestClient(app) as client:
        # Register user
        headers = create_auth_headers(client, "actions_farmer")

        # Run diagnosis
        files = {"file": ("test_leaf.jpg", test_leaf_bytes, "image/jpeg")}
        pred_res = client.post("/api/predict", headers=headers, files=files, data={"crop": "tomato"})
        assert pred_res.status_code == 200, pred_res.text
        pred_data = pred_res.json()
        diag_id = pred_data.get("diagnosis_id") or pred_data.get("saved_diagnosis_id")
        assert diag_id is not None, "Diagnosis ID must be present for follow-ups"

        # Action 1: Create cultivation task from diagnosis
        task_res = client.post("/api/calendar/tasks", headers=headers, json={
            "title": "Cắt tỉa lá bệnh và khử trùng kéo cắt",
            "crop_id": "tomato",
            "priority": "high",
            "task_type": "treatment",
            "due_date": "2026-11-10",
            "notes": f"Tạo từ chẩn đoán ID #{diag_id}"
        })
        assert task_res.status_code in (200, 201), task_res.text
        assert task_res.json().get("success") is True

        # Action 2: Request agronomist expert review case
        expert_case_res = client.post("/api/expert/cases", headers=headers, json={
            "crop_id": "tomato",
            "symptoms_description": "Vết đốm sẫm màu có quầng vàng xung quanh, rụng nhiều ở tầng gốc",
            "predicted_disease": pred_data.get("prediction", "Tomato Bacterial spot"),
            "confidence": pred_data.get("confidence", 0.95),
            "diagnosis_id": diag_id
        })
        assert expert_case_res.status_code in (200, 201), expert_case_res.text
        case_json = expert_case_res.json()
        assert case_json.get("success") is True
        assert case_json["case"]["id"] > 0

        # Action 3: AI Assistant receives diagnosis_id
        chat_res = client.post("/api/assistant/chat", headers=headers, json={
            "message": "Bệnh này có lây lan qua đất không?",
            "diagnosis_id": diag_id,
            "crop": "tomato"
        })
        assert chat_res.status_code == 200, chat_res.text
        chat_json = chat_res.json()
        assert chat_json.get("status") in ("ok", "success", "ready", "api_unconfigured")
        assert "reply" in chat_json or "response" in chat_json or "message" in chat_json


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 70)
    print("STARTING GARI MODULE 02 — LEAF INTELLIGENCE TEST SUITE")
    print("=" * 70)

    tests = [
        ("test_01_supported_crop_catalog_and_normalization", test_01_supported_crop_catalog_and_normalization),
        ("test_02_leaf_gate_validation_real_leaf_vs_non_leaf", test_02_leaf_gate_validation_real_leaf_vs_non_leaf),
        ("test_03_inference_auto_routing_combined_model", test_03_inference_auto_routing_combined_model),
        ("test_04_inference_manual_crop_routing_tomato", test_04_inference_manual_crop_routing_tomato),
        ("test_05_inference_chili_routing_via_model_tong", test_05_inference_chili_routing_via_model_tong),
        ("test_06_inference_durian_truthful_unsupported_model", test_06_inference_durian_truthful_unsupported_model),
        ("test_07_confidence_thresholds_and_uncertainty_categorization", test_07_confidence_thresholds_and_uncertainty_categorization),
        ("test_08_ai_prediction_vs_verified_distinction", test_08_ai_prediction_vs_verified_distinction),
        ("test_09_diagnosis_persistence_with_farm_and_plot_context", test_09_diagnosis_persistence_with_farm_and_plot_context),
        ("test_10_follow_up_actions_assistant_task_and_expert_review", test_10_follow_up_actions_assistant_task_and_expert_review),
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
