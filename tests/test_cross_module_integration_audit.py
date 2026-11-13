"""
GARI — CROSS-MODULE INTEGRATION & QUALITY AUDIT SUITE
File: tests/test_cross_module_integration_audit.py

Authoritative end-to-end integration tests tracing all 8 core workflows:
1. Leaf Image Upload → Diagnosis → Result → AI Explanation → Saved History.
2. Diagnosis → Create Task → Assign Task → Complete Task → Activity History.
3. Personal User → Create Organization → Invite Member → Assign Farm Access.
4. Organization Member → Diagnose a Crop → Create Task → Owner Sees Activity.
5. User → Request Expert Consultation → Consent → Expert Assignment → Response → Closure.
6. Subscription Change → Entitlement Update → Backend Limit Enforcement → UI Telemetry.
7. Host Admin → Update AI Provider Configuration → Backend Provider Adapter Uses Config.
8. Web Action → Mobile Reflects The Same Persisted Backend Data.
"""

import io
import os
import sys
import unittest
import uuid
from pathlib import Path

os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_PUBLIC_CHECKOUT_ENABLED"] = "1"

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
import api_server
import gari_auth
import gari_database
import gari_b2b
import gari_tasks
import gari_experts
import gari_entitlements
import gari_host_service
import gari_assistant


class TestCrossModuleIntegrationAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(api_server.app)

        # Helper to create test users
        cls.farmer_user, cls.farmer_token, cls.farmer_headers = cls._register_user("farmer")
        cls.pro_user, cls.pro_token, cls.pro_headers = cls._register_user("pro_user")
        gari_entitlements.assign_subscription("user", cls.pro_user["id"], "pro")

        cls.owner_user, cls.owner_token, cls.owner_headers = cls._register_user("owner_user")
        gari_entitlements.assign_subscription("user", cls.owner_user["id"], "organization")

        cls.member_user, cls.member_token, cls.member_headers = cls._register_user("member_user")
        cls.expert_user, cls.expert_token, cls.expert_headers = cls._register_user("expert_user", is_expert=True)

        cls.host_admin_user, cls.host_admin_token, cls.host_admin_headers = cls._register_user("host_admin", is_host_admin=True)

    @classmethod
    def _register_user(cls, prefix: str, is_host_admin: bool = False, is_expert: bool = False):
        uid = uuid.uuid4().hex[:8]
        email = f"{prefix}_{uid}@gari.vn"
        password = "AuditedPassword123!"
        res = cls.client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "full_name": f"User {prefix.capitalize()}",
            "account_type": "expert" if is_expert else ("admin" if is_host_admin else "farmer"),
        })
        assert res.status_code == 200, res.text
        data = res.json()
        token = data["token"]
        user = data["user"]

        if is_host_admin or is_expert:
            with gari_database.get_connection() as conn:
                cur = conn.cursor()
                if is_host_admin:
                    cur.execute("UPDATE users SET is_host_admin = 1, is_admin = 1 WHERE id = ?", (user["id"],))
                if is_expert:
                    cur.execute("UPDATE users SET is_expert = 1, account_type = 'expert' WHERE id = ?", (user["id"],))
                    cur.execute("""
                        INSERT INTO expert_profiles (user_id, full_name, display_title, institution, specialization, primary_crops_json, farming_regions_json, is_active, status, verification_status)
                        VALUES (?, ?, 'ThS. Nông Học', 'Viện BVTV', 'Bảo vệ thực vật', '["Tomato", "Coffee"]', '["Tây Nguyên"]', 1, 'active', 'verified')
                    """, (user["id"], user["full_name"]))
                conn.commit()

        return user, token, {"Authorization": f"Bearer {token}"}

    def _get_test_leaf_bytes(self) -> bytes:
        test_path = ROOT_DIR / "test_leaf.jpg"
        if test_path.exists():
            return test_path.read_bytes()
        from PIL import Image
        img = Image.new("RGB", (224, 224), color=(34, 139, 34))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    def test_workflow_01_leaf_diagnosis_ai_explanation_history(self):
        """Workflow 1: Leaf image upload → diagnosis → result → AI explanation → saved history."""
        image_bytes = self._get_test_leaf_bytes()
        files = {"file": ("leaf.jpg", image_bytes, "image/jpeg")}
        data = {"crop_name": "Tomato", "save_history": "true"}

        # Step 1: Diagnose leaf image
        pred_res = self.client.post("/api/predict", files=files, data=data, headers=self.farmer_headers)
        self.assertEqual(pred_res.status_code, 200)
        res_data = pred_res.json()
        self.assertTrue(res_data.get("success"))
        diag_id = res_data.get("saved_diagnosis_id") or res_data.get("diagnosis_id") or res_data.get("id")
        self.assertIsNotNone(diag_id)

        # Step 2: Contextual AI explanation bound to diagnosis
        chat_payload = {
            "diagnosis_id": diag_id,
            "message": "Bệnh này có lây lan nhanh trong mùa mưa không và cách phòng ngừa?",
            "conversation_history": []
        }
        chat_res = self.client.post("/api/assistant/chat", json=chat_payload, headers=self.farmer_headers)
        self.assertEqual(chat_res.status_code, 200)
        chat_data = chat_res.json()
        self.assertTrue(chat_data.get("success"))
        self.assertTrue(len(chat_data.get("reply", "")) > 10)

        # Step 3: Saved history retrieval
        hist_res = self.client.get(f"/api/diagnoses/{diag_id}", headers=self.farmer_headers)
        self.assertEqual(hist_res.status_code, 200)
        hist_data = hist_res.json()
        self.assertEqual(hist_data["diagnosis"]["id"], diag_id)
        self.assertEqual(hist_data["diagnosis"]["crop_id"], "tomato")

    def test_workflow_02_diagnosis_task_assignment_completion_activities(self):
        """Workflow 2: Diagnosis → create task → assign task → complete task → activity history."""
        # Step 1: Create diagnosis record
        diag = gari_database.save_diagnosis({
            "crop_id": "coffee",
            "crop_name": "Cà phê",
            "predicted_disease": "Coffee Leaf Rust",
            "disease_name_vi": "Bệnh gỉ sắt cà phê",
            "confidence": 0.94,
            "severity": "HIGH",
        }, user_id=self.farmer_user["id"])
        diag_id = diag["id"]

        # Step 2: Create task from diagnosis
        task_res = self.client.post("/api/calendar/tasks/from-diagnosis", json={
            "diagnosis_id": diag_id,
            "title": "Phun phòng trừ gỉ sắt đợt 1",
            "priority": "HIGH",
            "notes": "Ưu tiên thuốc sinh học gốc đồng"
        }, headers=self.farmer_headers)
        self.assertEqual(task_res.status_code, 200)
        task = task_res.json()["task"]
        task_id = task["id"]
        self.assertEqual(task["status"], "pending")

        # Step 3: Reassign task to another user
        patch_res = self.client.patch(f"/api/calendar/tasks/{task_id}", json={
            "assignee_user_id": self.pro_user["id"],
            "priority": "URGENT"
        }, headers=self.farmer_headers)
        self.assertEqual(patch_res.status_code, 200)

        # Step 4: Complete task
        comp_res = self.client.post(f"/api/calendar/tasks/{task_id}/complete", json={
            "notes": "Đã phun xong toàn bộ vườn lô A"
        }, headers=self.farmer_headers)
        self.assertEqual(comp_res.status_code, 200)
        self.assertEqual(comp_res.json()["task"]["status"], "completed")

        # Step 5: Check activity history
        act_res = self.client.get(f"/api/calendar/tasks/{task_id}/activities", headers=self.farmer_headers)
        self.assertEqual(act_res.status_code, 200)
        activities = act_res.json()["activities"]
        actions = [a["action"] for a in activities]
        self.assertIn("created", actions)
        self.assertIn("completed", actions)

    def test_workflow_03_organization_lifecycle_invitation_farm_assignment(self):
        """Workflow 3: Personal user → create organization → invite member → assign farm access."""
        # Step 1: Owner creates organization
        create_res = self.client.post("/api/organizations", json={
            "name": "Hợp Tác Xã Nông Sản Sạch Cao Nguyên",
            "organization_type": "cooperative",
            "region": "Tây Nguyên",
            "primary_crops": ["Coffee", "Pepper"]
        }, headers=self.owner_headers)
        self.assertEqual(create_res.status_code, 200)
        org = create_res.json()["organization"]
        org_id = org["id"]

        # Step 2: Create a farm for this organization via API
        farm_res = self.client.post("/api/farms", json={
            "name": "Nông Trại Cà Phê HTX 01",
            "organization_id": org_id,
            "province": "Đắk Lắk",
            "primary_crop": "Coffee",
            "area_m2": 20000.0
        }, headers=self.owner_headers)
        self.assertEqual(farm_res.status_code, 200)
        farm_id = farm_res.json()["farm"]["id"]

        # Step 3: Owner invites member
        inv_res = self.client.post(f"/api/organizations/{org_id}/invitations", json={
            "email": self.member_user["email"],
            "role": "field_worker"
        }, headers=self.owner_headers)
        self.assertEqual(inv_res.status_code, 200)
        invitation = inv_res.json()["invitation"]
        inv_id = invitation["id"]

        # Step 4: Member accepts invitation
        token = invitation.get("invite_token") or invitation.get("token") or invitation.get("raw_token")
        accept_res = self.client.post("/api/invitations/accept", json={"token": token}, headers=self.member_headers)
        self.assertEqual(accept_res.status_code, 200)

        # Step 5: Owner assigns member to farm scope
        assign_res = self.client.post(f"/api/organizations/{org_id}/assignments", json={
            "user_id": self.member_user["id"],
            "farm_id": farm_id,
            "notes": "Phụ trách chăm sóc và giám sát sâu bệnh lô cà phê"
        }, headers=self.owner_headers)
        self.assertEqual(assign_res.status_code, 200)

        # Step 6: Verify member sees assignment
        get_assigns = self.client.get(f"/api/organizations/{org_id}/assignments", headers=self.member_headers)
        self.assertEqual(get_assigns.status_code, 200)
        assignments = get_assigns.json()["assignments"]
        self.assertTrue(any(a["user_id"] == self.member_user["id"] and a["farm_id"] == farm_id for a in assignments))

    def test_workflow_04_org_member_diagnosis_task_owner_visibility(self):
        """Workflow 4: Organization member → diagnose a crop → create a task → owner sees activity."""
        # Use existing organization from owner
        org_id = self.client.get("/api/organizations", headers=self.owner_headers).json()["organizations"][0]["id"]

        # Step 1: Member creates diagnosis scoped to organization
        diag = gari_database.save_diagnosis({
            "crop_id": "pepper",
            "crop_name": "Hồ tiêu",
            "predicted_disease": "Foot Rot (Phytophthora)",
            "disease_name_vi": "Bệnh chết nhanh hồ tiêu",
            "confidence": 0.96,
            "severity": "URGENT",
            "organization_id": org_id,
        }, user_id=self.member_user["id"])
        diag_id = diag["id"]

        # Step 2: Member creates task in the organization
        task_res = self.client.post("/api/calendar/tasks/from-diagnosis", json={
            "diagnosis_id": diag_id,
            "title": "Cách ly trụ tiêu bị bệnh chết nhanh",
            "priority": "URGENT",
            "notes": "Đào rãnh thoát nước cách ly khu vực nhiễm bệnh"
        }, headers=self.member_headers)
        self.assertEqual(task_res.status_code, 200)
        task_id = task_res.json()["task"]["id"]

        # Step 3: Owner queries organization tasks and sees the member's task
        owner_tasks_res = self.client.get(f"/api/calendar/tasks?org_id={org_id}", headers=self.owner_headers)
        self.assertEqual(owner_tasks_res.status_code, 200)
        tasks = owner_tasks_res.json()["tasks"]
        self.assertTrue(any(t["id"] == task_id for t in tasks))

        # Step 4: Owner inspects the task's activity log
        owner_act_res = self.client.get(f"/api/calendar/tasks/{task_id}/activities", headers=self.owner_headers)
        self.assertEqual(owner_act_res.status_code, 200)
        activities = owner_act_res.json()["activities"]
        self.assertTrue(any(a["action"] == "created" for a in activities))

    def test_workflow_05_expert_consultation_lifecycle(self):
        """Workflow 5: User → request expert consultation → consent → expert assignment → response → closure."""
        # Step 1: User creates diagnosis
        diag = gari_database.save_diagnosis({
            "crop_id": "durian",
            "crop_name": "Sầu riêng",
            "predicted_disease": "Phytophthora Canker",
            "disease_name_vi": "Xì mủ gốc sầu riêng",
            "confidence": 0.92,
            "severity": "HIGH",
        }, user_id=self.farmer_user["id"])
        diag_id = diag["id"]

        # Step 2: Farmer requests consultation with explicit farm data consent
        create_case = self.client.post("/api/expert/cases", json={
            "diagnosis_id": diag_id,
            "symptoms_description": "Vết xì mủ lan rộng quanh gốc sầu riêng 4 năm tuổi, lá bắt đầu rụng.",
            "consent_share_farm_data": True,
            "urgency": "urgent"
        }, headers=self.farmer_headers)
        self.assertEqual(create_case.status_code, 200)
        case_id = create_case.json()["case"]["id"]

        # Step 3: Expert claims the case
        claim_res = self.client.post(f"/api/expert/portal/cases/{case_id}/claim", headers=self.expert_headers)
        self.assertEqual(claim_res.status_code, 200)
        self.assertEqual(claim_res.json()["case"]["status"], "in_review")

        # Step 4: Expert requests additional agronomic information
        req_info = self.client.post(f"/api/expert/cases/{case_id}/request-info", json={
            "question": "Bạn có bón nhiều đạm trong mùa mưa không và hệ thống thoát nước vườn thế nào?"
        }, headers=self.expert_headers)
        self.assertEqual(req_info.status_code, 200)

        # Step 5: Farmer provides additional info
        prov_info = self.client.post(f"/api/expert/cases/{case_id}/provide-info", json={
            "info": "Vườn trũng nước do mưa lớn tuần qua, có bón phân NPK 20-20-15 cách đây 10 ngày."
        }, headers=self.farmer_headers)
        self.assertEqual(prov_info.status_code, 200)

        # Step 6: Expert resolves the case with prescription
        resolve_res = self.client.post(f"/api/expert/portal/cases/{case_id}/resolve", json={
            "resolution_notes": "Xác nhận nấm Phytophthora palmivora tấn công cổ rễ. Cần cạo sạch vết thối, quét thuốc Ridomil Gold hoặc Aliette kết hợp lân Phosphonate.",
            "diagnosis_correction": "Phytophthora palmivora confirmed",
            "prescription_data": {
                "active_ingredients": ["Metalaxyl-M", "Mancozeb"],
                "dosage": "50g / 10L",
                "application_method": "Quét trực tiếp vết thương sau khi làm sạch"
            }
        }, headers=self.expert_headers)
        self.assertEqual(resolve_res.status_code, 200)
        self.assertEqual(resolve_res.json()["case"]["status"], "resolved")

        # Step 7: Farmer reviews and closes consultation with 5-star rating
        close_res = self.client.post(f"/api/expert/cases/{case_id}/close", json={
            "rating": 5.0,
            "feedback_notes": "Chuyên gia hướng dẫn rất chi tiết và kịp thời, cảm ơn GARI!"
        }, headers=self.farmer_headers)
        self.assertEqual(close_res.status_code, 200)
        self.assertEqual(close_res.json()["case"]["status"], "closed")

    def test_workflow_06_subscription_limit_enforcement_and_upgrade(self):
        """Workflow 6: Subscription change → entitlement update → backend limit enforcement → UI feedback."""
        fresh_user, fresh_token, fresh_headers = self._register_user("quota_tester")

        # Verify initial free plan usage
        usage_res = self.client.get("/api/subscriptions/usage", headers=fresh_headers)
        self.assertEqual(usage_res.status_code, 200)
        usage_data = usage_res.json()
        self.assertEqual(usage_data["plan"]["plan_id"], "free")

        # Simulate exhausting the limit
        gari_entitlements.record_usage(fresh_user["id"], "ai_usage", 50.0)

        # Enforce check now fails
        with self.assertRaises(gari_entitlements.EntitlementExceededError):
            gari_entitlements.enforce_entitlement(fresh_user["id"], "ai_usage")

        # User upgrades to Pro subscription
        gari_entitlements.assign_subscription("user", fresh_user["id"], "pro")

        # Enforce check now passes immediately
        gari_entitlements.enforce_entitlement(fresh_user["id"], "ai_usage")

        # UI usage telemetry reflects the new limit (higher than 50)
        new_usage = self.client.get("/api/subscriptions/usage", headers=fresh_headers).json()
        self.assertEqual(new_usage["plan"]["plan_id"], "pro")
        ai_dim = (new_usage.get("usage") or new_usage.get("metrics"))["ai_usage"]
        self.assertGreater(ai_dim["limit"], 50)
        self.assertEqual(ai_dim["used"], 50)
        self.assertEqual(ai_dim["remaining"], ai_dim["limit"] - 50)

    def test_workflow_07_host_admin_ai_config_propagation(self):
        """Workflow 7: Host Admin → update AI provider config → backend provider adapter uses config."""
        # Host Admin updates configuration
        update_res = self.client.post("/api/host/ai/config", json={
            "provider": "mock",
            "model": "gari-botanical-2026-v2",
            "temperature": 0.15,
            "timeout_sec": 12.0,
            "reason": "Routine system audit test configuration"
        }, headers=self.host_admin_headers)
        self.assertEqual(update_res.status_code, 200)

        # Assistant immediately loads updated configuration from host_api_config
        assistant_cfg = gari_assistant.get_assistant_config()
        self.assertEqual(assistant_cfg["provider"], "mock")
        self.assertEqual(assistant_cfg["model"], "gari-botanical-2026-v2")
        self.assertEqual(assistant_cfg["temperature"], 0.15)
        self.assertEqual(assistant_cfg["timeout_sec"], 12.0)

        # Verify audit log recorded
        with gari_database.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM host_audit_logs WHERE action_type = 'UPDATE_AI_CONFIG' ORDER BY id DESC LIMIT 1")
            audit = cur.fetchone()
            self.assertIsNotNone(audit)
            self.assertEqual(audit["host_admin_id"], self.host_admin_user["id"])

    def test_workflow_08_web_mobile_persisted_state_synchronization(self):
        """Workflow 8: Web action → mobile reflects the same persisted backend data."""
        # Web creates a farm and a task
        web_farm = gari_database.create_farm({
            "name": "Nông Trại Đồng Bộ Web-Mobile",
            "province": "Lâm Đồng",
            "primary_crop": "Tomato",
            "area_m2": 8500.0,
        }, user_id=self.farmer_user["id"])

        web_task = gari_tasks.create_task({
            "title": "Kiểm tra bẫy pheromone ruồi đục quả",
            "farm_id": web_farm["id"],
            "priority": "high",
            "due_date": "2026-11-20",
        }, creator_user_id=self.farmer_user["id"])

        # Mobile client requests farms via API
        mobile_farms = self.client.get("/api/farms", headers=self.farmer_headers).json()["farms"]
        self.assertTrue(any(f["id"] == web_farm["id"] and f["name"] == "Nông Trại Đồng Bộ Web-Mobile" for f in mobile_farms))

        # Mobile client requests tasks via API
        mobile_tasks = self.client.get("/api/calendar/tasks", headers=self.farmer_headers).json()["tasks"]
        self.assertTrue(any(t["id"] == web_task["id"] and t["title"] == "Kiểm tra bẫy pheromone ruồi đục quả" for t in mobile_tasks))

        # Mobile client toggles task completion
        comp_res = self.client.post(f"/api/calendar/tasks/{web_task['id']}/complete", headers=self.farmer_headers)
        self.assertEqual(comp_res.status_code, 200)

        # Web queries task and sees completed status
        refreshed_task = gari_tasks.get_task(web_task["id"], user_id=self.farmer_user["id"])
        self.assertEqual(refreshed_task["status"], "completed")


if __name__ == "__main__":
    unittest.main()
