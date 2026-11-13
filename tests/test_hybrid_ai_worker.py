"""
GARI Hybrid AI Worker Test Suite
=================================
Validates the worker lifecycle, RPC communication, image decoding,
heartbeat mechanism, failure reporting, and graceful shutdown.

Strict Rules:
- ZERO PHP.
- No production database mutations.
- Mocked PostgREST/Supabase HTTP interactions.
"""

import base64
import io
import time
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

from worker.gari_ai_worker import GariAIWorker, _mask_url


def _create_test_image_bytes(format="JPEG") -> bytes:
    img = Image.new("RGB", (100, 100), color=(50, 150, 50))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


class TestGariAIWorker(unittest.TestCase):
    def setUp(self):
        self.mock_session = MagicMock()
        self.test_url = "https://mockproject.supabase.co"
        self.test_key = "mock-service-role-key-12345"
        self.worker = GariAIWorker(
            supabase_url=self.test_url,
            service_role_key=self.test_key,
            worker_id="test-worker-01",
            poll_interval=0.1,
            heartbeat_interval=0.2,
            recover_interval=1.0,
            http_client=self.mock_session,
        )

    def test_url_masking(self):
        """Ensure sensitive tokens and paths in URLs are safely masked."""
        masked = _mask_url("https://user:pass@myproject.supabase.co/rest/v1/rpc")
        self.assertEqual(masked, "https://myproject.supabase.co")
        self.assertEqual(_mask_url(""), "<not-configured>")

    def test_worker_initialization(self):
        """Worker initializes with expected properties and safe headers."""
        self.assertTrue(self.worker.is_configured)
        self.assertEqual(self.worker.worker_id, "test-worker-01")
        headers = self.worker._rpc_headers()
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["apikey"], self.test_key)
        self.assertEqual(headers["Authorization"], f"Bearer {self.test_key}")

    def test_claim_job_success(self):
        """Worker claims a queued job via RPC."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "job_id": "88888888-8888-8888-8888-888888888888",
                "job_user_id": "11111111-1111-1111-1111-111111111111",
                "job_storage_path": "data:image/jpeg;base64,abc123",
                "job_crop_type": "Rice",
                "job_retry_count": 0,
            }
        ]
        self.mock_session.post.return_value = mock_resp

        job = self.worker.claim_job()
        self.assertIsNotNone(job)
        self.assertEqual(job["job_id"], "88888888-8888-8888-8888-888888888888")
        self.assertEqual(job["job_crop_type"], "Rice")

        # Verify RPC endpoint and payload
        args, kwargs = self.mock_session.post.call_args
        self.assertTrue(args[0].endswith("/rest/v1/rpc/claim_next_diagnosis_job"))
        self.assertEqual(kwargs["json"]["p_worker_id"], "test-worker-01")

    def test_claim_job_empty_queue(self):
        """Worker returns None when no jobs are available."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        self.mock_session.post.return_value = mock_resp

        job = self.worker.claim_job()
        self.assertIsNone(job)

    def test_fetch_image_base64(self):
        """Worker successfully decodes base64 data URI."""
        img_bytes = _create_test_image_bytes("JPEG")
        b64_str = "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode("ascii")
        fetched = self.worker.fetch_image_bytes(b64_str)
        self.assertEqual(fetched, img_bytes)

    def test_fetch_image_http(self):
        """Worker downloads remote image over HTTP."""
        img_bytes = _create_test_image_bytes("PNG")
        mock_resp = MagicMock()
        mock_resp.content = img_bytes
        self.mock_session.get.return_value = mock_resp

        fetched = self.worker.fetch_image_bytes("https://images.example.com/leaf.png")
        self.assertEqual(fetched, img_bytes)
        self.mock_session.get.assert_called_with("https://images.example.com/leaf.png", timeout=15.0)

    def test_fetch_image_supabase_storage(self):
        """Worker downloads from authenticated Supabase Storage endpoint."""
        img_bytes = _create_test_image_bytes("JPEG")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = img_bytes
        self.mock_session.get.return_value = mock_resp

        fetched = self.worker.fetch_image_bytes("diagnosis_uploads/leaf_99.jpg")
        self.assertEqual(fetched, img_bytes)
        args, kwargs = self.mock_session.get.call_args
        self.assertTrue(args[0].endswith("/storage/v1/object/authenticated/diagnosis_uploads/leaf_99.jpg"))

    def test_process_job_success_lifecycle(self):
        """Full end-to-end processing of a job with mock inference and completion."""
        img_bytes = _create_test_image_bytes("JPEG")
        b64_str = "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode("ascii")

        job = {
            "job_id": "99999999-9999-9999-9999-999999999999",
            "job_crop_type": "Tomato",
            "job_storage_path": b64_str,
        }

        # Mock custom inference
        def mock_infer(data, crop, mode):
            return {
                "success": True,
                "crop_id": "Tomato",
                "disease_name_vi": "Bệnh mốc lá cà chua",
                "confidence": 0.94,
                "treatment": "Cắt tỉa lá bệnh và thông thoáng luống.",
            }

        self.worker._custom_inference_fn = mock_infer

        # Mock complete RPC response
        mock_complete_resp = MagicMock()
        mock_complete_resp.json.return_value = True
        self.mock_session.post.return_value = mock_complete_resp

        result = self.worker.process_job(job)
        self.assertTrue(result)

        # Verify complete_diagnosis_job RPC was called
        calls = [c for c in self.mock_session.post.call_args_list if "complete_diagnosis_job" in c[0][0]]
        self.assertEqual(len(calls), 1)
        payload = calls[0][1]["json"]
        self.assertEqual(payload["p_job_id"], "99999999-9999-9999-9999-999999999999")
        self.assertEqual(payload["p_worker_id"], "test-worker-01")
        self.assertEqual(payload["p_result"]["disease_name"], "Bệnh mốc lá cà chua")
        self.assertEqual(payload["p_result"]["confidence"], 0.94)

    def test_process_job_failure_lifecycle(self):
        """Worker handles inference exception by calling fail_diagnosis_job."""
        job = {
            "job_id": "error-job-1111",
            "job_crop_type": "Rice",
            "job_storage_path": "invalid://not-a-valid-scheme",
        }

        # Mock fail RPC response
        mock_fail_resp = MagicMock()
        mock_fail_resp.json.return_value = True
        self.mock_session.post.return_value = mock_fail_resp

        result = self.worker.process_job(job)
        self.assertFalse(result)

        # Verify fail_diagnosis_job RPC was called
        calls = [c for c in self.mock_session.post.call_args_list if "fail_diagnosis_job" in c[0][0]]
        self.assertEqual(len(calls), 1)
        payload = calls[0][1]["json"]
        self.assertEqual(payload["p_job_id"], "error-job-1111")
        self.assertIn("error", payload["p_error"].lower())

    def test_heartbeat_during_execution(self):
        """Worker emits heartbeat during longer processing tasks."""
        img_bytes = _create_test_image_bytes("JPEG")
        b64_str = "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode("ascii")

        job = {
            "job_id": "heartbeat-job-2222",
            "job_crop_type": "Rice",
            "job_storage_path": b64_str,
        }

        def slow_infer(data, crop, mode):
            time.sleep(0.5)  # heartbeat_interval is 0.2s, so at least 1-2 heartbeats should fire
            return {"success": True, "disease_name_vi": "Đốm lá", "confidence": 0.85}

        self.worker._custom_inference_fn = slow_infer
        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = True
        self.mock_session.post.return_value = mock_post_resp

        self.worker.process_job(job)

        hb_calls = [c for c in self.mock_session.post.call_args_list if "update_diagnosis_job_heartbeat" in c[0][0]]
        self.assertGreaterEqual(len(hb_calls), 1)

    def test_stale_job_recovery(self):
        """Worker triggers recover_stale_diagnosis_jobs RPC."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = 2  # recovered 2 jobs
        self.mock_session.post.return_value = mock_resp

        count = self.worker.recover_stale_jobs()
        self.assertEqual(count, 2)
        args, kwargs = self.mock_session.post.call_args
        self.assertTrue(args[0].endswith("/rest/v1/rpc/recover_stale_diagnosis_jobs"))
        self.assertEqual(kwargs["json"]["p_stale_seconds"], 120)

    def test_concurrency_two_workers(self):
        """Simulate two workers pulling jobs from the queue."""
        w1 = GariAIWorker(
            supabase_url=self.test_url,
            service_role_key=self.test_key,
            worker_id="worker-node-1",
            http_client=self.mock_session,
        )
        w2 = GariAIWorker(
            supabase_url=self.test_url,
            service_role_key=self.test_key,
            worker_id="worker-node-2",
            http_client=self.mock_session,
        )

        # Worker 1 gets job A
        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = [{"job_id": "job-aaa", "job_crop_type": "Corn", "job_storage_path": "path/a"}]
        self.mock_session.post.return_value = mock_resp1
        job1 = w1.claim_job()

        # Worker 2 gets job B
        mock_resp2 = MagicMock()
        mock_resp2.json.return_value = [{"job_id": "job-bbb", "job_crop_type": "Soybean", "job_storage_path": "path/b"}]
        self.mock_session.post.return_value = mock_resp2
        job2 = w2.claim_job()

        self.assertEqual(job1["job_id"], "job-aaa")
        self.assertEqual(job2["job_id"], "job-bbb")
        self.assertNotEqual(job1["job_id"], job2["job_id"])


if __name__ == "__main__":
    unittest.main()
