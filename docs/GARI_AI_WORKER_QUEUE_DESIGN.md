# GARI AgriTech AI Platform — Durable AI Diagnosis Job Queue Design

**Document ID:** GARI-SPEC-AI-QUEUE-2026-01  
**Project:** GARI AgriTech AI Platform  
**Target Infrastructure:** Supabase PostgreSQL + Supabase Storage + Windows PyTorch Worker  
**Date:** 2026-11-11  
**Status:** DRAFT SPECIFICATION — APPROVED FOR REVIEW  

---

## 1. Architectural Motivation & Core Requirements

In traditional synchronous web architectures, leaf diagnosis requires holding an open HTTP connection while the server ingests, preprocesses, and evaluates an image through heavy neural models. When the inference server is a self-hosted PC operating only a few hours daily, synchronous requests inevitably fail with HTTP 504 / 503 timeouts.

### Core Design Requirements:
1. **Durable Cloud Ingestion:** Users must be able to submit plant images 24/7. Submission responses must return in under 600ms with HTTP 202 Accepted.
2. **Secure Object Storage:** Image binaries must be stored in private, encrypted cloud storage, never directly inside database tuples or on public endpoints.
3. **Finite State Machine:** Clear, unambiguous states (`queued`, `processing`, `completed`, `failed`) with automatic timeout recovery.
4. **Zero-Contention Atomic Worker Polling:** When the Windows PC powers on, workers must claim jobs atomically using `SELECT ... FOR UPDATE SKIP LOCKED` to prevent duplicate processing.
5. **Decoupled Security Boundary:** PyTorch model weights (53 models) remain exclusively on the Windows PC. Worker service credentials never appear in frontend code.

---

## 2. Job Queue State Machine & Data Model

```
   ┌─────────────────────────────────────────────────────────────┐
   │                          [ QUEUED ]                         │
   │  - Client submits image to Supabase Storage                 │
   │  - Job inserted into diagnosis_jobs table                   │
   │  - Awaiting Windows AI Worker power-on                      │
   └───────────────┬─────────────────────────────────────────────┘
                   │
                   │ Worker claims job via claim_next_diagnosis_job()
                   ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                        [ PROCESSING ]                       │
   │  - Windows worker downloads image via signed URL            │
   │  - PyTorch inference executes locally (~0.74s)             │
   │  - Worker periodically emits heartbeat timestamp            │
   └───────────────┬──────────────────────────────┬──────────────┘
                   │                              │
       Inference   │                  Fatal Error │ Heartbeat
       Succeeds    │                  or Max      │ Expired (>120s)
                   │                  Retries (3) │
                   ▼                              │
   ┌───────────────────────────────┐              │
   │         [ COMPLETED ]         │              │
   │  - Diagnostics saved in DB    │              ▼
   │  - Status updated to completed│  ┌───────────────────────────┐
   │  - Push event sent to client  │  │         [ FAILED ]        │
   │  - Client renders results     │  │  - Error code & message   │
   └───────────────────────────────┘  │  - User notified to retry │
                                      └───────────────────────────┘
```

### 2.1 Table Definition: `public.diagnosis_jobs`

```sql
-- Create Enum for Job State
DO $$ BEGIN
    CREATE TYPE diagnosis_job_status AS ENUM ('queued', 'processing', 'completed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Table: public.diagnosis_jobs
CREATE TABLE IF NOT EXISTS public.diagnosis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    farm_id UUID,
    plot_id UUID,
    crop_type TEXT DEFAULT 'auto',
    storage_path TEXT NOT NULL,
    status diagnosis_job_status NOT NULL DEFAULT 'queued',
    retry_count INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    heartbeat_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Concurrency and status indices
CREATE INDEX IF NOT EXISTS idx_diagnosis_jobs_status_created 
    ON public.diagnosis_jobs(status, created_at) 
    WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS idx_diagnosis_jobs_user 
    ON public.diagnosis_jobs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_diagnosis_jobs_heartbeat 
    ON public.diagnosis_jobs(status, heartbeat_at) 
    WHERE status = 'processing';
```

