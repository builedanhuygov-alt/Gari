"""
GARI Hybrid AI Worker
=====================
Decoupled background worker for AI plant disease diagnosis inference.

Features:
- Outbound-only polling over HTTPS (no open ports or inbound tunnels needed on the Windows PC).
- Atomic job claiming via PostgreSQL RPC `claim_next_diagnosis_job` (FOR UPDATE SKIP LOCKED).
- Active background heartbeat during inference via `update_diagnosis_job_heartbeat`.
- Stale job automatic recovery via `recover_stale_diagnosis_jobs`.
- Clean completion via `complete_diagnosis_job` or failure via `fail_diagnosis_job`.
- Resilient image retrieval (HTTP/S URL, base64 data URI, Supabase Storage, or local disk).
- Graceful shutdown on SIGINT/SIGTERM with resource cleanup.
- Zero PHP, zero credential exposure in logs.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests

logger = logging.getLogger("gari_ai_worker")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] [AI_WORKER] %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


def _mask_url(url: str) -> str:
    """Mask credentials and paths in URLs for safe logging."""
    if not url:
        return "<not-configured>"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or parsed.netloc
        port_part = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{host}{port_part}"
    except Exception:
        return "<invalid-url>"


class GariAIWorker:
    """
    Autonomous AI Inference Worker for GARI Hybrid Cloud.
    Polls the durable diagnosis_jobs queue on Supabase/PostgreSQL.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        service_role_key: Optional[str] = None,
        worker_id: Optional[str] = None,
        poll_interval: float = 2.0,
        heartbeat_interval: float = 15.0,
        recover_interval: float = 60.0,
        stale_threshold_seconds: int = 120,
        http_client: Optional[requests.Session] = None,
        inference_fn: Optional[Callable[[bytes, Optional[str], Optional[str]], Dict[str, Any]]] = None,
    ):
        self.supabase_url = (
            supabase_url
            or os.getenv("SUPABASE_URL")
            or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
            or ""
        ).rstrip("/")

        self.service_role_key = (
            service_role_key
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_KEY")
            or ""
        ).strip()

        hostname = socket.gethostname().split(".")[0]
        self.worker_id = worker_id or os.getenv("GARI_WORKER_ID") or f"worker-{hostname}-{uuid.uuid4().hex[:6]}"

        self.poll_interval = float(os.getenv("GARI_POLL_INTERVAL", str(poll_interval)))
        self.heartbeat_interval = float(os.getenv("GARI_HEARTBEAT_INTERVAL", str(heartbeat_interval)))
        self.recover_interval = float(os.getenv("GARI_RECOVER_INTERVAL", str(recover_interval)))
        self.stale_threshold_seconds = int(os.getenv("GARI_STALE_THRESHOLD", str(stale_threshold_seconds)))

        self._session = http_client or requests.Session()
        self._custom_inference_fn = inference_fn
        self._stop_event = threading.Event()
        self._last_recover_time = 0.0

        # Pre-warm or verify local inference engine if not custom fn
        self._engine = None
        if not self._custom_inference_fn:
            try:
                import gari_inference_engine
                self._engine = getattr(gari_inference_engine, "engine", None)
            except Exception as e:
                logger.warning("Local gari_inference_engine not directly importable: %s", e)

        logger.info(
            "Worker initialized | worker_id=%s supabase_url=%s poll_interval=%.1fs",
            self.worker_id,
            _mask_url(self.supabase_url),
            self.poll_interval,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.supabase_url and self.service_role_key)

    def _rpc_headers(self) -> Dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _call_rpc(self, fn_name: str, params: Dict[str, Any], timeout: float = 10.0) -> Any:
        """Execute a Supabase PostgREST RPC call securely."""
        if not self.is_configured:
            raise RuntimeError("Cannot call RPC: Supabase URL and service-role key must be configured.")

        endpoint = f"{self.supabase_url}/rest/v1/rpc/{fn_name}"
        resp = self._session.post(endpoint, headers=self._rpc_headers(), json=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def claim_job(self, lock_duration: int = 120) -> Optional[Dict[str, Any]]:
        """Atomically claim the next queued diagnosis job."""
        try:
            data = self._call_rpc(
                "claim_next_diagnosis_job",
                {"p_worker_id": self.worker_id, "p_lock_duration_seconds": lock_duration},
                timeout=5.0,
            )
            if not data:
                return None
            if isinstance(data, list):
                return data[0] if len(data) > 0 else None
            if isinstance(data, dict):
                return data
            return None
        except requests.HTTPError as he:
            logger.error("claim_job HTTP error: %s (status=%s)", he, getattr(he.response, "status_code", None))
            return None
        except Exception as e:
            logger.error("claim_job connection error: %s", type(e).__name__)
            return None

    def heartbeat(self, job_id: str) -> bool:
        """Update job heartbeat timestamp to prevent stale job reclaim."""
        try:
            res = self._call_rpc(
                "update_diagnosis_job_heartbeat",
                {"p_job_id": job_id, "p_worker_id": self.worker_id},
                timeout=5.0,
            )
            return bool(res)
        except Exception as e:
            logger.warning("Heartbeat failed for job %s: %s", job_id, e)
            return False

    def complete_job(self, job_id: str, result: Dict[str, Any]) -> bool:
        """Mark job completed and persist diagnosis result."""
        try:
            res = self._call_rpc(
                "complete_diagnosis_job",
                {"p_job_id": job_id, "p_worker_id": self.worker_id, "p_result": result},
                timeout=10.0,
            )
            return bool(res)
        except Exception as e:
            logger.error("complete_job failed for job %s: %s", job_id, e)
            return False

    def fail_job(self, job_id: str, error_message: str) -> bool:
        """Mark job failed with diagnostic error message."""
        try:
            res = self._call_rpc(
                "fail_diagnosis_job",
                {"p_job_id": job_id, "p_worker_id": self.worker_id, "p_error": error_message[:1000]},
                timeout=10.0,
            )
            return bool(res)
        except Exception as e:
            logger.error("fail_job failed for job %s: %s", job_id, e)
            return False

    def recover_stale_jobs(self) -> int:
        """Check for and recover jobs abandoned by dead workers."""
        try:
            res = self._call_rpc(
                "recover_stale_diagnosis_jobs",
                {"p_stale_seconds": self.stale_threshold_seconds},
                timeout=10.0,
            )
            count = int(res) if res is not None else 0
            if count > 0:
                logger.info("Recovered %d stale diagnosis jobs back to queue", count)
            return count
        except Exception as e:
            logger.warning("recover_stale_jobs warning: %s", e)
            return 0

    def fetch_image_bytes(self, storage_path: str) -> bytes:
        """
        Fetch image bytes from URL, base64 data URI, Supabase Storage, or local disk.
        """
        if not storage_path or not storage_path.strip():
            raise ValueError("Empty image storage path.")

        path = storage_path.strip()

        # 1. Base64 Data URI
        if path.startswith("data:image/"):
            try:
                header, encoded = path.split(",", 1)
                return base64.b64decode(encoded)
            except Exception as e:
                raise ValueError(f"Failed to decode base64 data URI: {e}")

        # 2. Remote HTTP/HTTPS URL
        if path.startswith("http://") or path.startswith("https://"):
            resp = self._session.get(path, timeout=15.0)
            resp.raise_for_status()
            return resp.content

        # 3. Local filesystem path (for offline / testing)
        local_p = Path(path)
        if local_p.is_file():
            return local_p.read_bytes()

        # 4. Supabase Storage path (e.g. 'leaf-images/job_123.jpg')
        if self.supabase_url and self.service_role_key:
            # First try authenticated storage endpoint
            storage_url = f"{self.supabase_url}/storage/v1/object/authenticated/{path.lstrip('/')}"
            headers = {"Authorization": f"Bearer {self.service_role_key}", "apikey": self.service_role_key}
            resp = self._session.get(storage_url, headers=headers, timeout=15.0)
            if resp.status_code == 200:
                return resp.content

            # Second try public storage endpoint
            public_url = f"{self.supabase_url}/storage/v1/object/public/{path.lstrip('/')}"
            resp2 = self._session.get(public_url, timeout=15.0)
            if resp2.status_code == 200:
                return resp2.content

        raise FileNotFoundError(f"Could not retrieve image data from path: '{storage_path[:120]}'")

    def run_inference(self, image_data: bytes, crop_hint: Optional[str] = None) -> Dict[str, Any]:
        """Run plant disease diagnosis using the active engine."""
        if self._custom_inference_fn:
            return self._custom_inference_fn(image_data, crop_hint, "auto_standard")

        if self._engine and hasattr(self._engine, "predict"):
            return self._engine.predict(
                image_data,
                crop_id=crop_hint if crop_hint and crop_hint.lower() not in ("auto", "none") else None,
                mode="auto_standard",
            )

        # Standalone mock/fallback for testing or host without AI models
        logger.warning("No inference engine configured. Returning simulated diagnosis.")
        return {
            "success": True,
            "status": "classified",
            "crop_id": crop_hint or "Rice",
            "disease_name_vi": "Đốm lá vi khuẩn",
            "confidence": 0.92,
            "recommendation": "Phun thuốc gốc đồng hoặc kasugamycin định kỳ vào buổi sáng sớm.",
            "is_simulated": True,
        }

    def process_job(self, job: Dict[str, Any]) -> bool:
        """
        Process a single claimed diagnosis job end-to-end with heartbeat protection.
        """
        job_id = str(job.get("job_id") or job.get("id"))
        crop_type = job.get("job_crop_type") or job.get("crop_type") or "auto"
        storage_path = job.get("job_storage_path") or job.get("storage_path") or ""

        logger.info("[JOB_START] Claimed job_id=%s crop=%s path=%s", job_id, crop_type, storage_path[:60])

        # Start periodic heartbeat thread
        heartbeat_stop = threading.Event()

        def _heartbeat_worker():
            while not heartbeat_stop.wait(timeout=self.heartbeat_interval):
                if not self.heartbeat(job_id):
                    logger.warning("[HEARTBEAT_WARN] Heartbeat ping failed for %s", job_id)

        hb_thread = threading.Thread(target=_heartbeat_worker, daemon=True, name=f"hb-{job_id[:8]}")
        hb_thread.start()

        start_time = time.perf_counter()
        try:
            # 1. Fetch image bytes
            image_data = self.fetch_image_bytes(storage_path)

            # 2. Run inference
            t_inf_start = time.perf_counter()
            raw_res = self.run_inference(image_data, crop_hint=crop_type)
            inf_ms = (time.perf_counter() - t_inf_start) * 1000

            # 3. Format result payload for complete_diagnosis_job
            disease_name = (
                raw_res.get("disease_name_vi")
                or raw_res.get("disease_id")
                or raw_res.get("prediction")
                or "Cây khỏe / Chưa xác định bệnh"
            )
            confidence = float(raw_res.get("confidence") or 0.0)
            treatment = (
                raw_res.get("treatment")
                or raw_res.get("recommendation")
                or raw_res.get("message")
                or "Theo dõi và duy trì chế độ chăm sóc tiêu chuẩn."
            )

            result_payload = {
                "disease_name": disease_name,
                "confidence": confidence,
                "treatment": treatment,
                "crop_type": raw_res.get("crop_id") or crop_type,
                "status": raw_res.get("status", "completed"),
                "inference_time_ms": round(inf_ms, 2),
                "worker_id": self.worker_id,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "details": {k: v for k, v in raw_res.items() if k not in ("image_bytes",)},
            }

            # 4. Mark complete
            success = self.complete_job(job_id, result_payload)
            elapsed_total = (time.perf_counter() - start_time) * 1000
            if success:
                logger.info(
                    "[JOB_SUCCESS] job_id=%s disease='%s' conf=%.2f inf=%.1fms total=%.1fms",
                    job_id,
                    disease_name,
                    confidence,
                    inf_ms,
                    elapsed_total,
                )
            else:
                logger.error("[JOB_ERROR] complete_job returned false for %s", job_id)
            return success

        except Exception as e:
            elapsed_total = (time.perf_counter() - start_time) * 1000
            err_msg = f"{type(e).__name__}: {str(e)}"
            logger.error("[JOB_FAILED] job_id=%s elapsed=%.1fms error=%s", job_id, elapsed_total, err_msg)
            self.fail_job(job_id, err_msg)
            return False

        finally:
            heartbeat_stop.set()
            hb_thread.join(timeout=1.0)

    def stop(self) -> None:
        """Signal the worker to exit after current cycle."""
        logger.info("Shutdown requested. Stopping worker loop...")
        self._stop_event.set()

    def run_loop(self) -> None:
        """Main daemon loop."""
        logger.info("GARI AI Worker started. Awaiting jobs...")

        # Setup graceful signal handlers
        def _handle_sig(sig, frame):
            logger.info("Signal %s received", sig)
            self.stop()

        try:
            signal.signal(signal.SIGINT, _handle_sig)
            signal.signal(signal.SIGTERM, _handle_sig)
        except Exception:
            pass  # Some environments don't support signal binding in threads

        while not self._stop_event.is_set():
            try:
                # 1. Periodic stale job recovery check
                now = time.time()
                if now - self._last_recover_time > self.recover_interval:
                    self.recover_stale_jobs()
                    self._last_recover_time = now

                # 2. Check for next job
                job = self.claim_job()
                if job:
                    self.process_job(job)
                    # Quickly poll again if work is active
                    continue

                # 3. Idle sleep
                self._stop_event.wait(timeout=self.poll_interval)

            except Exception as loop_err:
                logger.error("Unexpected worker loop error: %s", loop_err)
                self._stop_event.wait(timeout=self.poll_interval)

        logger.info("Worker loop stopped cleanly.")


def main():
    """CLI entrypoint for running the AI worker process directly."""
    import argparse

    parser = argparse.ArgumentParser(description="GARI Hybrid Cloud AI Inference Worker")
    parser.add_argument("--url", default=None, help="Supabase Project URL")
    parser.add_argument("--key", default=None, help="Supabase Service Role Key")
    parser.add_argument("--worker-id", default=None, help="Unique worker identifier")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Poll interval in seconds")
    parser.add_argument("--recover-interval", type=float, default=60.0, help="Stale recovery check interval")
    args = parser.parse_args()

    worker = GariAIWorker(
        supabase_url=args.url,
        service_role_key=args.key,
        worker_id=args.worker_id,
        poll_interval=args.poll_interval,
        recover_interval=args.recover_interval,
    )

    if not worker.is_configured:
        logger.warning(
            "Worker starting in UNCONFIGURED mode (no SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY). "
            "Please provide credentials in environment or CLI."
        )

    try:
        worker.run_loop()
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    main()
