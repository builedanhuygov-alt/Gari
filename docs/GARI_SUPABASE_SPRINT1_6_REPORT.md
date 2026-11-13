# GARI AgriTech AI Platform — Sprint 1.6: Isolated PostgreSQL Runtime Validation Report

**Document ID:** GARI-REPORT-SPRINT1-6-2026-01  
**Project:** GARI AgriTech AI Platform  
**Target:** Supabase PostgreSQL Schema Migrations (Isolated Runtime Validation)  
**Date:** 2026-11-11  
**Status:** BLOCKED — REAL POSTGRESQL ENGINE NOT PRESENT ON HOST  
**Final Verdict:** `BLOCKED — REAL POSTGRESQL EXECUTION NOT COMPLETED`  

---

## 1. Executive Summary

Sprint 1.6 evaluated options to execute and validate the five Supabase migration files against an **actual, live PostgreSQL database engine** in an isolated, disposable test environment.

In strict compliance with user instructions:
- **Zero Fabrication:** The 17 passing simulation checks from Sprint 1.5 are explicitly categorized as **Python relational simulations**, NOT as evidence of actual PostgreSQL execution.
- **Strict Safety Constraints:**
  - Zero PHP used.
  - Windows Defender was not disabled or modified.
  - Antigravity internal logs were not modified.
  - The local SQLite database (`database/disease_detector.db`) was not modified.
  - No connection was made to the real production GARI Supabase project.
  - No production or real user accounts were migrated.
  - No system-wide software (Docker, WSL, PostgreSQL) was installed without explicit user approval.

**Final Verdict:** `BLOCKED — REAL POSTGRESQL EXECUTION NOT COMPLETED`  
**Root Blocker:** No PostgreSQL daemon, Docker daemon, or disposable PostgreSQL connection string exists on this Windows host.

---

## 2. Task 1: Evaluation of Isolated PostgreSQL Testing Options

An exhaustive audit of potential execution runtime avenues was conducted on the host machine:

| Option | Method | Host Discovery & Feasibility Status | Blocker / Safety Constraint |
| :--- | :--- | :--- | :--- |
| **Option 1: Local Docker Container** | `docker run --rm -p 5432:5432 postgres:15-alpine` | **UNAVAILABLE.** Docker CLI (`docker.exe`) and Docker Desktop daemon are not installed. | Constraint: "Do not install Docker, WSL, or PostgreSQL system-wide without approval." |
| **Option 2: Windows Subsystem for Linux (WSL)** | `wsl -e postgres` or Linux package execution | **UNAVAILABLE.** `wsl --list` reports: *"Windows Subsystem for Linux has no installed distributions."* | Constraint: "Do not install Docker, WSL, or PostgreSQL system-wide without approval." |
| **Option 3: Local Windows PostgreSQL Service** | Service connection to `127.0.0.1:5432` | **UNAVAILABLE.** No Windows PostgreSQL service exists. `Test-NetConnection 127.0.0.1 -Port 5432` failed. | Constraint: "Do not install Docker, WSL, or PostgreSQL system-wide without approval." |
| **Option 4: Supabase Local CLI Runtime** | `supabase start` | **UNAVAILABLE.** Supabase CLI requires a functional Docker engine to spawn container pods (`supabase/postgres`, `supabase/gotrue`). | Dependent on Option 1 (Docker absent). |
| **Option 5: Disposable Managed Cloud Instance** | Ephemeral DB via Neon, Aiven, or CockroachDB | **UNAVAILABLE WITHOUT USER-PROVIDED CONNECTION URL.** No ephemeral test connection string (`TEST_DATABASE_URL`) is configured in `.env.local`. | Constraint: "Do not connect to the real GARI Supabase project. Do not expose credentials." |
| **Option 6: Python In-Memory Relational Engine** | `sqlite3` relational simulation | **FUNCTIONAL BUT SIMULATION ONLY.** Cannot execute PL/pgSQL, `SET request.jwt.claims`, or PostgreSQL RLS kernel (`pg_policy`). | Constraint: "Never report simulated tests as PostgreSQL integration tests." |

---

## 3. Strict Results Separation (Task 4 & 5)

In compliance with Task 4 and Task 5, test results are rigorously separated into three distinct tiers:

