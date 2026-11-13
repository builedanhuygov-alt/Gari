# GARI AgriTech AI Platform — Sprint 1: Supabase Foundation Implementation Report

**Document ID:** GARI-REPORT-SPRINT1-2026-01  
**Project:** GARI AgriTech AI Platform  
**Target Environment:** Local Standalone & Supabase Preview Foundation  
**Date:** 2026-11-11  
**Status:** COMPLETE — LOCAL TESTS VERIFIED  

---

## 1. Executive Summary

Sprint 1 successfully implements the core **Supabase Foundation** locally, establishing the database schema, security rules, and identity mapping mechanisms required for GARI's hybrid cloud architecture. 

All database definitions, Row Level Security (RLS) policies, idempotent provisioning logic, and privilege guards have been codified into versioned SQL migrations and thoroughly validated through automated test suites.

**Sprint 1 Verdict:** `SPRINT 1 COMPLETE`

---

## 2. Implemented Schema & Architecture Reconciliation

The PostgreSQL foundation reconciles GARI's business needs with the existing 86-table SQLite database (`database/disease_detector.db`):

| PostgreSQL Table | SQLite Counterpart / Source | Primary Role | Security & Access Level |
| :--- | :--- | :--- | :--- |
| **`public.profiles`** | `users` (id, full_name, phone, province, account_type, etc.) | User identity, farmer profile, role indicators | RLS enabled; `auth.uid() = id`; privilege guard trigger active |
| **`public.user_preferences`**| `users` (localization, notification flags) | UI theme, language ('vi', 'en'), timezone, alerts | RLS enabled; `auth.uid() = user_id` |
| **`public.gari_identity_links`**| `gari_identity_links` | Authoritative bridge mapping Supabase UUID to SQLite integer ID | Strict 1:1 unique constraint; Read-only for users; Write-only for `service_role` |
| **`public.account_provisioning`**| `account_provisioning` | Idempotent onboarding state machine (PENDING, ACTIVE, FAILED) | Read-only for users; Write-only for `service_role` |

---

## 3. Versioned Migrations Created (`supabase/migrations/`)

