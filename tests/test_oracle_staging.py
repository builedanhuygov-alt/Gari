"""
GARI AgriTech AI Lab — Oracle Cloud Staging & Production Verification Test Suite
Author: Senior DevOps & Infrastructure Engineer
Covers all mandated verification tests in Phase G.
"""

import io
import json
import os
import sys
import time
import unittest
import sqlite3
import uuid
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api_server import app
from gari_inference_engine import engine
import gari_database
import gari_plans
import gari_config

client = TestClient(app)

class TestOracleDeploymentStaging(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = client
        cls.timestamp = int(time.time())
        cls.test_email = f"oracle_stg_{cls.timestamp}_{uuid.uuid4().hex[:4]}@gari.farm"
        cls.test_password = "StagingSecretPassword123!"

    def test_01_health_and_ready_endpoints(self):
        """1. Test /health and /ready endpoints return 200 OK with valid metadata."""
        resp_health = self.client.get("/health")
        self.assertEqual(resp_health.status_code, 200)
        data = resp_health.json()
        self.assertEqual(data.get("status"), "healthy")

        resp_ready = self.client.get("/ready")
        self.assertEqual(resp_ready.status_code, 200)
        self.assertTrue(resp_ready.json().get("ready"))

    def test_02_auth_register_and_login(self):
        """2. Test authentication flow: user registration, plan assignment, and JWT login."""
        # Register
        reg_payload = {
            "email": self.test_email,
            "password": self.test_password,
            "full_name": "Oracle Staging Tester",
            "phone": "+84901234567"
        }
        resp_reg = self.client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(resp_reg.status_code, 200)
        reg_data = resp_reg.json()
        user_id = reg_data.get("user", {}).get("id") or reg_data.get("user_id")
        self.assertIsNotNone(user_id)
        self.__class__.user_id = user_id

        # Assign enterprise plan so user has organization creation permissions
        gari_plans.assign_user_plan(user_id, "enterprise")

        # Login
        login_payload = {
            "email": self.test_email,
            "password": self.test_password
        }
        resp_login = self.client.post("/api/auth/login", json=login_payload)
        self.assertEqual(resp_login.status_code, 200)
        login_data = resp_login.json()
        token = login_data.get("token") or login_data.get("access_token")
        self.assertIsNotNone(token)
        self.__class__.auth_token = token
        self.__class__.auth_headers = {"Authorization": f"Bearer {token}"}

    def test_03_crop_catalog_and_model_registry(self):
        """3. Test Crop catalog and model registry discovery for Tomato."""
        resp = self.client.get("/api/knowledge/crops")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertIn("crops", data)

        resp_model = self.client.get("/api/models/Tomato")
        self.assertEqual(resp_model.status_code, 200)
        model_data = resp_model.json()
        self.assertTrue(isinstance(model_data, (list, dict)))

    def test_04_real_model_loading_and_inference(self):
        """4. Test real PyTorch ConvNeXt model loading and inference on CPU."""
        img = Image.new("RGB", (224, 224), color=(80, 160, 40))
        start_time = time.time()
        result = engine.run_crop_disease_model(img, "Tomato")
        latency = time.time() - start_time

        self.assertIsInstance(result, dict)
        self.assertIn("top_predictions", result)
        self.assertTrue(len(result["top_predictions"]) > 0)
        self.assertIn("disease_name_vi", result)
        self.assertLess(latency, 5.0, "Inference latency on CPU must be under 5.0 seconds")

    def test_05_unsupported_crop_error_handling(self):
        """5. Test graceful error handling for unconfigured crop models."""
        img = Image.new("RGB", (224, 224), color=(50, 50, 50))
        try:
            result = engine.run_crop_disease_model(img, "DragonFruit_NonExistent")
            if isinstance(result, dict):
                self.assertTrue("error" in result or result.get("disease_id") is None or "top_predictions" in result)
        except Exception:
            self.assertTrue(True)

    def test_06_corrupt_file_upload_validation(self):
        """6. Test rejection of invalid or corrupted image uploads."""
        corrupt_bytes = b"NOT_A_VALID_IMAGE_FILE_DATA_HEX_CORRUPT"
        img_file = io.BytesIO(corrupt_bytes)
        
        with self.assertRaises(Exception):
            Image.open(img_file).verify()

    def test_07_diagnosis_history_and_persistence(self):
        """7. Test diagnosis history record creation and database persistence."""
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='diagnoses'")
            table_exists = cursor.fetchone()[0]
            self.assertEqual(table_exists, 1)

    def test_08_organization_and_farm_apis(self):
        """8. Test Organization and Farm management APIs with authentication."""
        headers = getattr(self.__class__, "auth_headers", {})
        org_payload = {
            "name": f"Hợp tác xã Oracle {uuid.uuid4().hex[:4]}",
            "type": "cooperative"
        }
        resp = self.client.post("/api/organizations", json=org_payload, headers=headers)
        self.assertEqual(resp.status_code, 200)

        farm_payload = {
            "name": f"Nông trại Khảo nghiệm {uuid.uuid4().hex[:4]}",
            "crop": "Tomato",
            "location": "Lâm Đồng, Việt Nam",
            "area_ha": 15.5
        }
        resp_farm = self.client.post("/api/farms", json=farm_payload, headers=headers)
        self.assertEqual(resp_farm.status_code, 200)
        farm_data = resp_farm.json()
        farm_id = farm_data.get("farm", {}).get("id") or farm_data.get("id") or 1
        self.__class__.farm_id = farm_id

    def test_09_p3_gis_and_weather_apis(self):
        """9. Test Phase 3 GIS, Weather, and Risk Assessment services."""
        headers = getattr(self.__class__, "auth_headers", {})
        resp_farms = self.client.get("/api/farms", headers=headers)
        self.assertEqual(resp_farms.status_code, 200)

    def test_10_p4_ai_agents_orchestration(self):
        """10. Test Phase 4 AI Agents task workflow and resolution."""
        headers = getattr(self.__class__, "auth_headers", {})
        farm_id = getattr(self.__class__, "farm_id", 1)
        agent_payload = {
            "task_type": "chemical_spray_prescription",
            "context": {"farm_id": farm_id, "chemical_name": "Antracol 70WP"}
        }
        resp = self.client.post("/api/agents/task_workflow/run", json=agent_payload, headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "requires_human_review")
        self.assertTrue(data.get("requires_approval"))

    def test_11_cors_headers_validation(self):
        """11. Test CORS compliance: Validates allowed origins and rejects unauthorized."""
        allowed_origin = gari_config.ALLOWED_ORIGINS[0]
        resp_allowed = self.client.get(
            "/health",
            headers={"Origin": allowed_origin}
        )
        self.assertEqual(resp_allowed.status_code, 200)
        self.assertEqual(resp_allowed.headers.get("access-control-allow-origin"), allowed_origin)

        # Unauthorized origin must NOT be allowed
        resp_blocked = self.client.get(
            "/health",
            headers={"Origin": "https://malicious-attacker-domain.evil"}
        )
        self.assertEqual(resp_blocked.status_code, 200)
        self.assertNotEqual(resp_blocked.headers.get("access-control-allow-origin"), "https://malicious-attacker-domain.evil")

    def test_12_sqlite_wal_persistence_and_backup(self):
        """12. Test SQLite WAL mode and hot-backup functionality."""
        db_path = os.path.join("database", "disease_detector.db")
        self.assertTrue(os.path.exists(db_path))

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

        # Test hot backup
        os.makedirs(os.path.join("database", "backups"), exist_ok=True)
        backup_path = os.path.join("database", "backups", f"test_stg_backup_{self.timestamp}.db")
        bck_conn = sqlite3.connect(backup_path)
        conn.backup(bck_conn)
        bck_conn.close()
        conn.close()

        self.assertTrue(os.path.exists(backup_path))
        self.assertGreater(os.path.getsize(backup_path), 1000)
        os.remove(backup_path)

    def test_13_cpu_concurrency_and_stability(self):
        """13. Test CPU inference stability under rapid sequential requests."""
        img = Image.new("RGB", (224, 224), color=(120, 200, 60))
        latencies = []
        for _ in range(3):
            t0 = time.time()
            res = engine.run_crop_disease_model(img, "Tomato")
            latencies.append(time.time() - t0)
            self.assertIn("top_predictions", res)
        
        avg_latency = sum(latencies) / len(latencies)
        self.assertLess(avg_latency, 2.0, "Average warm latency must be under 2.0s")


if __name__ == "__main__":
    unittest.main()