### Tier A: Actual PostgreSQL Runtime Execution Results
- **Engine Executed:** None.
- **Total Runtime Queries Executed:** 0.
- **Status:** **BLOCKED (0/5 migrations executed against a live PostgreSQL socket).**
- **Exact Blocker:** Absence of an isolated local PostgreSQL process listening on `127.0.0.1:5432` or an authorized disposable cloud connection string.

---

### Tier B: Static SQL Inspection & Formal Verification Results
*All five migration files in [`supabase/migrations/`](file:///d:/leaf-diseases-detector-main/supabase/migrations/) were statically audited against PostgreSQL 15 and Supabase specifications:*

```
====================================================================================================
                        STATIC SQL COMPATIBILITY & SECURITY AUDIT MATRIX
====================================================================================================
```

#### 1. SQL Syntax & Sequential Ordering
- **Ordering:** Chronological prefix sequence verified:
  - `20261111120000_create_base_schema_and_profiles.sql` (Base schema, extensions, profiles)
  - `20261111120001_create_user_preferences.sql` (User preferences)
  - `20261111120002_create_identity_bridge_and_provisioning.sql` (Identity bridge & state tracking)
  - `20261111120003_create_idempotent_provisioning_trigger.sql` (Sign-up triggers & RPC)
  - `20261111120004_create_rls_and_privilege_guards.sql` (RLS policies & privilege escalation guards)
- **Syntax:** Standard PostgreSQL 15 DDL. All extension declarations utilize `CREATE EXTENSION IF NOT EXISTS`. All trigger bindings utilize `DROP TRIGGER IF EXISTS` before creation.

#### 2. Table Constraints & Indexes
- **`public.profiles`:**
  - Primary Key: `id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE`.
  - Check Constraints: `account_type IN ('farmer', 'enterprise', 'expert', 'host_admin')`, `moderation_status IN ('clean', 'flagged', 'suspended', 'under_review')`.
  - Indexes: `idx_profiles_phone`, `idx_profiles_account_type`, `idx_profiles_is_admin`, `idx_profiles_moderation`.
- **`public.user_preferences`:**
  - Foreign Key: `user_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE`.
  - Check Constraints: `language IN ('vi', 'en')`, `theme IN ('light', 'dark', 'system')`.
- **`public.gari_identity_links`:**
  - Strict 1:1 Mapping: `supabase_uid UUID UNIQUE NOT NULL` and `sqlite_user_id INTEGER UNIQUE NOT NULL`.
  - Check Constraint: `status IN ('ACTIVE', 'SUSPENDED', 'PENDING_MIGRATION')`.
  - Indexes: `idx_identity_links_sub`, `idx_identity_links_sqlite`.
- **`public.account_provisioning`:**
  - Check Constraint: `status IN ('PENDING', 'ACTIVE', 'FAILED')`.
  - Partial Index: `idx_account_provisioning_status ON (status) WHERE status = 'PENDING'`.

#### 3. Idempotent Provisioning & User Data Preservation
- **Trigger Function:** `handle_new_user_signup()` on `auth.users` (`AFTER INSERT`).
- **Conflict Handling:**
  ```sql
  ON CONFLICT (id) DO UPDATE SET
      full_name = EXCLUDED.full_name,
      phone = COALESCE(NULLIF(EXCLUDED.phone, ''), public.profiles.phone),
      updated_at = NOW();
  ```
  - **Data Preservation Guarantee:** If a user has already customized their `phone` or `province`, an empty re-signup trigger metadata payload will **not overwrite** existing populated data (`COALESCE(NULLIF(...))`).

#### 4. Row Level Security & Access Isolation Policies
- **RLS Enabled:** Explicitly executed across all four foundation tables:
  `ALTER TABLE public.<table_name> ENABLE ROW LEVEL SECURITY;`.
- **Private Profile Policy:** `profiles_select_own` enforces `USING (auth.uid() = id)`. Anonymous users receive 0 rows; User A cannot read User B's profile.
- **Identity Bridge Immutability:** Authenticated users have `SELECT` only on `gari_identity_links` and `account_provisioning`. No `INSERT`, `UPDATE`, or `DELETE` policies exist for `authenticated`.

#### 5. Privilege Escalation & Boundary Hardening
- **Guard Trigger:** `protect_profile_privileged_fields()` executes `BEFORE UPDATE ON public.profiles`.
  - Evaluates `account_type`, `is_admin`, `is_host_admin`, `is_expert`, `is_active`, `moderation_status`, and `feature_restrictions`.
  - If any of these fields differ from `OLD` and caller is not `service_role`: Raises PostgreSQL exception `42501` (`CANNOT_MODIFY_PRIVILEGED_FIELDS`).
- **Cryptographic Trust Boundary:** Validates role solely via trusted engine calls (`auth.role()`, `auth.jwt() ->> 'role'`, `current_user = 'service_role'`). Zero trust is placed in unverified client-controlled header parameters (`request.jwt.claim.role`).
- **Search-Path Hijacking Protection:** All `SECURITY DEFINER` functions explicitly declare:
  ```sql
  SET search_path = public, auth, pg_temp;
  ```
- **Column-Level Least Privilege:**
  - `REVOKE UPDATE ON public.profiles FROM authenticated;`
  - `GRANT UPDATE (full_name, phone, province, address, avatar_url, bio) ON public.profiles TO authenticated;`
  - `REVOKE INSERT, UPDATE, DELETE ON public.gari_identity_links FROM authenticated;`
  - `REVOKE INSERT, UPDATE, DELETE ON public.account_provisioning FROM authenticated;`

---

### Tier C: Python Relational Simulation Tests
*Executed locally via `.venv\Scripts\python.exe tests\test_supabase_postgres_integration.py`:*

- **Total Test Cases:** 17 scenarios.
- **Execution Time:** 1.014 seconds.
- **Status:** **17/17 PASSED (100% Behavioral Simulation Compliance).**
- **Scope Verified via Simulation:**
  - `test_01_probe_postgres_daemon`: Correctly reported local daemon absence.
  - `test_02`–`test_04`: Syntax, cascade FKs, and index declarations verified.
  - `test_05`–`test_07`: Anonymous and User A vs User B isolation verified.
  - `test_08`–`test_09`: Privilege escalation to admin or modified moderation rejected.
  - `test_10`–`test_11`: Bridge write restrictions and service-role execution verified.
  - `test_12`–`test_15`: Single profile creation, duplicate idempotency, retry safety, and cascade purges verified.
  - `test_16`–`test_17`: `search_path` and untrusted claim rejections verified.

---

## 4. Options to Unblock Real PostgreSQL Runtime Execution

To transition from `BLOCKED` to `POSTGRESQL RUNTIME VALIDATION PASSED`, the user may select one of the following sanctioned paths:

### Path 1: User-Provided Ephemeral PostgreSQL Connection (Zero Host Modification)
1. User provides a temporary, disposable connection string to an isolated, empty PostgreSQL database (e.g., from Neon.tech, Supabase branch, or ElephantSQL):
   ```powershell
   $env:TEST_POSTGRES_URL = "postgres://user:password@ephemeral-host:5432/testdb?sslmode=require"
   ```
2. The test harness connects to this disposable database, applies all five migrations, executes live DDL/RLS/JWT context tests, and immediately tears down the test schema.
3. **Safety:** Zero software installed on Windows; zero modification to the real GARI database.

### Path 2: Local Docker Desktop Approval
1. User grants explicit permission to install Docker Desktop on the Windows machine.
2. The agent runs a disposable container:
   ```powershell
   docker run --name gari-pg-test -e POSTGRES_PASSWORD=test -p 5432:5432 -d postgres:15-alpine
   ```
3. The test harness executes live against `127.0.0.1:5432` and stops/destroys the container upon completion.

### Path 3: Continuous Integration (CI) Validation
1. Execute the migration test suite within a GitHub Actions workflow using a managed `services: postgres:15` service container.

---

## 5. Final Report Conclusion

In strict alignment with the instructions:
- **No live PostgreSQL execution was fabricated.**
- **The exact technical blocker has been established and reported.**
- **All static SQL inspection and Python relational tests are documented separately.**

**Final Verdict:** `BLOCKED — REAL POSTGRESQL EXECUTION NOT COMPLETED`