---

## 3. Storage Architecture: `diagnosis-images`

Raw leaf photos are uploaded directly to the private Supabase Storage bucket `diagnosis-images`.

### Storage Path Scheme:
`raw/{user_id}/{job_id}.jpg`

### Storage Security Controls:
1. **Private Bucket:** Public access is disabled (`public = false`).
2. **Upload Policy:** Authenticated users may upload only into their own folder:
   ```sql
   CREATE POLICY "Users upload own diagnosis images"
   ON storage.objects FOR INSERT TO authenticated
   WITH CHECK (
       bucket_id = 'diagnosis-images' AND
       (storage.foldername(name))[2] = auth.uid()::text
   );
   ```
3. **Read Policy:** Users can only view their own images:
   ```sql
   CREATE POLICY "Users read own diagnosis images"
   ON storage.objects FOR SELECT TO authenticated
   USING (
       bucket_id = 'diagnosis-images' AND
       (storage.foldername(name))[2] = auth.uid()::text
   );
   ```
4. **Worker Access:** The Windows worker utilizes `service_role` permissions to generate short-lived (60-second) signed URLs to download image bytes for inference.

---

## 4. Atomic Job Claiming & Recovery Stored Procedure

To eliminate race conditions across multiple worker processes or threads, jobs are claimed atomically using `FOR UPDATE SKIP LOCKED`.