Five sequential, idempotent SQL migration files were authored in [`supabase/migrations/`](file:///d:/leaf-diseases-detector-main/supabase/migrations/):

### 3.1 [`20261111120000_create_base_schema_and_profiles.sql`](file:///d:/leaf-diseases-detector-main/supabase/migrations/20261111120000_create_base_schema_and_profiles.sql)
- Enables `uuid-ossp` and `pgcrypto` extensions.
- Creates universal `handle_updated_at()` trigger function.
- Creates `public.profiles` with primary key referencing `auth.users(id) ON DELETE CASCADE`.
- Defines constraints on `account_type` (`farmer`, `enterprise`, `expert`, `host_admin`) and `moderation_status` (`clean`, `flagged`, `suspended`, `under_review`).
- Configures partial and standard indexes for phone numbers, account types, and admin flags.

### 3.2 [`20261111120001_create_user_preferences.sql`](file:///d:/leaf-diseases-detector-main/supabase/migrations/20261111120001_create_user_preferences.sql)
- Creates `public.user_preferences` linked 1:1 to `public.profiles(id)`.
- Defines check constraints: `language IN ('vi', 'en')`, `theme IN ('light', 'dark', 'system')`.
- Stores structured notification preferences as JSONB with Vietnamese localization defaults.

### 3.3 [`20261111120002_create_identity_bridge_and_provisioning.sql`](file:///d:/leaf-diseases-detector-main/supabase/migrations/20261111120002_create_identity_bridge_and_provisioning.sql)
- Creates `public.gari_identity_links` with bidirectional `UNIQUE` constraints on both `supabase_uid` and `sqlite_user_id` to guarantee unbroken 1:1 identity mapping.
- Creates `public.account_provisioning` tracking onboarding retry counts and diagnostic metadata.

### 3.4 [`20261111120003_create_idempotent_provisioning_trigger.sql`](file:///d:/leaf-diseases-detector-main/supabase/migrations/20261111120003_create_idempotent_provisioning_trigger.sql)
- Implements `handle_new_user_signup()` trigger function on `auth.users` (`AFTER INSERT`).
- Guarantees idempotent upsert using `ON CONFLICT (id) DO UPDATE` and `ON CONFLICT DO NOTHING`.
- Disallows administrative role assignment via client metadata (forces `is_admin = false`, `is_host_admin = false`).
- Implements `provision_user_account_idempotent()` RPC for serverless replay and reconciliation.

### 3.5 [`20261111120004_create_rls_and_privilege_guards.sql`](file:///d:/leaf-diseases-detector-main/supabase/migrations/20261111120004_create_rls_and_privilege_guards.sql)
- Enables Row Level Security on all 4 tables.
- **Role Escalation Protection:** Implements `protect_profile_privileged_fields()` trigger function. Rejects updates to `account_type`, `is_admin`, `is_host_admin`, `is_expert`, `is_active`, `moderation_status`, or `feature_restrictions` unless the caller is `service_role`.
- **Identity Link Immutability:** Grants `SELECT` only to `authenticated` users on `gari_identity_links` and `account_provisioning`. All write access is revoked from client roles.
- **Column-Level Least Privilege:** Revokes blanket `UPDATE` on `public.profiles` from `authenticated`; explicitly grants updates only to safe personal fields (`full_name`, `phone`, `province`, `address`, `avatar_url`, `bio`).

---

## 4. Test Execution & Verification

### 4.1 Sprint 1 Test Suite: [`tests/test_supabase_foundation.py`](file:///d:/leaf-diseases-detector-main/tests/test_supabase_foundation.py)
Executed locally via `.venv\Scripts\python.exe`:
```
Ran 13 tests in 0.012s
OK
```

#### Detailed Test Verification Matrix:
| Test Method | Description | Result |
| :--- | :--- | :---: |
| `test_01_migration_files_present_and_ordered` | Chronological ordering and presence of 5 migration files | **PASS** |
| `test_02_ddl_tables_defined_with_proper_constraints`| DDL schema, foreign keys, cascade rules, and check constraints | **PASS** |
| `test_03_row_level_security_explicitly_enabled` | Verification that RLS is active on all 4 foundation tables | **PASS** |
| `test_04_rls_policies_least_privilege_enforcement` | Tenant isolation: `auth.uid() = id`, write lockouts on bridge | **PASS** |
| `test_05_role_escalation_guard_implementation` | Trigger guard presence for all 7 privileged columns | **PASS** |
| `test_06_column_level_security_permissions` | Column-level update grants and write revokes | **PASS** |
| `test_07_idempotent_provisioning_trigger_design` | Conflict-handling upsert patterns on sign-up | **PASS** |
| `test_08_migration_repeatability_and_idempotency` | Idempotent guards (`IF NOT EXISTS`, `OR REPLACE`) on all DDL | **PASS** |
| `test_09_foreign_key_cascading_deletion` | Relational simulation: Cascade deletion from auth.users | **PASS** |
| `test_10_identity_bridge_1_to_1_integrity` | Rejection of duplicate mappings for `sqlite_user_id` & `supabase_uid`| **PASS** |
| `test_11_check_constraints_enforcement` | Rejection of invalid account types and unsupported languages | **PASS** |
| `test_12_idempotent_upsert_simulation` | Successful re-provisioning without unique constraint crashes | **PASS** |
| `test_13_simulated_role_escalation_guard` | PermissionError raised when regular user attempts privilege escalation| **PASS** |

### 4.2 Auth Integration Security Suite: [`tests/test_supabase_auth_suite.py`](file:///d:/leaf-diseases-detector-main/tests/test_supabase_auth_suite.py)
Executed locally:
```
Ran 20 tests in 0.414s
OK
```
*Confirmed zero regressions across JWT cryptographic validation, session extraction, and SQLite bridge persistence.*

---

## 5. Security & Safety Compliance Checklist

- [x] **Strictly Zero PHP:** No PHP code, files, or extensions exist or were created.
- [x] **Windows Defender Unmodified:** No exclusions or security overrides applied.
- [x] **Antigravity Logs Untouched:** Internal transcript and conversation logs remain pristine.
- [x] **SQLite Baseline Preserved:** `database\disease_detector.db` was not modified, reset, or truncated.
- [x] **Zero Real User Migration:** No production or staging user records were altered or pushed.
- [x] **Zero Synthetic Production Accounts:** All tests run strictly in-memory or on designated local test tables.
- [x] **Zero Secret Exposure:** No secret keys or service role tokens stored in version control or output logs.
- [x] **No Git Commits / Deployments:** All files remain local for user review.

---

## 6. Stop Condition & Next Steps

All requirements for **Sprint 1: Supabase Foundation Implementation** have been completed locally. 

**Next Recommended Sprint (Sprint 2):**
- Implementation of the **Durable Diagnosis Job Queue** (`diagnosis_jobs` table and `claim_next_diagnosis_job` RPC).
- Creation of the local Windows AI worker daemon (`worker/gari_ai_worker.py`).

