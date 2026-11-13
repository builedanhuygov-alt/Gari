# GARI — Production Deployment Runbook & Checklist
**Document:** `docs/GARI_PRODUCTION_DEPLOYMENT_CHECKLIST.md`  
**Date:** November 13, 2026  
**Status:** DRAFTED — AWAITING EXPLICIT USER APPROVAL BEFORE EXECUTION  
**Priority:** PRODUCTION READINESS & DISASTER RECOVERY

---

## 1. Safety Gate & Approval Requirement

> [!IMPORTANT]
> **STRICT REQUISITE:** Do not execute any item in this checklist until explicit, written confirmation is given by the project owner. No changes to production environment variables, production databases, or the production Vercel branch (`main`) may occur without authorization.

---

## 2. Phase 1 — Pre-Flight Verification

Before requesting deployment approval, ensure all local verification checks pass:

- [x] **Zero PHP Audit:** Confirm 0 PHP files in repository.
- [x] **Gateway Unit Tests:** Run `node tests/test_gateway_login_repair.js` (11/11 PASSED).
- [x] **AI Worker Unit Tests:** Run `python -m unittest tests/test_hybrid_ai_worker.py` (12/12 PASSED).
- [x] **Local Data Safety:** Verify `database/disease_detector.db` checksum is unmodified.
- [x] **Host Safety:** Verify Windows Defender and Antigravity system logs are untouched.
- [ ] **Preview Verification:** Deploy to Vercel Preview and confirm interactive login behavior.

---

## 3. Phase 2 — Cloud Infrastructure & Database Provisioning

Execute against the designated Supabase Production project:

1. **Sequential Migration Execution:**
   - [ ] Migration 1: `20261111120001_create_user_profiles_and_roles.sql`
   - [ ] Migration 2: `20261111120002_create_auth_triggers_and_sync.sql`
   - [ ] Migration 3: `20261111120003_add_profile_columns_and_rls.sql`
   - [ ] Migration 4: `20261111120004_fix_profile_triggers_and_grants.sql`
   - [ ] Migration 5: `20261111120005_create_hybrid_cloud_and_ai_worker_queue.sql`
2. **Schema & Stored Procedure Verification:**
   - [ ] Confirm RLS is enabled on all 8 application tables (`farms`, `farm_plots`, `cultivation_tasks`, `crops`, `diseases`, `diagnoses`, `notifications`, `diagnosis_jobs`).
   - [ ] Verify stored procedures:
     - `claim_next_diagnosis_job`
     - `update_diagnosis_job_heartbeat`
     - `complete_diagnosis_job`
     - `fail_diagnosis_job`
     - `recover_stale_diagnosis_jobs`

---

## 4. Phase 3 — Account Migration (3,611 Accounts)

- [ ] **Cold Backup:** Create a read-only copy of `database/disease_detector.db` before migration:
  `Copy-Item database/disease_detector.db database/disease_detector_backup_pre_migration.db`
- [ ] **Native Bcrypt Import (3,550 accounts):**
  Batch insert into `auth.users` with `encrypted_password` preserving existing hashes. Populate `public.profiles`.
- [ ] **Non-Standard Accounts (61 accounts):**
  Flag for password reset email or magic link upon first login.
- [ ] **Verification:** Test login with 1 sample account in each category (`farmer`, `enterprise`, `expert`, `host_admin`).

---

## 5. Phase 4 — Vercel Environment Configuration

Configure the following environment variables in the Vercel Dashboard for Production:

| Variable Name | Environment | Sensitivity | Description |
|---|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Production | Public | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Production | Public | Supabase anon/publishable key |
| `SUPABASE_SERVICE_ROLE_KEY` | Production | Secret | Supabase backend service role key |
| `VERCEL_BACKEND_API_URL` | Production | Secret | Backend API URL (optional in full hybrid mode) |

---

## 6. Phase 5 — Production Deployment Promotion

1. **Deploy to Production:**
   ```bash
   vercel --prod
   ```
2. **Post-Deployment Sanity Checks:**
   - [ ] Navigate to `https://gari-team.vercel.app/frontend2/predict`.
   - [ ] Attempt login with incorrect credentials -> Verify uniform 401 error message within 2 seconds.
   - [ ] Attempt login with valid account -> Verify seamless authentication and redirection.
   - [ ] Disconnect backend -> Verify 503 Service Unavailable is rendered cleanly without UI hang.
   - [ ] Verify button resets to clickable state in all failure conditions.

---

## 7. Phase 6 — AI Inference Worker Activation

On the local Windows PC (with PyTorch / GPU environment):
1. **Configure Environment:**
   ```powershell
   $env:SUPABASE_URL = "https://<production-project>.supabase.co"
   $env:SUPABASE_SERVICE_ROLE_KEY = "<production-service-role-key>"
   $env:GARI_POLL_INTERVAL = "2.0"
   ```
2. **Start Background Worker:**
   ```powershell
   .venv\Scripts\python worker\gari_ai_worker.py
   ```
3. **Monitor Queue:**
   - [ ] Submit a test leaf image from `https://gari-team.vercel.app/frontend2/predict`.
   - [ ] Observe worker log: `[JOB_START] -> [INFERENCE] -> [JOB_SUCCESS]`.
   - [ ] Verify result displays on frontend and persists in `public.diagnoses`.

---

## 8. Rollback & Disaster Recovery Plan

If unexpected failures occur during production rollout:
1. **Vercel Instant Rollback:**
   In Vercel Dashboard, promote previous stable deployment with 1 click (instant, 0s delay).
2. **Database Rollback:**
   Execute `supabase/tests/99_rollback_and_cleanup.sql` to revert Migration 5 tables and stored procedures without affecting core auth tables.
3. **SQLite Preserved:**
   `database/disease_detector.db` remains 100% intact throughout the entire procedure.
