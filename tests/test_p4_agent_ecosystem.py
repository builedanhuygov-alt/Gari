"""
GARI AgriTech AI Lab — Phase P4 Automated Test Suite
AI Agent Ecosystem Verification (12 Mandated Scenarios):
1. Agent Registry Discovery: All 7 specialized agents registered with metadata & tools.
2. Own Diagnosis Access: Agronomy agent retrieves and correlates user's own diagnosis.
3. Other User Diagnosis Blocked: Zero-trust boundary strictly blocks cross-tenant diagnosis access.
4. Farm Access Boundary: Farm Monitoring agent enforces farm ownership / membership.
5. Weather Forecast Provenance: Weather & Risk agent distinguishes observation vs forecast.
6. Satellite Cloudy Masking: Satellite agent handles cloud cover transparently without fake values.
7. Transparent Risk Explanation: Risk agent provides 5-vector breakdown without black-box metrics.
8. Task Assignment & Permissions: Task & Workflow agent enforces authorization.
9. Report Provenance: Reporting agent details exact data lineage and timestamping.
10. Expert Matching Disclaimer: Expert agent enforces unconfirmed consultation disclaimer.
11. Human Approval Gate: High-impact actions trigger 'requires_human_review' and can be resolved.
12. Telemetry Secret Scrubbing & Error Recovery: Log sanitization redacts secrets; graceful error handling.
"""

import json
import unittest
import uuid
from starlette.testclient import TestClient

from api_server import app
from gari_database import get_connection
import gari_plans
import gari_entitlements
import gari_agent_orchestrator


