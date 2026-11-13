# GARI — Hybrid Cloud Backend Implementation
**Document:** `docs/GARI_HYBRID_BACKEND_IMPLEMENTATION.md`  
**Date:** November 13, 2026  
**Status:** IMPLEMENTED LOCALLY — READY FOR POSTGRESQL VALIDATION  
**Priority:** ARCHITECTURE TRANSITION

---

## 1. Architectural Transition: Monolith to Hybrid Cloud

Historically, the GARI AgriTech platform required the developer's Windows PC to remain powered on and connected via an inbound Cloudflare Tunnel for all user interactions — including authentication, user profile management, farm and plot CRUD, calendar task management, and diagnosis history inspection. When the Windows PC was asleep or the tunnel expired, the entire application became non-responsive.

The **GARI Hybrid Cloud Architecture** decouples the platform into two distinct operational planes:

```
+-----------------------------------------------------------------------------------+
|                            CLOUD SAAS PLANE (Supabase)                            |
|                                                                                   |
|  [ Auth.Users ]      [ Profiles ]       [ Farms & Plots ]    [ Cultivation Tasks] |
|  [ Crop Library]     [ Disease Lib ]    [ Diagnoses Hist]    [ Notifications ]    |
|                                                                                   |
|                ===========================================                        |
|                [ diagnosis_jobs ] Durable AI Worker Queue                         |
|                ===========================================                        |
+-----------------------------------------------------------------------------------+
                                         ^
                                         | Outbound HTTPS Polling (No Inbound Tunnel)
                                         | claim_next_diagnosis_job (SKIP LOCKED)
                                         v
+-----------------------------------------------------------------------------------+
|                         LOCAL AI WORKER PLANE (Windows PC)                        |
|                                                                                   |
|  [ worker/gari_ai_worker.py ]                                                    |
|       -> PyTorch / ConvNeXt / ViT / Swin / Timm Inference Engine                  |
|       -> Heartbeat Ping (update_diagnosis_job_heartbeat)                          |
|       -> Result Submission (complete_diagnosis_job / fail_diagnosis_job)          |
+-----------------------------------------------------------------------------------+
```

### Operational Invariants:
1. **Windows PC Independence:** Core SaaS capabilities (login, registration, farm records, crop references, notifications, and historical reports) function 24/7 in the cloud without requiring the developer PC to be active.
2. **Zero Inbound Attack Surface:** The local PC requires no open ports, no static IP, no port forwarding, and no third-party inbound tunnels. It initiates outbound HTTPS requests only.
3. **Durable Queuing:** In the event of a worker outage, AI diagnosis requests are durably queued in PostgreSQL rather than dropped. Once the worker resumes, pending requests are processed automatically.

---

## 2. Database Schema: Migration 5

The database schema is declared in `supabase/migrations/20261111120005_create_hybrid_cloud_and_ai_worker_queue.sql` and includes the following primary entities:

### 2.1. Farm & Plot Hierarchy
- `public.farms`: Top-level agricultural property owned by a user (`id`, `user_id`, `name`, `location`, `total_area_sqm`, `created_at`, `updated_at`).
- `public.farm_plots`: Cultivation zones within a farm (`id`, `farm_id`, `user_id`, `name`, `crop_type`, `area_sqm`, `soil_type`, `created_at`, `updated_at`).

### 2.2. Agronomic & Knowledge Reference
- `public.crops`: Normalized catalog of crops (`id`, `crop_code`, `name_vi`, `scientific_name`, `family`, `description`, `metadata`).
- `public.diseases`: Normalized catalog of crop diseases (`id`, `crop_id`, `disease_code`, `name_vi`, `symptoms_vi`, `treatment_vi`, `severity_level`).

### 2.3. Agronomic Lifecycle & Activity
- `public.cultivation_tasks`: Task scheduling for farming calendars (`id`, `user_id`, `farm_id`, `plot_id`, `title`, `description`, `due_date`, `status`, `priority`).
- `public.diagnoses`: Historical record of completed plant health diagnoses (`id`, `user_id`, `farm_id`, `plot_id`, `crop_type`, `disease_name`, `confidence`, `image_url`, `treatment_summary`, `diagnosis_metadata`).
- `public.notifications`: User notifications for completed diagnoses, weather warnings, and task reminders (`id`, `user_id`, `title`, `body`, `is_read`, `type`, `metadata`).