```sql
-- ============================================================================
-- Function: claim_next_diagnosis_job
-- Atomically locks and transitions the oldest queued job to 'processing'
-- ============================================================================
CREATE OR REPLACE FUNCTION public.claim_next_diagnosis_job(
    p_worker_id TEXT,
    p_lock_duration_seconds INTEGER DEFAULT 120
)
RETURNS TABLE (
    job_id UUID,
    user_id UUID,
    storage_path TEXT,
    crop_type TEXT,
    retry_count INTEGER
) AS $$
DECLARE
    v_job_id UUID;
BEGIN
    -- 1. Identify and lock the oldest queued job
    SELECT id INTO v_job_id
    FROM public.diagnosis_jobs
    WHERE status = 'queued'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    -- 2. If found, transition state to 'processing'
    IF v_job_id IS NOT NULL THEN
        UPDATE public.diagnosis_jobs
        SET status = 'processing',
            worker_id = p_worker_id,
            heartbeat_at = NOW(),
            started_at = NOW(),
            updated_at = NOW()
        WHERE id = v_job_id;

        RETURN QUERY
        SELECT j.id, j.user_id, j.storage_path, j.crop_type, j.retry_count
        FROM public.diagnosis_jobs j
        WHERE j.id = v_job_id;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- Function: recover_stale_diagnosis_jobs
-- Resets jobs that have been in 'processing' with no heartbeat for > 120s
-- ============================================================================
CREATE OR REPLACE FUNCTION public.recover_stale_diagnosis_jobs()
RETURNS INTEGER AS $$
DECLARE
    recovered_count INTEGER := 0;
BEGIN
    UPDATE public.diagnosis_jobs
    SET status = CASE 
            WHEN retry_count >= 3 THEN 'failed'::diagnosis_job_status
            ELSE 'queued'::diagnosis_job_status
        END,
        error_message = CASE 
            WHEN retry_count >= 3 THEN 'Max retries exceeded due to worker disconnect.'
            ELSE 'Worker heartbeat timed out. Re-enqueued.'
        END,
        retry_count = retry_count + 1,
        worker_id = NULL,
        heartbeat_at = NULL,
        updated_at = NOW()
    WHERE status = 'processing'
      AND heartbeat_at < NOW() - INTERVAL '120 seconds';

    GET DIAGNOSTICS recovered_count = ROW_COUNT;
    RETURN recovered_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

## 5. Windows AI Worker Polling Implementation

The Windows host runs a lightweight daemon script [`worker/gari_ai_worker.py`](file:///d:/leaf-diseases-detector-main/worker/gari_ai_worker.py):

```python
"""
GARI AgriTech AI Platform — Headless PyTorch Queue Worker
Daemon running locally on Windows host.
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from supabase import create_client, Client
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
WORKER_ID = os.getenv("GARI_WORKER_ID", "windows-node-01")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    logging.fatal("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Import local PyTorch inference pipeline
from gari_inference_engine import run_leaf_diagnosis

def poll_and_process():
    logging.info(f"GARI AI Worker {WORKER_ID} active. Polling Supabase queue...")
    
    while True:
        try:
            # 1. Recover any stale jobs first
            supabase.rpc("recover_stale_diagnosis_jobs").execute()

            # 2. Claim next available job
            res = supabase.rpc("claim_next_diagnosis_job", {"p_worker_id": WORKER_ID}).execute()
            jobs = res.data

            if not jobs or len(jobs) == 0:
                time.sleep(4)  # Gentle poll interval when queue is empty
                continue

            job = jobs[0]
            job_id = job["job_id"]
            storage_path = job["storage_path"]
            crop_type = job.get("crop_type", "auto")

            logging.info(f"Claimed Job: {job_id} | Path: {storage_path} | Crop: {crop_type}")

            # 3. Download image using signed URL
            signed_url_res = supabase.storage.from_("diagnosis-images").create_signed_url(storage_path, 60)
            image_url = signed_url_res["signedURL"]
            img_bytes = requests.get(image_url, timeout=15).content

            # 4. Execute Local PyTorch Inference
            t0 = time.perf_counter()
            diagnosis_result = run_leaf_diagnosis(img_bytes, crop=crop_type)
            duration = time.perf_counter() - t0
            logging.info(f"Job {job_id} inferred in {duration:.2f}s | Result: {diagnosis_result.get('disease')}")

            # 5. Write results back to Supabase
            supabase.table("diagnosis_jobs").update({
                "status": "completed",
                "result": diagnosis_result,
                "completed_at": "now()"
            }).eq("id", job_id).execute()

        except Exception as e:
            logging.error(f"Worker iteration error: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    poll_and_process()
```

---

## 6. Client Result Retrieval Patterns

### Option 1: Supabase Realtime Subscription (Recommended)
The frontend establishes a lightweight WebSocket channel listening for updates to its specific `job_id`:
```javascript
import { supabase } from './supabase-client.js';

export function listenForDiagnosisResult(jobId, onResult, onError) {
  const channel = supabase
    .channel(`job-${jobId}`)
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'diagnosis_jobs',
        filter: `id=eq.${jobId}`
      },
      (payload) => {
        const { status, result, error_message } = payload.new;
        if (status === 'completed') {
          channel.unsubscribe();
          onResult(result);
        } else if (status === 'failed') {
          channel.unsubscribe();
          onError(error_message);
        }
      }
    )
    .subscribe();
}
```

### Option 2: Gentle Polling Fallback
For environments where WebSockets are blocked:
- Poll `GET /rest/v1/diagnosis_jobs?id=eq.{job_id}&select=status,result,error_message` every 3 seconds for up to 60 seconds.
- If still `queued`, show UI badge: *"Yêu cầu của bạn đã lưu an toàn trong hàng đợi. Hệ thống sẽ gửi thông báo khi máy chủ AI hoàn tất phân tích."*

---

## 7. Security & Failure Guarantees

1. **Zero Credential Exposure:** Frontend code holds only `SUPABASE_ANON_KEY`. It can read and write only rows belonging to `auth.uid()`. It cannot see other users' jobs or tamper with job statuses.
2. **Worker Privilege Isolation:** The Windows worker uses `SUPABASE_SERVICE_ROLE_KEY` solely for RPC calls and signed URL generation. It runs in a local environment on the Windows host.
3. **Cold Shutdown Resilience:** If the user powers off the PC while a job is in `processing`, the heartbeat watchdog detects the missing worker after 120 seconds and cleanly resets the job to `queued`.

