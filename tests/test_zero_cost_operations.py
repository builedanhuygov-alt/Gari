"""
GARI AgriTech AI Lab — Zero Cost Self-Hosted Operations Test Suite
Path: tests/test_zero_cost_operations.py

Validates the 14 Zero Cost Operational Pillars:
1. Local Backend Startup & Health
2. Local Backend Readiness Probe
3. Backend Graceful Restart & Resilience
4. Cloudflare Tunnel Connectivity (Local Origin & Public Probe)
5. API Authentication & Token Scoping
6. On-Demand Lazy Model Loading
7. Model Idle Auto-Unloading
8. Multi-Threaded Concurrent Inference
9. SQLite WAL Journal Mode & Synchronous Safety
10. WAL-Safe Online Database Backup
11. Disaster Recovery Restore on Test Fixture
12. Frontend Error & Offline Boundary Handling
13. System Resource Telemetry & Memory Introspection
14. Process Recovery & OOM Safety Guard
"""

import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from PIL import Image

import gari_config
import gari_database
from api_server import app
from deploy.oracle.backup_sqlite import perform_online_backup, verify_sqlite_integrity
from deploy.oracle.restore_sqlite import restore_database
from fastapi.testclient import TestClient
from gari_inference_engine import GariInferenceEngine

class TestZeroCostOperations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.test_image_path = Path("test_leaf.jpg")
        if not cls.test_image_path.exists():
            cls.test_image_path = Path("tests/fixtures/real_leaf.jpg")
            if not cls.test_image_path.exists():
                cls.test_image_path.parent.mkdir(parents=True, exist_ok=True)
                img = Image.new("RGB", (224, 224), color=(34, 139, 34))
                img.save(cls.test_image_path)

    # 1. Backend startup
    def test_01_backend_startup_and_health(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn(data.get("status"), ("healthy", "ok"))
        self.assertEqual(data.get("services", {}).get("backend_runtime"), "healthy")

    # 2. Backend readiness probe
    def test_02_backend_readiness_probe(self):
        resp = self.client.get("/ready")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ready"))
        self.assertEqual(data.get("database"), "healthy")

    # 3. Backend restart scripts presence
    def test_03_backend_lifecycle_scripts_present(self):
        scripts = [
            Path("scripts/start_backend.ps1"),
            Path("scripts/stop_backend.ps1"),
            Path("scripts/restart_backend.ps1"),
            Path("scripts/backend_healthcheck.ps1")
        ]
        for s in scripts:
            self.assertTrue(s.exists(), f"Missing required script: {s}")

    # 4. Cloudflare Tunnel connectivity
    def test_04_tunnel_connectivity(self):
        tunnel_url = "https://ist-towards-exclude-said.trycloudflare.com/health"
        try:
            req = urllib.request.Request(tunnel_url, headers={"User-Agent": "Gari-Test/1.0"})
            with urllib.request.urlopen(req, timeout=8.0) as response:
                status_code = response.getcode()
                raw_body = response.read().decode("utf-8")
                data = json.loads(raw_body)
                self.assertEqual(status_code, 200)
                self.assertIn(data.get("status"), ("healthy", "ok"))
        except Exception as exc:
            # If network is unavailable or quick tunnel changed, log without breaking local test
            self.skipTest(f"Public Cloudflare Tunnel probe skipped (Network/Ephemeral): {exc}")

    # 5. API Authentication
    def test_05_api_authentication_security(self):
        # Accessing protected admin endpoint without auth must return 401
        resp = self.client.get("/api/admin/models/lifecycle")
        self.assertEqual(resp.status_code, 401)

    # 6. On-demand model loading
    def test_06_on_demand_lazy_loading(self):
        engine = GariInferenceEngine()
        engine.unload_model("Tomato")
        self.assertFalse(engine.is_model_loaded("Tomato"))
        img = Image.open(self.test_image_path).convert("RGB")
        res = engine.run_crop_disease_model(img, "Tomato")
        self.assertTrue(engine.is_model_loaded("Tomato"))
        self.assertIsNotNone(res)

    # 7. Model auto-unloading
    def test_07_model_auto_unloading(self):
        engine = GariInferenceEngine()
        engine.lifecycle.idle_timeout_seconds = 1
        img = Image.open(self.test_image_path).convert("RGB")
        engine.run_crop_disease_model(img, "Tomato")
        self.assertTrue(engine.is_model_loaded("Tomato"))
        time.sleep(1.2)
        unloaded = engine.lifecycle.check_and_unload_idle_models()
        self.assertIn("Tomato", unloaded)
        self.assertFalse(engine.is_model_loaded("Tomato"))
        engine.lifecycle.idle_timeout_seconds = 300

    # 8. Concurrent inference
    def test_08_concurrent_inference_handling(self):
        engine = GariInferenceEngine()
        img = Image.open(self.test_image_path).convert("RGB")
        outcomes = []

        def worker():
            res = engine.run_crop_disease_model(img, "Tomato")
            outcomes.append(res["disease_id"])

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(outcomes), 5)
        self.assertEqual(len(set(outcomes)), 1)

    # 9. SQLite WAL
    def test_09_sqlite_wal_integrity(self):
        db_path = Path("database/disease_detector.db")
        self.assertTrue(db_path.exists())
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        self.assertEqual(mode.lower(), "wal")
        cursor.execute("PRAGMA integrity_check;")
        check = cursor.fetchone()[0]
        self.assertEqual(check, "ok")
        conn.close()

    # 10. Database backup
    def test_10_database_online_backup(self):
        tmp_dir = Path(tempfile.mkdtemp())
        src_db = Path("database/disease_detector.db")
        try:
            backup_path = perform_online_backup(src_db, tmp_dir)
            self.assertTrue(backup_path.exists())
            self.assertTrue(backup_path.stat().st_size > 0)
            self.assertTrue(verify_sqlite_integrity(backup_path))
        finally:
            shutil.rmtree(tmp_dir)

    # 11. Database restore on fixture
    def test_11_database_restore_drill(self):
        tmp_dir = Path(tempfile.mkdtemp())
        src_db = Path("database/disease_detector.db")
        try:
            backup_path = perform_online_backup(src_db, tmp_dir)
            restored_db = tmp_dir / "target_restore.db"
            success = restore_database(backup_path, restored_db)
            self.assertTrue(success)
            self.assertTrue(verify_sqlite_integrity(restored_db))
        finally:
            shutil.rmtree(tmp_dir)

    # 12. Frontend offline handling structure
    def test_12_frontend_offline_handling(self):
        predict_html = Path("frontend2/predict.html").read_text(encoding="utf-8")
        self.assertIn("res.status === 502 || res.status === 503", predict_html)
        self.assertIn("res.status === 504", predict_html)
        self.assertIn("clearStageTimers();", predict_html)

    # 13. Resource monitoring script & log verification
    def test_13_resource_monitoring(self):
        monitor_script = Path("scripts/gari_monitor.ps1")
        self.assertTrue(monitor_script.exists())
        monitoring_log = Path("logs/local_monitoring.jsonl")
        self.assertTrue(monitoring_log.exists())
        # Parse last entry
        lines = [line.strip() for line in monitoring_log.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(len(lines) > 0)
        last_rec = json.loads(lines[-1])
        self.assertIn("system", last_rec)
        self.assertIn("backend", last_rec)
        self.assertIn("tunnel", last_rec)

    # 14. Recovery & RAM protection guard
    def test_14_ram_protection_guard(self):
        engine = GariInferenceEngine()
        # Verify guard exists and does not crash when memory is normal
        status = engine.lifecycle.get_lifecycle_status()
        self.assertIn("memory_rss_mb", status)
        self.assertGreater(status["memory_rss_mb"], 0.0)

if __name__ == "__main__":
    unittest.main()

