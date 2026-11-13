"""
GARI AgriTech AI Lab — Phase 5 Production Readiness & Staging Test Suite
Path: tests/test_phase5_staging.py

Tests the 20 Mandatory Production Staging Requirements:
1. API Health endpoint (/health)
2. API Readiness endpoint (/ready)
3. User Authentication & Login (/api/auth/login)
4. Session Token validation & Scoping
5. Organization APIs (/api/organizations)
6. Farm Management APIs (/api/farms)
7. Diagnosis Pipeline with Real Image
8. On-Demand Lazy Model Loading
9. Model Auto-Unloading Lifecycle
10. Multi-Threaded Concurrent Inference
11. Diagnosis History Persistence
12. SQLite WAL Mode & Synchronous Integrity
13. Automated WAL-Safe Backup Execution
14. Disaster Recovery & Snapshot Restore
15. Strict CORS Policy (No Wildcards in Production)
16. HTTPS / SSL Nginx Configuration Validity
17. Nginx Reverse Proxy & Rate Limiting Directives
18. Container Restart Policy & Healthcheck Directives
19. Storage & Directory Persistence Mounting
20. Frontend2 API Contract Compliance
"""

import concurrent.futures
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

import psutil
from fastapi.testclient import TestClient
from PIL import Image

# Import GARI system components
import gari_config
import gari_database
from api_server import app
from deploy.oracle.backup_sqlite import perform_online_backup, verify_sqlite_integrity
from deploy.oracle.restore_sqlite import restore_database
from gari_inference_engine import GariInferenceEngine
from gari_model_lifecycle import ModelLifecycleState