### 2.4. Durable AI Worker Queue
- `public.diagnosis_jobs`:
  - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
  - `user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE`
  - `farm_id UUID REFERENCES public.farms(id) ON DELETE SET NULL`
  - `plot_id UUID REFERENCES public.farm_plots(id) ON DELETE SET NULL`
  - `crop_type TEXT NOT NULL DEFAULT 'auto'`
  - `storage_path TEXT NOT NULL`
  - `status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed'))`
  - `retry_count INTEGER NOT NULL DEFAULT 0`
  - `worker_id TEXT`
  - `heartbeat_at TIMESTAMPTZ`
  - `started_at TIMESTAMPTZ`
  - `completed_at TIMESTAMPTZ`
  - `result JSONB`
  - `error_message TEXT`

---

## 3. Security Model: Row Level Security (RLS)

All 8 tables have RLS explicitly enabled (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY;`).

1. **Strict User Tenant Isolation:**
   - Authenticated users can only `SELECT`, `INSERT`, `UPDATE`, and `DELETE` records matching their verified JWT identity (`auth.uid() = user_id`).
   - Cross-user data access is blocked at the database engine level.
2. **Public Knowledge Reference:**
   - `crops` and `diseases` tables permit read-only access to `anon` and `authenticated` roles (`SELECT TO anon, authenticated USING (true)`), while mutations are restricted to the `service_role`.
3. **Service Role Authorization:**
   - Administrative and background worker operations utilize the dedicated `service_role` role with explicit `USING (true) WITH CHECK (true)` policies.
4. **Queue RLS:**
   - End-users can insert jobs and view their own jobs. Only `service_role` can claim, update status, and complete jobs.

---

## 4. Stored Procedures: Atomic Queue Protocol

Concurrency and job locking are managed via atomic PostgreSQL stored procedures defined with `SECURITY DEFINER` and sanitized `search_path`:

1. `claim_next_diagnosis_job(p_worker_id TEXT, p_lock_duration_seconds INTEGER DEFAULT 120)`:
   - Uses `SELECT ... FROM public.diagnosis_jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED`
   - Atomically transitions status to `'processing'`, sets `worker_id`, `started_at`, and `heartbeat_at`.
   - Prevents race conditions and duplicate claims across multiple concurrent workers.
2. `update_diagnosis_job_heartbeat(p_job_id UUID, p_worker_id TEXT)`:
   - Extends the lease of an actively running job by updating `heartbeat_at = NOW()`.
3. `complete_diagnosis_job(p_job_id UUID, p_worker_id TEXT, p_result JSONB)`:
   - Transitions status to `'completed'`, stores result JSONB, inserts into `public.diagnoses`, and emits an automated user notification in `public.notifications`.
4. `fail_diagnosis_job(p_job_id UUID, p_worker_id TEXT, p_error TEXT)`:
   - Records error details and marks the job as `'failed'`.
5. `recover_stale_diagnosis_jobs(p_stale_seconds INTEGER DEFAULT 120)`:
   - Identifies jobs stuck in `'processing'` whose heartbeat has timed out. Increments `retry_count`. If `retry_count < 3`, returns them to `'queued'`; otherwise marks them `'failed'`.

---

## 5. Continuous Integration & Ephemeral PostgreSQL Validation

To prevent regression and guarantee PostgreSQL 15 compatibility:
- **Workflow File:** `.github/workflows/postgres-validation.yml`
- **Service Container:** Dedicated ephemeral `postgres:15-alpine` container running inside GitHub Actions.
- **Security Hardening:**
  - Strict read-only workflow permissions (`permissions: contents: read`).
  - Pinned actions (`actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`, `actions/setup-python@0a5c61591373683505ea898e09a60046235733b1`).
  - Ephemeral test credentials (`POSTGRES_DB: gari_test_db`, isolated port binding).
- **Execution Test Suite:** `tests/test_postgres_live_validation.py` sequentially executes all 5 migrations, runs end-to-end RLS and stored procedure test suites, and runs `99_rollback_and_cleanup.sql`.
