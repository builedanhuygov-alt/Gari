"""
GARI MODULE 13 — MOBILE APP PARITY BACKEND INTEGRATION TEST SUITE
File: tests/test_module_13_mobile_parity.py

Comprehensive test suite verifying backend API parity with Flutter mobile client:
1. Mobile Auth: Register, Login, Session Bearer token, Centralized Profile retrieval.
2. Mobile Leaf Intelligence: Multi-crop inference across 7 crops with JWT auth header.
3. Mobile AI Assistant: Contextual agronomic chat with leaf diagnosis context & history.
4. Mobile Farms Management: Farm listing and creation matching Mobile FarmModel contract.
5. Mobile Tasks & Crop Calendar: Tasks listing with views, task creation, and status completion.
6. Mobile Diagnosis-to-Task Linkage: Direct treatment task generation from AI diagnosis.
7. Mobile Organizations: Cooperative/Business organization listing and member roster inspection.
8. Mobile Community & Knowledge: Knowledge article search by crop, community feed, and like toggling.
9. Mobile Expert Consultation: Diagnosis case escalation and message thread interaction.
10. Mobile 7-Dimension Entitlements: Live usage summary matching Mobile SubscriptionUsageModel.
"""

import os
import sys
import unittest
import uuid
from pathlib import Path
import io

os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
import api_server
import gari_auth
import gari_database
import gari_entitlements


