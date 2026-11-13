# GARI AgriTech AI Platform — Sprint 1.7.1: Pre-Push CI Security Review Report

**Document ID:** GARI-REVIEW-SPRINT1-7-1-2026-01  
**Project:** GARI AgriTech AI Platform  
**Target:** Sprint 1.7 Pre-Push Artifacts Security & Validity Audit  
**Date:** 2026-11-13  
**Status:** BLOCKED — FIXES REQUIRED  
**Final Verdict:** `BLOCKED — FIXES REQUIRED`  

---

## 1. Executive Summary

In accordance with Sprint 1.7.1, an exhaustive security, validity, and compliance review of all newly authored Sprint 1.7 artifacts was conducted prior to any commit, push, or workflow execution.

Reviewed files:
1. [`.github/workflows/postgres-validation.yml`](file:///d:/leaf-diseases-detector-main/.github/workflows/postgres-validation.yml)
2. [`supabase/tests/00_bootstrap_test_roles.sql`](file:///d:/leaf-diseases-detector-main/supabase/tests/00_bootstrap_test_roles.sql)
3. [`supabase/tests/99_rollback_and_cleanup.sql`](file:///d:/leaf-diseases-detector-main/supabase/tests/99_rollback_and_cleanup.sql)
4. [`tests/test_postgres_live_validation.py`](file:///d:/leaf-diseases-detector-main/tests/test_postgres_live_validation.py)
5. [`docs/GARI_SUPABASE_SPRINT1_7_REPORT.md`](file:///d:/leaf-diseases-detector-main/docs/GARI_SUPABASE_SPRINT1_7_REPORT.md)

**Review Conclusion:**  
While the architectural design is sound, zero PHP was used, zero SQLite mutations occurred, and the host was kept untouched, **3 actionable security/correctness findings (1 Critical, 2 High)** were identified that must be remediated before committing or pushing to GitHub:
1. **Critical:** In CI environments, missing PostgreSQL or missing drivers would result in tests silently skipping rather than failing the build.
2. **High:** Caught `RuntimeError` in safety guards masks illegal database targets into test skips.
3. **High:** GitHub Actions workflow lacks explicit minimal `GITHUB_TOKEN` permissions.

Per instructions, **no files have been silently edited**. All suggested fixes are detailed below with complete diffs awaiting user approval.

---

## 2. Review Section 1: GitHub Actions Security

| Audit Item | Current State | Status / Finding | Severity |
| :--- | :--- | :--- | :--- |
| **Action Pinning** | Uses `@v4` and `@v5` version tags | Release tags are mutable; should pin to 40-char commit SHAs | **MEDIUM** (SEC-05) |
| **GITHUB_TOKEN Permissions** | Omitted | Uses default repository permissions; should declare `permissions: contents: read` | **HIGH** (SEC-03) |
| **pull_request Behavior** | Triggers on `pull_request` targeting `main`/`master` | Executes in fork context without write tokens or repo secrets | **VERIFIED SAFE** |
| **Untrusted Input Injection** | Input `test_profile` declared in `workflow_dispatch` | Never referenced inside any `run:` block; command injection impossible | **VERIFIED SAFE** |
| **Production Secrets Exposure** | Zero `secrets.` referenced; Step 3 scans environment | Zero secrets accessible; pre-flight guard blocks `supabase.co` | **VERIFIED SAFE** |
| **PostgreSQL Port Binding** | `5432:5432` on `ubuntu-latest` runner | Bound to runner loopback only; not exposed publicly | **VERIFIED SAFE** |

---

## 3. Review Section 2: PostgreSQL Test Validity

| Audit Item | Current State | Status / Finding | Severity |
| :--- | :--- | :--- | :--- |
| **Sequential Migration** | `test_02` sorts `*.sql` and executes 00 to 04 | Verified: chronologically applies all 5 migrations in order | **VERIFIED SAFE** |
| **Silent Skip in CI** | `setUpClass` skips if socket is closed or driver missing | **Vulnerability:** If container fails in CI, tests skip and CI reports green! | **CRITICAL** (SEC-01) |
| **Fail-Closed in CI** | Does not check `CI` or `GITHUB_ACTIONS` env vars | Must abort CI with failure if PostgreSQL is unavailable | **CRITICAL** (SEC-01) |
| **Result Separation** | Local skips clearly marked with notice | Local skip reason is clear, but must not apply in CI | **HIGH** (SEC-01) |

---

## 4. Review Section 3: Supabase Compatibility

| Audit Item | Current State | Status / Finding | Severity |
| :--- | :--- | :--- | :--- |
| **Auth Function Emulation** | `auth.uid()`, `auth.role()`, `auth.jwt()` | Reads `request.jwt.claims` JSONB session GUC; returns NULL when unauthenticated | **VERIFIED SAFE** |
| **JWT Claim Context** | `set_config('request.jwt.claims', ..., false)` | Properly simulates GoTrue JWT payload and claims parsing | **VERIFIED SAFE** |
| **Role Privileges** | `anon`, `authenticated`, `service_role` | `anon` receives 0 rows; `authenticated` restricted by RLS & column grants | **VERIFIED SAFE** |
| **BYPASSRLS Attribute** | `service_role` created without `BYPASSRLS` | Uses RLS policy `USING (true)`. In real Supabase, `service_role` has `BYPASSRLS` | **MEDIUM** (SEC-06) |
| **SECURITY DEFINER Audit** | Functions created by superuser with `search_path` | Verified: all 4 functions have `prosecdef = true` and explicit `search_path` | **VERIFIED SAFE** |
| **RPC Execute Permissions** | `provision_user_account_idempotent` in `public` | Has default `EXECUTE` to `PUBLIC`; should be revoked from `authenticated` in future | **MEDIUM** (SEC-04) |
| **Supabase Limitations** | Documented in Sprint 1.7 report | Lacks GoTrue bcrypt engine, Realtime, and PostgREST web server | **DOCUMENTED** |

---

## 5. Review Section 4: Cleanup & Teardown Safety

| Audit Item | Current State | Status / Finding | Severity |
| :--- | :--- | :--- | :--- |
| **Disposable Target Only** | Database name strictly `gari_disposable_test_db` | Confirmed: hardcoded disposable test database name | **VERIFIED SAFE** |
| **Safety Guards Enforcement** | `assert_safety_guards` checks host & dbname | **Flaw:** Caught exception sets `live_available = False`, skipping tests | **HIGH** (SEC-02) |
| **Rollback Order** | `99_rollback_and_cleanup.sql` reverse dependency | Policies -> Triggers -> Tables (Cascade) -> Functions | **VERIFIED SAFE** |
| **Unrelated DB Protection** | `DROP DATABASE IF EXISTS gari_disposable_test_db` | Drops only the disposable DB; `postgres` system DB untouched | **VERIFIED SAFE** |

---

## 6. Review Section 5: Migration Correctness

| Audit Item | Current State | Status / Finding | Severity |
| :--- | :--- | :--- | :--- |
| **Rerun Idempotency** | Tested in `test_03_migration_rerun_idempotency` | All DDL uses `IF NOT EXISTS`, `CREATE OR REPLACE`, `DROP ... IF EXISTS` | **VERIFIED SAFE** |
| **Profile Preservation** | `COALESCE(NULLIF(EXCLUDED.phone, ''), phone)` | Verified in `test_05`: blank signup metadata does not wipe phone | **VERIFIED SAFE** |
| **Trigger Idempotency** | `handle_new_user_signup` uses `ON CONFLICT` | Verified in `test_04` & `test_05` | **VERIFIED SAFE** |
| **RLS & Column Grants** | Column-level `GRANT UPDATE (...)` + guard trigger | Verified: non-privileged users cannot escalate to admin | **VERIFIED SAFE** |

---

## 7. Detailed Findings & Proposed Remediation

### [CRITICAL] SEC-01: Silent Skip When PostgreSQL Is Unavailable in CI
- **File:** [`tests/test_postgres_live_validation.py`](file:///d:/leaf-diseases-detector-main/tests/test_postgres_live_validation.py#L74-L107)
- **Line Reference:** Lines 74–107.
- **Problem:** If the `postgres:15-alpine` container fails to start, or if `psycopg2` fails to install, `setUpClass` catches the condition and marks tests as skipped. In CI, this means the job exits with code 0 (`OK (skipped=17)`), generating a false positive pass.
- **Proposed Fix:** Check `is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"`. If `is_ci` is true, immediately raise `RuntimeError` to hard-fail the CI build:
  ```python
  is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
  if not PSYCOPG2_AVAILABLE:
      if is_ci:
          raise RuntimeError("CI FATAL: psycopg2 is required in CI but not installed!")
      cls.live_available = False
      cls.skip_reason = "psycopg2 is not installed on this host..."
      return

  if not is_socket_open(cls.conn_params["host"], cls.conn_params["port"], timeout=1.5):
      if is_ci:
          raise RuntimeError(f"CI FATAL: PostgreSQL socket {cls.conn_params['host']}:{cls.conn_params['port']} unreachable!")
      cls.live_available = False
      cls.skip_reason = f"PostgreSQL socket {cls.conn_params['host']}:{cls.conn_params['port']} not reachable..."
      return
  ```

---

### [HIGH] SEC-02: Safety Guard Exception Masking
- **File:** [`tests/test_postgres_live_validation.py`](file:///d:/leaf-diseases-detector-main/tests/test_postgres_live_validation.py#L83-L88)
- **Line Reference:** Lines 83–88.
- **Problem:**
  ```python
  try:
      assert_safety_guards(cls.conn_params)
  except RuntimeError as e:
      cls.live_available = False
      cls.skip_reason = str(e)
      return
  ```
  If connection parameters point to `supabase.co` or a production DB name, `assert_safety_guards` raises `RuntimeError`, but `setUpClass` catches it and skips tests instead of failing.
- **Proposed Fix:** Do not catch `RuntimeError` from `assert_safety_guards`. Let it propagate immediately to terminate the test runner:
  ```python
  # Safety guards must always fail closed
  assert_safety_guards(cls.conn_params)
  ```

---

### [HIGH] SEC-03: Missing Minimal `GITHUB_TOKEN` Permissions
- **File:** [`.github/workflows/postgres-validation.yml`](file:///d:/leaf-diseases-detector-main/.github/workflows/postgres-validation.yml#L29-L37)
- **Line Reference:** Lines 29–37.
- **Problem:** The workflow does not set explicit `permissions:`. By default, workflows without permissions inherit default repository settings (which may include broad write access).
- **Proposed Fix:** Add top-level least-privilege permission block:
  ```yaml
  permissions:
    contents: read
  ```

---

### [MEDIUM] SEC-05: Unpinned GitHub Actions Version Tags
- **File:** [`.github/workflows/postgres-validation.yml`](file:///d:/leaf-diseases-detector-main/.github/workflows/postgres-validation.yml#L56-L62)
- **Line Reference:** Lines 56 and 59.
- **Problem:** `actions/checkout@v4` and `actions/setup-python@v5` use floating tags vulnerable to upstream tag alteration.
- **Proposed Fix:** Pin to verified commit SHAs:
  ```yaml
  - name: 1. Checkout Repository
    uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

  - name: 2. Setup Python Runtime (3.11)
    uses: actions/setup-python@0b93645e9fb717ef0f17e8f819dd8826487ab549 # v5.3.0
  ```

---

### [MEDIUM] SEC-06: Explicit `BYPASSRLS` for `service_role` in Test Harness
- **File:** [`supabase/tests/00_bootstrap_test_roles.sql`](file:///d:/leaf-diseases-detector-main/supabase/tests/00_bootstrap_test_roles.sql#L19-L21)
- **Line Reference:** Lines 19–21.
- **Problem:** In real Supabase, `service_role` possesses the `BYPASSRLS` attribute. While policy coverage permits access, explicitly adding `ALTER ROLE service_role BYPASSRLS;` ensures 100% parity with Supabase's role definition.
- **Proposed Fix:**
  ```sql
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
      CREATE ROLE service_role NOLOGIN BYPASSRLS;
  ELSE
      ALTER ROLE service_role BYPASSRLS;
  END IF;
  ```

---

## 8. Proposed Patches Ready for User Approval

### Patch 1: `.github/workflows/postgres-validation.yml`
```diff
--- a/.github/workflows/postgres-validation.yml
+++ b/.github/workflows/postgres-validation.yml
@@ -28,6 +28,9 @@ on:
 concurrency:
   group: ${{ github.workflow }}-${{ github.ref }}
   cancel-in-progress: true
+
+permissions:
+  contents: read
 
 jobs:
   validate-postgresql-15:
@@ -53,10 +56,10 @@ jobs:
 
     steps:
       - name: 1. Checkout Repository
-        uses: actions/checkout@v4
+        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
 
       - name: 2. Setup Python Runtime (3.11)
-        uses: actions/setup-python@v5
+        uses: actions/setup-python@0b93645e9fb717ef0f17e8f819dd8826487ab549 # v5.3.0
         with:
           python-version: '3.11'
           cache: 'pip'
```

### Patch 2: `tests/test_postgres_live_validation.py`
```diff
--- a/tests/test_postgres_live_validation.py
+++ b/tests/test_postgres_live_validation.py
@@ -74,25 +74,27 @@ class TestPostgresLiveValidation(unittest.TestCase):
     @classmethod
     def setUpClass(cls):
+        is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
+
         if not PSYCOPG2_AVAILABLE:
+            if is_ci:
+                raise RuntimeError("CI FATAL: psycopg2-binary is required in CI but not installed!")
             cls.live_available = False
             cls.skip_reason = (
                 "psycopg2 is not installed on this host. "
                 "This suite executes against the ephemeral PostgreSQL 15 service container in GitHub Actions CI."
             )
             return
 
         cls.conn_params = get_pg_connection_params()
         
-        # Verify safety guards before any socket activity
-        try:
-            assert_safety_guards(cls.conn_params)
-        except RuntimeError as e:
-            cls.live_available = False
-            cls.skip_reason = str(e)
-            return
+        # Verify safety guards before any socket activity (fail-closed, never masked)
+        assert_safety_guards(cls.conn_params)
 
         # Check if database is reachable
         if not is_socket_open(cls.conn_params["host"], cls.conn_params["port"], timeout=1.5):
+            if is_ci:
+                raise RuntimeError(
+                    f"CI FATAL: PostgreSQL socket {cls.conn_params['host']}:{cls.conn_params['port']} not reachable in CI!"
+                )
             cls.live_available = False
             cls.skip_reason = (
                 f"PostgreSQL socket {cls.conn_params['host']}:{cls.conn_params['port']} not reachable. "
```

### Patch 3: `supabase/tests/00_bootstrap_test_roles.sql`
```diff
--- a/supabase/tests/00_bootstrap_test_roles.sql
+++ b/supabase/tests/00_bootstrap_test_roles.sql
@@ -19,7 +19,9 @@ BEGIN
     IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
         CREATE ROLE authenticated NOLOGIN;
     END IF;
     IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN
-        CREATE ROLE service_role NOLOGIN;
+        CREATE ROLE service_role NOLOGIN BYPASSRLS;
+    ELSE
+        ALTER ROLE service_role BYPASSRLS;
     END IF;
     IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'supabase_admin') THEN
         CREATE ROLE supabase_admin NOLOGIN;
```

---

## 9. Final Verdict

```
================================================================================
FINAL VERDICT: BLOCKED — FIXES REQUIRED
================================================================================
```
The workflow and test artifacts must apply the 3 high/critical safety fixes (Fail-closed in CI, unmasked safety guards, and minimal `GITHUB_TOKEN` permissions) before pushing to GitHub.

Awaiting explicit user approval to apply these recommended patches.
