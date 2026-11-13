# GARI — Hybrid AI Worker Implementation & Queue Architecture
**Document:** `docs/GARI_AI_WORKER_IMPLEMENTATION.md`  
**Date:** November 13, 2026  
**Status:** IMPLEMENTED & TESTED (12/12 TESTS PASSED)  
**Priority:** HYBRID CLOUD AI WORKER

---

## 1. Architectural Mission & Overview

In the GARI Hybrid Cloud model, heavy agricultural AI inference (PyTorch, ConvNeXt, Vision Transformers, Swin Transformer, Grad-CAM heatmap generation) remains localized on high-performance machines (e.g. the developer's Windows PC equipped with GPU/high RAM), while all user-facing SaaS services run 24/7 on cloud infrastructure.

The **GARI Hybrid AI Worker** (`worker/gari_ai_worker.py`) is an autonomous background daemon that pulls pending diagnosis requests from the cloud queue via outbound HTTPS polling.

### Key Architectural Advantages:
1. **Zero Inbound Attack Surface:** No inbound ports, no dynamic DNS, no static IP, and no Cloudflare Tunnel dependencies are needed on the local PC.
2. **Atomic Concurrency:** Multiple worker nodes can run concurrently without race conditions; PostgreSQL `FOR UPDATE SKIP LOCKED` guarantees that each job is claimed by exactly one worker.
3. **Resilience & Lease Heartbeating:** Active jobs emit heartbeat pings every 15 seconds. If a worker abruptly powers off or loses connectivity, the job's lease expires and it is safely recovered back into the queue.
4. **Zero PHP:** Built strictly with Python 3, PyTorch, PIL, and standard REST PostgREST protocols.

---

## 2. Worker Lifecycle & Protocol

```
+-----------------------------------------------------------------------------------+
|                            POSTGRESQL QUEUE PROTOCOL                              |
+-----------------------------------------------------------------------------------+
                                        |
  1. claim_next_diagnosis_job(worker_id, lock_duration=120) [FOR UPDATE SKIP LOCKED]
                                        v
                            [ Status: processing ]
                                        |
                     +------------------+------------------+
                     |                                     |
    [Heartbeat Thread (every 15s)]               [Inference Pipeline]
    update_diagnosis_job_heartbeat()             1. Fetch image bytes
                     |                           2. Leaf validation gate
                     |                           3. ConvNeXt / ViT inference
                     |                           4. Treatment recommendations
                     |                                     |
                     +------------------+------------------+
                                        |
                                        v
                    Is inference successful and valid?
                                   /         \
                              YES /           \ NO / ERROR
                                 v             v
       complete_diagnosis_job(job_id, res)    fail_diagnosis_job(job_id, error)
            [ Status: completed ]                 [ Status: failed ]
            - Inserts public.diagnoses
            - Sends public.notifications
```

---

## 3. Implementation Details (`worker/gari_ai_worker.py`)

### 3.1. Atomic Job Claiming
```python
def claim_job(self, lock_duration: int = 120) -> Optional[Dict[str, Any]]:
    data = self._call_rpc(
        "claim_next_diagnosis_job",
        {"p_worker_id": self.worker_id, "p_lock_duration_seconds": lock_duration},
        timeout=5.0
    )
    ...
```

### 3.2. Resilient Multi-Source Image Retrieval
The worker supports flexible image input formats:
1. **Base64 Data URIs:** `data:image/jpeg;base64,...` decoded in-memory.
2. **Remote URLs:** `http://` or `https://` retrieved with bounded 15-second timeouts.
3. **Supabase Storage:** Authenticated retrieval from `diagnosis_uploads` or public buckets using the service-role token.
4. **Local Disk:** Fallback for offline integration testing.

### 3.3. Long-Running Task Heartbeat Thread
During heavy inference tasks or Grad-CAM generation:
- A dedicated daemon thread (`hb-{job_id}`) sends `update_diagnosis_job_heartbeat` pings every 15 seconds (`GARI_HEARTBEAT_INTERVAL`).
- Guaranteed cleanup in a `finally` block ensures heartbeat threads never leak.

### 3.4. Stale Job Recovery Daemon
Every 60 seconds (`GARI_RECOVER_INTERVAL`), the worker calls:
```python
recover_stale_diagnosis_jobs(p_stale_seconds=120)
```
Any job whose worker died or disconnected for >120 seconds is automatically reset to `'queued'` (if `retry_count < 3`) or marked `'failed'`.

### 3.5. Safe Logging & Credential Masking
- The helper `_mask_url()` strips basic auth credentials (`user:pass@`) and query tokens before logging.
- `service_role_key` is strictly injected into HTTP request headers and never logged to stdout, stderr, or logfiles.

---

## 4. Test Verification & Results

The test suite in `tests/test_hybrid_ai_worker.py` validates all 12 operational facets:

| Test Name | Verified Functionality | Status |
|---|---|---|
| `test_url_masking` | Strips user credentials and paths from log messages | **PASSED** |
| `test_worker_initialization` | Validates headers, worker ID, and default intervals | **PASSED** |
| `test_claim_job_success` | Verifies `claim_next_diagnosis_job` RPC invocation | **PASSED** |
| `test_claim_job_empty_queue` | Handles empty queue gracefully without error | **PASSED** |
| `test_fetch_image_base64` | Decodes base64 data URIs into binary image data | **PASSED** |
| `test_fetch_image_http` | Downloads remote images over HTTP/S with timeout | **PASSED** |
| `test_fetch_image_supabase_storage` | Fetches private images from Supabase Storage | **PASSED** |
| `test_process_job_success_lifecycle` | End-to-end claim -> infer -> complete RPC | **PASSED** |
| `test_process_job_failure_lifecycle` | Captures exceptions and calls `fail_diagnosis_job` | **PASSED** |
| `test_heartbeat_during_execution` | Emits active heartbeat during long execution | **PASSED** |
| `test_stale_job_recovery` | Successfully invokes `recover_stale_diagnosis_jobs` | **PASSED** |
| `test_concurrency_two_workers` | Simulates two independent workers processing queue | **PASSED** |

**Execution Result:**
```
Ran 12 tests in 7.576s
OK
```

---

## 5. Worker Startup Instructions

When ready to run the AI Worker on the Windows PC:
```powershell
# Set credentials (or add to .env)
$env:SUPABASE_URL = "https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"

# Launch worker
.venv\Scripts\python worker\gari_ai_worker.py --poll-interval 2.0
```