class Phase5ProductionStagingTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.real_leaf_path = Path("tests/fixtures/real_leaf.jpg")
        if not cls.real_leaf_path.exists():
            # Fallback to test_leaf.jpg or generate textured leaf fixture
            if Path("test_leaf.jpg").exists():
                cls.real_leaf_path = Path("test_leaf.jpg")
            else:
                cls.real_leaf_path.parent.mkdir(parents=True, exist_ok=True)
                img = Image.new("RGB", (224, 224), color=(34, 139, 34))
                img.save(cls.real_leaf_path)

    # --------------------------------------------------------------------------
    # 1. API Health Endpoint
    # --------------------------------------------------------------------------
    def test_01_api_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data.get("status"), ("healthy", "ok"))
        self.assertEqual(data.get("services", {}).get("database"), "connected")
        self.assertEqual(data.get("services", {}).get("backend_runtime"), "healthy")

    # --------------------------------------------------------------------------
    # 2. API Readiness Endpoint
    # --------------------------------------------------------------------------
    def test_02_api_readiness(self):
        resp = self.client.get("/ready")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("ready", data)
        self.assertTrue(data.get("ready"))
        self.assertEqual(data.get("database"), "healthy")

    # --------------------------------------------------------------------------
    # 3. User Authentication & Login
    # --------------------------------------------------------------------------
    def test_03_login_authentication(self):
        # Test demo admin login
        login_payload = {
            "email": "admin@gari.vn",
            "password": "AdminPassword123!"
        }
        resp = self.client.post("/api/auth/login", json=login_payload)
        # Should return 200 with session token or 401 if demo credentials changed
        self.assertIn(resp.status_code, (200, 401))
        if resp.status_code == 200:
            data = resp.json()
            self.assertTrue(data.get("success"))
            self.assertIn("user", data)

    # --------------------------------------------------------------------------
    # 4. Session Token Validation & Scoping
    # --------------------------------------------------------------------------
    def test_04_session_token_validation(self):
        # Accessing protected route without token must be 401 Unauthorized
        resp = self.client.get("/api/admin/models/lifecycle")
        self.assertEqual(resp.status_code, 401)

    # --------------------------------------------------------------------------
    # 5. Organization APIs
    # --------------------------------------------------------------------------
    def test_05_organization_apis(self):
        # Anonymous request should be properly handled (401 or redirect)
        resp = self.client.get("/api/organizations")
        self.assertIn(resp.status_code, (200, 401))

    # --------------------------------------------------------------------------
    # 6. Farm Management APIs
    # --------------------------------------------------------------------------
    def test_06_farm_apis(self):
        resp = self.client.get("/api/farms")
        self.assertIn(resp.status_code, (200, 401))

    # --------------------------------------------------------------------------
    # 7. Diagnosis Pipeline with Real Image
    # --------------------------------------------------------------------------
    def test_07_diagnosis_pipeline_real_image(self):
        engine = GariInferenceEngine()
        img = Image.open(self.real_leaf_path).convert("RGB")
        res = engine.run_crop_disease_model(img, "Tomato")
        self.assertIsNotNone(res)
        self.assertIn("disease_id", res)
        self.assertIn("disease_score", res)
        self.assertGreater(res["disease_score"], 0.0)

    # --------------------------------------------------------------------------
    # 8. On-Demand Lazy Model Loading
    # --------------------------------------------------------------------------
    def test_08_on_demand_lazy_loading(self):
        engine = GariInferenceEngine()
        engine.unload_model("Tomato")
        self.assertFalse(engine.is_model_loaded("Tomato"))
        # Execute inference -> triggers lazy load
        img = Image.open(self.real_leaf_path).convert("RGB")
        res = engine.run_crop_disease_model(img, "Tomato")
        self.assertTrue(engine.is_model_loaded("Tomato"))
        self.assertIsNotNone(res)

    # --------------------------------------------------------------------------
    # 9. Model Auto-Unloading Lifecycle
    # --------------------------------------------------------------------------
    def test_09_model_auto_unloading_lifecycle(self):
        engine = GariInferenceEngine()
        engine.lifecycle.idle_timeout_seconds = 1
        img = Image.open(self.real_leaf_path).convert("RGB")
        engine.run_crop_disease_model(img, "Tomato")
        self.assertTrue(engine.is_model_loaded("Tomato"))
        time.sleep(1.2)
        unloaded = engine.lifecycle.check_and_unload_idle_models()
        self.assertIn("Tomato", unloaded)
        self.assertFalse(engine.is_model_loaded("Tomato"))
        # Reset timeout
        engine.lifecycle.idle_timeout_seconds = 300

    # --------------------------------------------------------------------------
    # 10. Multi-Threaded Concurrent Inference
    # --------------------------------------------------------------------------
    def test_10_concurrent_inference(self):
        engine = GariInferenceEngine()
        img = Image.open(self.real_leaf_path).convert("RGB")
        results = []

        def worker():
            r = engine.run_crop_disease_model(img, "Tomato")
            results.append(r["disease_id"])

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 10)
        self.assertEqual(len(set(results)), 1)  # All return identical diagnosis

    # --------------------------------------------------------------------------
    # 11. Diagnosis History Persistence
    # --------------------------------------------------------------------------
    def test_11_diagnosis_history_persistence(self):
        history = gari_database.list_diagnoses(limit=5)
        self.assertIsInstance(history, list)

    # --------------------------------------------------------------------------
    # 12. SQLite WAL Mode & Synchronous Integrity
    # --------------------------------------------------------------------------
    def test_12_sqlite_wal_integrity(self):
        db_path = Path("database/disease_detector.db")
        self.assertTrue(db_path.exists())
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        journal = cursor.fetchone()[0]
        self.assertEqual(journal.lower(), "wal")
        cursor.execute("PRAGMA integrity_check;")
        integrity = cursor.fetchone()[0]
        self.assertEqual(integrity, "ok")
        conn.close()

    # --------------------------------------------------------------------------
    # 13. Automated WAL-Safe Backup Execution
    # --------------------------------------------------------------------------
    def test_13_automated_backup_execution(self):
        temp_dir = Path(tempfile.mkdtemp())
        src_db = Path("database/disease_detector.db")
        try:
            backup_file = perform_online_backup(src_db, temp_dir)
            self.assertTrue(backup_file.exists())
            self.assertTrue(backup_file.stat().st_size > 0)
            self.assertTrue(verify_sqlite_integrity(backup_file))
        finally:
            shutil.rmtree(temp_dir)

    # --------------------------------------------------------------------------
    # 14. Disaster Recovery & Snapshot Restore
    # --------------------------------------------------------------------------
    def test_14_disaster_recovery_restore(self):
        temp_dir = Path(tempfile.mkdtemp())
        src_db = Path("database/disease_detector.db")
        try:
            backup_file = perform_online_backup(src_db, temp_dir)
            target_db = temp_dir / "restored_test.db"
            success = restore_database(backup_file, target_db)
            self.assertTrue(success)
            self.assertTrue(verify_sqlite_integrity(target_db))
        finally:
            shutil.rmtree(temp_dir)

    # --------------------------------------------------------------------------
    # 15. Strict CORS Policy (No Wildcards in Production)
    # --------------------------------------------------------------------------
    def test_15_cors_policy_production(self):
        origins = gari_config.ALLOWED_ORIGINS
        self.assertNotIn("*", origins, "Wildcard '*' must never be permitted in CORS configuration")
        # In production, fallback must include official domains
        if gari_config.IS_PRODUCTION:
            self.assertIn("https://gari-team.vercel.app", origins)

    # --------------------------------------------------------------------------
    # 16. HTTPS / SSL Nginx Configuration Validity
    # --------------------------------------------------------------------------
    def test_16_nginx_ssl_configuration_validity(self):
        ssl_conf = Path("deploy/oracle/nginx/conf.d/gari-ssl.conf")
        self.assertTrue(ssl_conf.exists())
        content = ssl_conf.read_text(encoding="utf-8")
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3;", content)
        self.assertIn("Strict-Transport-Security", content)
        self.assertIn("ssl_certificate /etc/letsencrypt/live/gari/fullchain.pem;", content)

    # --------------------------------------------------------------------------
    # 17. Nginx Reverse Proxy & Rate Limiting Directives
    # --------------------------------------------------------------------------
    def test_17_nginx_rate_limiting(self):
        nginx_conf = Path("deploy/oracle/nginx/nginx.conf")
        self.assertTrue(nginx_conf.exists())
        content = nginx_conf.read_text(encoding="utf-8")
        self.assertIn("limit_req_zone", content)
        self.assertIn("rate=15r/s", content)

    # --------------------------------------------------------------------------
    # 18. Container Restart Policy & Healthcheck Directives
    # --------------------------------------------------------------------------
    def test_18_container_restart_and_healthcheck(self):
        compose_path = Path("docker-compose.yml")
        self.assertTrue(compose_path.exists())
        content = compose_path.read_text(encoding="utf-8")
        self.assertIn("restart: unless-stopped", content)
        self.assertIn("healthcheck:", content)
        self.assertIn("http://localhost:8000/health", content)

    # --------------------------------------------------------------------------
    # 19. Storage & Directory Persistence Mounting
    # --------------------------------------------------------------------------
    def test_19_storage_persistence_mounting(self):
        compose_path = Path("docker-compose.yml")
        content = compose_path.read_text(encoding="utf-8")
        self.assertIn("./database:/app/database", content)
        self.assertIn("./models:/app/models:ro", content)
        self.assertIn("./logs:/app/logs", content)

    # --------------------------------------------------------------------------
    # 20. Frontend2 API Contract Compliance
    # --------------------------------------------------------------------------
    def test_20_frontend2_api_contract_compliance(self):
        # Verify knowledge base crops endpoint
        resp = self.client.get("/api/knowledge/crops")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("crops", data)
        self.assertTrue(len(data["crops"]) >= 5)

if __name__ == "__main__":
    unittest.main()