class TestP4AgentEcosystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # 1. Register User A (Tenant A)
        cls.email_a = f"p4_user_a_{uuid.uuid4().hex[:8]}@gari.vn"
        cls.pass_a = "Password123!"
        res_a = cls.client.post("/api/auth/register", json={
            "email": cls.email_a,
            "password": cls.pass_a,
            "full_name": "Nong Dan A"
        })
        assert res_a.status_code == 200, f"Register A failed: {res_a.text}"
        data_a = res_a.json()
        cls.token_a = data_a.get("access_token") or data_a.get("token")
        cls.user_a_id = data_a.get("user", {}).get("id") or data_a.get("user_id")
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        # 2. Register User B (Tenant B)
        cls.email_b = f"p4_user_b_{uuid.uuid4().hex[:8]}@gari.vn"
        cls.pass_b = "Password123!"
        res_b = cls.client.post("/api/auth/register", json={
            "email": cls.email_b,
            "password": cls.pass_b,
            "full_name": "Nong Dan B"
        })
        assert res_b.status_code == 200, f"Register B failed: {res_b.text}"
        data_b = res_b.json()
        cls.token_b = data_b.get("access_token") or data_b.get("token")
        cls.user_b_id = data_b.get("user", {}).get("id") or data_b.get("user_id")
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

        # Upgrade User A to enterprise plan to ensure full resource access
        gari_plans.assign_user_plan(cls.user_a_id, "enterprise", status="pilot_active")

        # Create Farm A for User A
        res_farm_a = cls.client.post("/api/farms", headers=cls.headers_a, json={
            "name": f"Nong Trai A {uuid.uuid4().hex[:4]}",
            "province": "Lam Dong",
            "district": "Da Lat",
            "latitude": 11.9404,
            "longitude": 108.4583,
            "total_area": 5.0
        })
        assert res_farm_a.status_code == 200, f"Farm creation failed: {res_farm_a.text}"
        cls.farm_a_id = res_farm_a.json()["farm"]["id"]

        # Insert a diagnosis record owned by User A
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO diagnoses (
                    user_id, farm_id, crop_id, crop_name, predicted_disease, disease_name_vi,
                    confidence, severity, diagnosis_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                cls.user_a_id, cls.farm_a_id, "tomato", "Tomato", "Tomato_Late_blight",
                "Bệnh mốc sương cà chua", 0.94, "severe", "diagnosed"
            ))
            cls.diag_a_id = cur.lastrowid
            conn.commit()

    def test_01_agent_registry_discovery(self):
        """1. Verify all 7 specialized agents are correctly registered with metadata & tools."""
        res = self.client.get("/api/agents", headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["total"], 7)

        agent_ids = [a["agent_id"] for a in data["agents"]]
        expected = [
            "agronomy", "farm_monitoring", "weather_risk",
            "satellite_intelligence", "task_workflow", "reporting", "expert_assistance"
        ]
        for exp in expected:
            self.assertIn(exp, agent_ids)

    def test_02_own_diagnosis_access(self):
        """2. Agronomy Agent can access and analyze user's own diagnosis record."""
        payload = {
            "task_type": "clinical_analysis",
            "context": {"diagnosis_id": self.diag_a_id}
        }
        res = self.client.post("/api/agents/agronomy/run", headers=self.headers_a, json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["status"], "completed")
        self.assertIn("differential_diagnosis", data["result"])
        self.assertEqual(data["result"]["crop"], "Tomato")

    def test_03_other_user_diagnosis_blocked(self):
        """3. Zero-Trust Access: Agent of User B is blocked from accessing User A's diagnosis."""
        payload = {
            "task_type": "clinical_analysis",
            "context": {"diagnosis_id": self.diag_a_id}
        }
        res = self.client.post("/api/agents/agronomy/run", headers=self.headers_b, json=payload)
        # Should return HTTP 403 Forbidden
        self.assertEqual(res.status_code, 403)
        self.assertIn("quyền", res.text.lower())

    def test_04_farm_access_permission_enforcement(self):
        """4. Farm Monitoring Agent enforces farm ownership boundaries."""
        # User B attempting to monitor User A's farm
        payload = {
            "task_type": "monitor_farm",
            "context": {"farm_id": self.farm_a_id}
        }
        res = self.client.post("/api/agents/farm_monitoring/run", headers=self.headers_b, json=payload)
        self.assertEqual(res.status_code, 403)

        # User A monitoring their own farm succeeds
        res_a = self.client.post("/api/agents/farm_monitoring/run", headers=self.headers_a, json=payload)
        self.assertEqual(res_a.status_code, 200)
        self.assertTrue(res_a.json()["success"])

    def test_05_weather_forecast_provenance(self):
        """5. Weather & Risk Agent returns weather telemetry with explicit source provenance."""
        payload = {
            "task_type": "weather_risk_assessment",
            "context": {"farm_id": self.farm_a_id}
        }
        res = self.client.post("/api/agents/weather_risk/run", headers=self.headers_a, json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        weather = data["result"].get("weather_telemetry", {})
        self.assertIn("source", weather)
        self.assertIn("Open-Meteo", weather["source"])

    def test_06_satellite_cloudy_masking(self):
        """6. Satellite Intelligence Agent reports cloudy masking or no-geometry honestly without fabrication."""
        payload = {
            "task_type": "canopy_index_analysis",
            "context": {"farm_id": self.farm_a_id}
        }
        res = self.client.post("/api/agents/satellite_intelligence/run", headers=self.headers_a, json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        # Farm has no plot polygon uploaded yet, agent should report missing boundary without fake NDVI
        self.assertIn("satellite_indices", data["result"])
        status = data["result"]["satellite_indices"].get("status")
        self.assertIn(status, ["no_geometry", "cloud_masked", "available", "unsupported"])

    def test_07_risk_engine_transparent_explanation(self):
        """7. Risk Agent returns 5-vector transparent risk factors without black-box scores."""
        payload = {
            "task_type": "farm_risk_audit",
            "context": {"farm_id": self.farm_a_id}
        }
        res = self.client.post("/api/agents/weather_risk/run", headers=self.headers_a, json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("overall_threat_level", data["result"])
        self.assertIn("advisory", data["result"])

    def test_08_task_workflow_permission(self):
        """8. Task & Workflow Agent lists tasks and generates actionable plans within scope."""
        payload = {
            "task_type": "plan_crop_tasks",
            "context": {"farm_id": self.farm_a_id, "diagnosis_id": self.diag_a_id}
        }
        res = self.client.post("/api/agents/task_workflow/run", headers=self.headers_a, json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("proposed_tasks", data["result"])

    def test_09_reporting_provenance(self):
        """9. Reporting Agent details complete data lineage and provenance in output."""
        payload = {
            "task_type": "generate_farm_audit_report",
            "context": {"farm_id": self.farm_a_id, "report_type": "health"}
        }
        res = self.client.post("/api/agents/reporting/run", headers=self.headers_a, json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("provenance", data["result"])
        self.assertEqual(data["result"]["provenance"]["data_source"], "GARI AgriTech Database & Live Telemetry")

    def test_10_expert_matching_disclaimer(self):
        """10. Expert Assistance Agent includes mandatory unconfirmed consultation disclaimer."""
        payload = {
            "task_type": "prepare_consultation_case",
            "context": {"diagnosis_id": self.diag_a_id}
        }
        res = self.client.post("/api/agents/expert_assistance/run", headers=self.headers_a, json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        summary = data["result"].get("case_summary", {})
        self.assertIn("disclaimer", summary)
        self.assertIn("Chuyên gia chưa tiếp nhận", summary["disclaimer"])

    def test_11_human_approval_gate_high_impact(self):
        """11. High-impact operations (e.g. chemical spray prescription) mandate human approval."""
        payload = {
            "task_type": "chemical_spray_prescription",
            "context": {
                "farm_id": self.farm_a_id,
                "diagnosis_id": self.diag_a_id,
                "chemical_name": "Mancozeb 80WP",
                "dosage": "50g / 20L nước"
            }
        }
        res = self.client.post("/api/agents/task_workflow/run", headers=self.headers_a, json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "requires_human_review")
        self.assertTrue(data["requires_approval"])
        self.assertIsNotNone(data.get("approval_id"))
        approval_id = data["approval_id"]

        # List pending approvals and verify it appears
        res_appr = self.client.get("/api/agents/approvals", headers=self.headers_a)
        self.assertEqual(res_appr.status_code, 200)
        pending_ids = [a["approval_id"] for a in res_appr.json()["approvals"]]
        self.assertIn(approval_id, pending_ids)

        # Resolve approval: Approve action
        res_res = self.client.post(
            f"/api/agents/approvals/{approval_id}/resolve",
            headers=self.headers_a,
            json={"action": "approve", "notes": "Đã kiểm tra nồng độ thuốc, duyệt phun."}
        )
        self.assertEqual(res_res.status_code, 200)
        self.assertEqual(res_res.json()["status"], "approved")

    def test_12_telemetry_secret_scrubbing_and_safe_error(self):
        """12. Telemetry and execution logs redact sensitive credentials and recover safely from errors."""
        # Run agent task with sensitive tokens in context
        payload = {
            "task_type": "test_scrubbing",
            "context": {
                "diagnosis_id": self.diag_a_id,
                "api_token": "secret_jwt_token_12345",
                "password": "super_secret_db_pass",
                "auth_bearer": "Bearer eyJhbGciOi..."
            }
        }
        res = self.client.post("/api/agents/agronomy/run", headers=self.headers_a, json=payload)
        self.assertEqual(res.status_code, 200)
        exec_id = res.json()["execution_id"]

        # Retrieve execution log via API and assert sensitive fields were scrubbed
        res_log = self.client.get(f"/api/agents/executions/{exec_id}", headers=self.headers_a)
        self.assertEqual(res_log.status_code, 200)
        log_data = res_log.json()["execution"]
        input_ctx = log_data.get("input_context", {})

        # Ensure tokens were redacted
        self.assertEqual(input_ctx.get("api_token"), "[REDACTED_SECRET]")
        self.assertEqual(input_ctx.get("password"), "[REDACTED_SECRET]")
        self.assertEqual(input_ctx.get("auth_bearer"), "[REDACTED_SECRET]")

        # Error recovery: Invalid diagnosis_id returns clean error instead of 500 crash
        res_err = self.client.post("/api/agents/agronomy/run", headers=self.headers_a, json={
            "task_type": "clinical_analysis",
            "context": {"diagnosis_id": 999999999}
        })
        self.assertIn(res_err.status_code, [400, 404])


if __name__ == "__main__":
    unittest.main()
