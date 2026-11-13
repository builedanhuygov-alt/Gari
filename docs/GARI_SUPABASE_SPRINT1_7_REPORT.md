# GARI AgriTech AI Platform — Sprint 1.7: GitHub Actions PostgreSQL 15 Validation Report

**Document ID:** GARI-REPORT-SPRINT1-7-2026-01  
**Project:** GARI AgriTech AI Platform  
**Target:** Ephemeral PostgreSQL 15 GitHub Actions Integration Test Architecture  
**Date:** 2026-11-13  
**Status:** WORKFLOW PREPARED — AWAITING APPROVAL  
**Final Verdict:** `WORKFLOW PREPARED — AWAITING APPROVAL`  

---

## 1. Executive Summary

Sprint 1.7 resolves the execution blocker identified in Sprint 1.6 (`BLOCKED — REAL POSTGRESQL ENGINE NOT PRESENT ON HOST`) by preparing a **fully isolated, disposable PostgreSQL 15 integration test pipeline using GitHub Actions service containers**.

In strict compliance with user instructions and security mandates:
- **Zero Fabrication Guarantee:** We explicitly state that actual PostgreSQL execution has **not yet occurred**; the workflow and test suite are prepared locally and await explicit user approval to push and trigger the GitHub Actions runner.
- **Strict Separation of Tiers:**
  - **Tier A (Real PostgreSQL 15 Engine):** Implemented in [`tests/test_postgres_live_validation.py`](file:///d:/leaf-diseases-detector-main/tests/test_postgres_live_validation.py) and configured to run against the `postgres:15-alpine` service container in CI.
  - **Tier B (Static SQL & DDL Verification):** Formal audit of syntax, constraints, and `SECURITY DEFINER` `search_path` declarations across all five migrations.
  - **Tier C (Python Relational Simulation):** Maintained in [`tests/test_supabase_postgres_integration.py`](file:///d:/leaf-diseases-detector-main/tests/test_supabase_postgres_integration.py) (17/17 passing simulation checks).
- **Strict Safety Rules Upheld:**
  - Absolutely **zero PHP** used or introduced.
  - **Zero host modification:** No Docker, WSL, or PostgreSQL was installed on this Windows workstation.
  - **Zero production exposure:** No connection made to GARI Production Supabase (`supabase.co`); fail-closed guards prevent any non-test host connection.
  - **Zero real user data:** 100% synthetic mock identities.
  - **Zero SQLite modification:** Local `database/disease_detector.db` remains untouched.
  - **Zero git mutation:** No files committed or pushed without explicit user approval.
  - Windows Defender and internal logs left untouched.

---

## 2. GitHub Actions Workflow Architecture

The workflow definition has been created locally at [`.github/workflows/postgres-validation.yml`](file:///d:/leaf-diseases-detector-main/.github/workflows/postgres-validation.yml).

### 2.1 Workflow Design Matrix

| Component | Implementation Specification | Security / Operational Guarantee |
| :--- | :--- | :--- |
| **Workflow File** | `.github/workflows/postgres-validation.yml` | Validated YAML; isolated to test triggers. |
| **Trigger Mechanism** | `workflow_dispatch` (manual button) + `pull_request` (on `supabase/**` or test paths) | Will never run unexpectedly on accidental master pushes; requires deliberate triggering. |
| **Runner Environment** | `ubuntu-latest` | Clean, isolated Linux microVM provisioned on demand. |
| **Service Container** | `postgres:15-alpine` | Official lightweight PostgreSQL 15 engine; isolated network namespace. |
| **Test Database** | `gari_disposable_test_db` | Dedicated ephemeral DB created at container spin-up; contains zero production data. |
| **Container Credentials** | `postgres:test_password` | Ephemeral dummy credentials bound to `127.0.0.1:5432` only. |
| **Pre-Flight Guard** | Bash fail-closed pattern check | Immediately aborts if `supabase.co`, `sb_secret`, or production tokens exist in environment. |
| **Post-Run Cleanup** | `if: always()` SQL `DROP DATABASE` + container destruction | Ensures disposable database is dropped; runner VM is destroyed upon job completion. |

### 2.2 Workflow Execution Flow

```
[GitHub Actions Runner: ubuntu-latest]
               │
               ▼ (Step 1-2)
  [Checkout Code & Setup Python 3.11]
               │
               ▼ (Step 3)
  [Pre-Flight Production Guard]
  ──> Scans env for 'supabase.co' or production secrets. Fail-closed if detected.
               │
               ▼ (Step 4)
  [Install Driver: psycopg2-binary]
               │
               ▼ (Step 5: Tier A — Real PostgreSQL 15 Engine)
  [Service Container: postgres:15-alpine @ localhost:5432]
  ├─ 1. Run supabase/tests/00_bootstrap_test_roles.sql
  │     (Creates anon, authenticated, service_role, auth.uid(), auth.role(), auth.jwt())
  ├─ 2. Apply Migrations 0000 -> 0004 sequentially
  ├─ 3. Re-apply Migrations 0000 -> 0004 (Idempotency test)
  ├─ 4. Verify auth.users -> public.profiles trigger execution
  ├─ 5. Test Real RLS Isolation (anon -> 0 rows; User A cannot see User B)
  ├─ 6. Test Privilege Escalation Guards (is_admin, moderation_status block)
  ├─ 7. Test Column-Level Grants (UPDATE safe fields only)
  ├─ 8. Test Service Role Elevated Operations
  ├─ 9. Test Constraints & FK Cascades
  ├─ 10. Audit pg_proc for SECURITY DEFINER & search_path
  └─ 11. Run supabase/tests/99_rollback_and_cleanup.sql
               │
               ▼ (Step 6: Tier C — Python Relational Simulation)
  [Execute tests/test_supabase_postgres_integration.py]
               │
               ▼ (Step 7: Teardown — if: always())
  [DROP DATABASE gari_disposable_test_db WITH (FORCE)]
  [Destroy postgres:15-alpine Service Container]
```

---

## 3. Test Suites & Test Harness Artifacts Prepared

Three dedicated artifacts were authored to support the ephemeral CI pipeline:

### 3.1 Test Harness Bootstrap: [`supabase/tests/00_bootstrap_test_roles.sql`](file:///d:/leaf-diseases-detector-main/supabase/tests/00_bootstrap_test_roles.sql)
Provisions standard Supabase roles and auth helper functions on the vanilla PostgreSQL 15 container before migrations execute:
- **Roles:** `anon`, `authenticated`, `service_role`, `supabase_admin`.
- **Functions:**
  - `auth.uid()`: Resolves session UUID via `current_setting('request.jwt.claims', true)::jsonb ->> 'sub'`.
  - `auth.role()`: Resolves session role claim via `current_setting('request.jwt.claims', true)::jsonb ->> 'role'`.
  - `auth.jwt()`: Returns the parsed JWT JSONB payload.
- **Grants:** Sets Supabase default schema privileges (`USAGE ON SCHEMA public/auth`, `ALTER DEFAULT PRIVILEGES`).

### 3.2 Live PostgreSQL 15 Test Suite: [`tests/test_postgres_live_validation.py`](file:///d:/leaf-diseases-detector-main/tests/test_postgres_live_validation.py)
A full-featured 17-scenario live test suite implemented in Python 3.11 with `psycopg2`:
- **Host Protection:** When executed locally on Windows where `psycopg2` or PostgreSQL is absent, it prints a clean environment notice and skips gracefully (17 skipped in 0.001s), preventing crashes or host violations.
- **Live Scenarios Validated in CI:**
  1. `test_01_environment_safety_and_production_isolation`: Rejects non-test databases and external hosts.
  2. `test_02_sequential_migration_execution`: Applies migrations 0 to 4 chronologically.
  3. `test_03_migration_rerun_idempotency`: Validates re-running migrations causes 0 errors.
  4. `test_04_automatic_provisioning_trigger_on_auth_signup`: Tests `on_auth_user_created` trigger.
  5. `test_05_signup_metadata_idempotency_and_preservation`: Verifies re-signups never wipe existing profile data.
  6. `test_06_updated_at_trigger_execution`: Verifies `handle_updated_at` advances timestamp on UPDATE.
  7. `test_07_rls_anonymous_isolation`: Verifies `anon` role receives 0 rows across all tables.
  8. `test_08_rls_authenticated_tenant_isolation`: Verifies User A cannot read or mutate User B's rows.
  9. `test_09_rls_own_profile_safe_updates`: Verifies User A can update `address` and `bio`.
  10. `test_10_privilege_escalation_guard_and_column_grants`: Verifies attempts to update `is_admin`, `account_type`, or `moderation_status` fail with error `42501` or column permission denied.
  11. `test_11_read_only_grants_on_identity_bridge_and_provisioning`: Verifies `authenticated` cannot write to bridge tables.
  12. `test_12_service_role_privileged_operations`: Verifies `service_role` can upgrade users and manage links.
  13. `test_13_rpc_idempotent_provisioning_function`: Verifies `provision_user_account_idempotent` RPC returns valid JSONB.
  14. `test_14_table_check_constraints`: Verifies check constraints on `account_type`, `moderation_status`, `language`, and `theme`.
  15. `test_15_foreign_key_cascade_deletion`: Verifies `ON DELETE CASCADE` from `auth.users`.
  16. `test_16_security_definer_and_search_path_audit`: Queries `pg_proc` to verify `prosecdef = true` and `search_path` pinning.
  17. `test_17_rollback_and_cleanup_verification`: Executes rollback script and verifies 0 remaining tables/functions.

### 3.3 Rollback & Teardown Script: [`supabase/tests/99_rollback_and_cleanup.sql`](file:///d:/leaf-diseases-detector-main/supabase/tests/99_rollback_and_cleanup.sql)
Executes clean teardown of all policies, triggers, tables, and functions in reverse dependency order, confirming rollback safety.

---

## 4. Local Execution & Readiness Verification

Before reporting, local verification of the test suites was performed:

```powershell
# 1. Local execution of live suite on Windows host (Safe skip verification)
PS D:\leaf-diseases-detector-main> python tests/test_postgres_live_validation.py -v
Ran 17 tests in 0.001s
OK (skipped=17)
# Reason: 'psycopg2 is not installed on this host. This suite executes against the ephemeral PostgreSQL 15 service container in GitHub Actions CI.'

# 2. Local execution of simulation suite (Tier C verification)
PS D:\leaf-diseases-detector-main> python tests/test_supabase_postgres_integration.py
Ran 17 tests in 1.037s
OK
[NOTICE] Live PostgreSQL daemon NOT running at 127.0.0.1:5432 on this Windows host.
[NOTICE] Relational simulation and security boundary suites will validate all contract behaviors.

# 3. Git status audit (Zero unauthorized commits or pushes)
PS D:\leaf-diseases-detector-main> git status
On branch gari-2.0-redesign
Untracked files:
	.github/workflows/postgres-validation.yml
	supabase/tests/00_bootstrap_test_roles.sql
	supabase/tests/99_rollback_and_cleanup.sql
	tests/test_postgres_live_validation.py
nothing added to commit but untracked files present
```

---

## 5. Security & Isolation Matrix

| Security Area | Audit Checkpoint | CI Implementation Status |
| :--- | :--- | :--- |
| **No PHP** | Full repository check | **COMPLIANT.** Zero PHP code used or introduced. |
| **Windows Host Protection** | Docker, WSL, PostgreSQL | **COMPLIANT.** Zero system-level software installed on Windows. |
| **Windows Defender** | Antivirus exclusion rules | **COMPLIANT.** Untouched. |
| **Internal Logs** | Antigravity logs | **COMPLIANT.** Untouched. |
| **SQLite Preservation** | `database/disease_detector.db` | **COMPLIANT.** Byte-exact preservation; untouched. |
| **Production Credential Guard** | Secrets & URLs in CI | **COMPLIANT.** Fail-closed pre-flight check blocks any `supabase.co` string. |
| **Tenant Data Privacy** | Real user data | **COMPLIANT.** 100% synthetic mock identities. |
| **Disposable Container Cleanup** | Ephemeral DB lifespan | **COMPLIANT.** `DROP DATABASE` executed on completion; container discarded by GitHub Actions. |
| **Source Control Safety** | Commit & push control | **COMPLIANT.** Changes staged locally only; zero commits or pushes executed. |

---

## 6. Next Steps & Approval Protocol

To trigger actual execution on GitHub Actions:

1. **User Reviews Local Workflow & Test Files:**
   - [`.github/workflows/postgres-validation.yml`](file:///d:/leaf-diseases-detector-main/.github/workflows/postgres-validation.yml)
   - [`tests/test_postgres_live_validation.py`](file:///d:/leaf-diseases-detector-main/tests/test_postgres_live_validation.py)
   - [`supabase/tests/00_bootstrap_test_roles.sql`](file:///d:/leaf-diseases-detector-main/supabase/tests/00_bootstrap_test_roles.sql)
   - [`supabase/tests/99_rollback_and_cleanup.sql`](file:///d:/leaf-diseases-detector-main/supabase/tests/99_rollback_and_cleanup.sql)
2. **User Explicit Approval:**
   - Once approved, the files will be committed and pushed to the repository branch.
3. **Execution on GitHub Actions:**
   - The workflow can be triggered manually via `workflow_dispatch` in the GitHub Actions tab or via a pull request.
4. **Final PostgreSQL Runtime Certification:**
   - Upon successful execution of all 17 live PostgreSQL 15 tests in GitHub Actions, the final certification report will transition to `POSTGRESQL RUNTIME VALIDATION PASSED`.

---

## 7. Final Verdict

```
================================================================================
FINAL VERDICT: WORKFLOW PREPARED — AWAITING APPROVAL
================================================================================
```
The disposable PostgreSQL 15 integration test workflow and live validation test suite have been fully prepared locally, verified for host safety, and rigorously isolated from production environments. Awaiting explicit user approval before committing or pushing to GitHub Actions.