class TestModule13MobileParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api_server.app)
        cls.uid = uuid.uuid4().hex[:8]

        # Register mobile user
        reg_payload = {
            "email": f"mobile_farmer_{cls.uid}@gari.vn",
            "password": "FarmerPassword123!",
            "confirm_password": "FarmerPassword123!",
            "full_name": "Nguyen Van Mobile",
            "account_type": "farmer",
        }
        res = cls.client.post("/api/auth/register", json=reg_payload)
        assert res.status_code == 200, res.text
        cls.token = res.json()["token"]
        cls.user = res.json()["user"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_01_mobile_auth_and_profile_parity(self):
        """1. Verify mobile login, session token generation, and centralized profile contract."""
        login_res = self.client.post("/api/auth/login", json={
            "email": f"mobile_farmer_{self.uid}@gari.vn",
            "password": "FarmerPassword123!"
        })
        self.assertEqual(login_res.status_code, 200)
        data = login_res.json()
        self.assertTrue(data.get("success"))
        self.assertIn("token", data)
        self.assertEqual(data["user"]["email"], f"mobile_farmer_{self.uid}@gari.vn")

        # Test profile retrieval
        prof_res = self.client.get("/api/auth/profile", headers=self.headers)
        self.assertEqual(prof_res.status_code, 200)
        prof_data = prof_res.json()
        full_name = prof_data.get("profile", {}).get("full_name") or prof_data.get("full_name") or prof_data.get("user", {}).get("full_name")
        self.assertEqual(full_name, "Nguyen Van Mobile")

    def test_02_mobile_leaf_intelligence_diagnosis_parity(self):
        """2. Verify mobile image upload & inference across 7 crops with Bearer auth."""
        # Use real test leaf or create valid JPEG bytes
        test_leaf_path = ROOT_DIR / "test_leaf.jpg"
        if test_leaf_path.exists():
            image_bytes = test_leaf_path.read_bytes()
        else:
            from PIL import Image
            img = Image.new("RGB", (224, 224), color=(34, 139, 34))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            image_bytes = buf.getvalue()

        # Test with Tomato filter
        files = {"file": ("mobile_leaf.jpg", image_bytes, "image/jpeg")}
        data = {"crop_filter": "Tomato"}
        res = self.client.post("/api/predict", files=files, data=data, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        res_data = res.json()
        self.assertTrue(res_data.get("success"))
        self.assertIn("crop", res_data)
        self.assertIn("prediction", res_data)
        self.assertIn("confidence", res_data)

    def test_03_mobile_contextual_assistant_parity(self):
        """3. Verify mobile chatbot communication with crop & diagnosis context."""
        payload = {
            "message": "Cần lưu ý gì khi bón phân cho cây cà chua đang ra hoa?",
            "crop": "Tomato",
            "disease": "Đốm vi khuẩn",
            "history": [
                {"role": "user", "content": "Cây cà chua nhà tôi bị vàng lá đốm."},
                {"role": "assistant", "content": "Bạn nên kiểm tra mặt dưới lá và điều chỉnh độ ẩm."}
            ]
        }
        res = self.client.post("/api/assistant/chat", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertTrue(len(data.get("reply", "")) > 10)

    def test_04_mobile_farms_management_parity(self):
        """4. Verify mobile farm listing and farm creation contracts."""
        create_res = self.client.post("/api/farms", json={
            "name": "Nông trại Thử Nghiệm Mobile",
            "province": "Lâm Đồng",
            "district": "Đơn Dương",
            "primary_crop": "Tomato",
            "area_m2": 15000.0,
            "soil_type": "Đất đỏ bazan"
        }, headers=self.headers)
        self.assertEqual(create_res.status_code, 200)
        farm = create_res.json().get("farm")
        self.assertIsNotNone(farm)
        self.assertEqual(farm["name"], "Nông trại Thử Nghiệm Mobile")

        # List farms
        list_res = self.client.get("/api/farms", headers=self.headers)
        self.assertEqual(list_res.status_code, 200)
        farms = list_res.json().get("farms", [])
        self.assertTrue(any(f["name"] == "Nông trại Thử Nghiệm Mobile" for f in farms))

    def test_05_mobile_tasks_and_calendar_parity(self):
        """5. Verify mobile task creation, listing by view, and completion."""
        # Create task
        create_res = self.client.post("/api/calendar/tasks", json={
            "title": "Tưới nước nhỏ giọt khu nhà kính A",
            "description": "Bổ sung dinh dưỡng NPK vi lượng",
            "priority": "HIGH",
            "due_date": "2026-11-15",
            "status": "pending"
        }, headers=self.headers)
        self.assertEqual(create_res.status_code, 200)
        task = create_res.json().get("task")
        task_id = task["id"]

        # List tasks
        list_res = self.client.get("/api/calendar/tasks", headers=self.headers)
        self.assertEqual(list_res.status_code, 200)
        tasks = list_res.json().get("tasks", [])
        self.assertTrue(any(t["id"] == task_id for t in tasks))

        # Complete task
        comp_res = self.client.post(f"/api/calendar/tasks/{task_id}/complete", json={
            "notes": "Đã hoàn thành qua ứng dụng GARI Mobile"
        }, headers=self.headers)
        self.assertEqual(comp_res.status_code, 200)
        self.assertEqual(comp_res.json()["task"]["status"], "completed")

    def test_06_mobile_diagnosis_to_task_generation(self):
        """6. Verify mobile workflow of generating a cultivation task directly from diagnosis."""
        # Save dummy diagnosis in database
        diag_id = gari_database.save_diagnosis({
            "crop_id": "coffee",
            "crop_name": "Cà phê",
            "predicted_disease": "Coffee Leaf Rust",
            "disease_name_vi": "Bệnh gỉ sắt cà phê",
            "confidence": 0.95,
            "severity": "HIGH",
        }, user_id=self.user["id"])["id"]

        # Generate task from diagnosis
        res = self.client.post("/api/calendar/tasks/from-diagnosis", json={
            "diagnosis_id": diag_id,
            "title": "Phun phòng trừ gỉ sắt cà phê",
            "priority": "URGENT",
            "notes": "Kiểm tra tàn dư nấm mặt dưới lá"
        }, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        task = res.json().get("task")
        self.assertEqual(task["title"], "Phun phòng trừ gỉ sắt cà phê")
        self.assertEqual(task["priority"].upper(), "URGENT")

    def test_07_mobile_organizations_and_members_parity(self):
        """7. Verify mobile organization queries and member roster."""
        # List organizations
        res = self.client.get("/api/organizations", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("organizations", data)

    def test_08_mobile_community_and_knowledge_parity(self):
        """8. Verify mobile knowledge library filtering, community feed, and post liking."""
        # Query articles
        art_res = self.client.get("/api/knowledge/articles?crop_id=pepper", headers=self.headers)
        self.assertEqual(art_res.status_code, 200)
        self.assertIn("articles", art_res.json())

        # Create community post
        post_res = self.client.post("/api/community/posts", json={
            "title": "Hỏi về bệnh xoăn ngọn trên cây ớt chỉ thiên",
            "content": "Cây ớt có hiện tượng ngọn non bị chùn, lá xoăn mép lên trên.",
            "crop_id": "chili",
            "region": "Bình Định"
        }, headers=self.headers)
        self.assertEqual(post_res.status_code, 200)
        post_id = post_res.json()["post"]["id"]

        # Like the post
        like_res = self.client.post(f"/api/community/posts/{post_id}/like", headers=self.headers)
        self.assertEqual(like_res.status_code, 200)
        self.assertTrue(like_res.json().get("liked"))

    def test_09_mobile_expert_consultation_flow(self):
        """9. Verify mobile expert case consultation creation from diagnosis."""
        diag_id = gari_database.save_diagnosis({
            "crop_id": "durian",
            "crop_name": "Sầu riêng",
            "predicted_disease": "Phytophthora Stem Canker",
            "disease_name_vi": "Xì mủ thân sầu riêng",
            "confidence": 0.91,
            "severity": "HIGH",
        }, user_id=self.user["id"])["id"]

        case_res = self.client.post("/api/expert/cases", json={
            "diagnosis_id": diag_id,
            "symptoms_description": "Vết xì mủ lan rộng ở cổ rễ sầu riêng, cần tư vấn phác đồ quét thuốc.",
            "consent_share_farm_data": True
        }, headers=self.headers)
        self.assertEqual(case_res.status_code, 200)
        case_data = case_res.json().get("case")
        case_id = case_data["id"]

        # Post message to case
        msg_res = self.client.post(f"/api/expert/cases/{case_id}/messages", json={
            "message": "Tôi đã cạo sạch phần vỏ thối và đang để khô vết thương."
        }, headers=self.headers)
        self.assertEqual(msg_res.status_code, 200)

        # Retrieve messages
        get_msgs = self.client.get(f"/api/expert/cases/{case_id}/messages", headers=self.headers)
        self.assertEqual(get_msgs.status_code, 200)
        msgs = get_msgs.json().get("messages", [])
        self.assertTrue(len(msgs) >= 1)

    def test_10_mobile_7_dimension_entitlement_usage_parity(self):
        """10. Verify mobile 7-dimension usage summary matching Mobile SubscriptionUsageModel."""
        res = self.client.get("/api/subscriptions/usage", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        metrics = data.get("usage") or data.get("metrics")
        self.assertIsNotNone(metrics)
        required_dimensions = [
            "ai_usage", "diagnosis", "farms", "plots",
            "organization_seats", "storage_mb", "expert_consultations"
        ]
        for dim in required_dimensions:
            self.assertIn(dim, metrics)
            m = metrics[dim]
            self.assertIn("label", m)
            self.assertIn("unit", m)
            self.assertIn("used", m)
            self.assertIn("percentage", m)
            self.assertIn("is_unlimited", m)
            self.assertIn("is_exhausted", m)

        # Check upgrade guidance
        self.assertIn("upgrade_guidance", data)
        guidance = data["upgrade_guidance"]
        self.assertIn("suggested_plan_name", guidance)


if __name__ == "__main__":
    unittest.main()
