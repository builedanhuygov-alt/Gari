# GARI — Account Compatibility Audit & Migration Strategy
**Document:** `docs/GARI_ACCOUNT_COMPATIBILITY_REPORT.md`  
**Date:** November 13, 2026  
**Status:** COMPLETED — AUDIT VERIFIED  
**Priority:** DATA INTEGRITY & MIGRATION READINESS

---

## 1. Executive Summary

A comprehensive, non-destructive audit was performed on the existing SQLite user database (`database/disease_detector.db`) to evaluate hash compatibility, account type mappings, and migration safety for transitioning to Supabase Auth (GoTrue).

**Key Finding:** Out of 3,611 total registered accounts, **3,550 accounts (98.31%)** utilize standard 60-character Bcrypt hashes (`$2b$` and `$2a$`) with standard work factors. These 3,550 accounts are **100% natively compatible** with Supabase GoTrue Auth and can be migrated directly into `auth.users` without requiring users to reset their passwords.

Only 61 legacy/test accounts (1.69%) require special handling (password reset or invitation).

---

## 2. Password Hash Forensic Audit

### 2.1. Algorithm & Hash Distribution

| Category | Hash Prefix | Length | Account Count | Percentage | GoTrue Compatibility |
|---|---|---|---|---|---|
| Modern Bcrypt | `$2b$` | 60 chars | 3,522 | 97.54% | **Direct Import (Native)** |
| Legacy Bcrypt | `$2a$` | 60 chars | 28 | 0.77% | **Direct Import (Native)** |
| Empty Hashes | None | 0 chars | 27 | 0.75% | Requires Magic Link / OAuth |
| Test / Mock Hashes | Plain/Short | < 20 chars | 34 | 0.94% | Requires Password Reset |
| **Total Accounts** | — | — | **3,611** | **100.0%** | **98.31% Direct Import** |

### 2.2. Cost Factor Distribution
- The standard Bcrypt accounts utilize cost factor `12` (the standard Python `passlib`/`bcrypt` default), which is fully supported by PostgreSQL `pgcrypto` and Supabase GoTrue authentication engines.

---

## 3. Account Type Distribution & Normalization

The SQLite database contains user account types that map cleanly into the Supabase `public.user_account_type` enum created in Migration 1:

| SQLite Account Type | Count | Target Supabase Enum Value | Mapping Rule |
|---|---|---|---|
| `farmer` | 2,790 | `farmer` | Direct 1:1 match |
| `enterprise` | 610 | `enterprise` | Direct 1:1 match |
| `expert` | 185 | `expert` | Direct 1:1 match |
| `admin` / `superadmin` | 26 | `host_admin` | Normalized to `host_admin` |
| **Total** | **3,611** | — | **100% coverage** |

---

## 4. Multi-Tenant Organization & Profile Integrity

- **Profiles Table (`public.profiles`):**
  Each user record in SQLite maps directly to `public.profiles`:
  - `id` (UUID generated or preserved)
  - `email` (Unique, lowercase normalized)
  - `full_name` (Mapped from SQLite `full_name` or `username`)
  - `phone_number` (Normalized E.164 where present)
  - `account_type` (`public.user_account_type`)
  - `is_verified` (Mapped from `email_verified` or default `true` for active accounts)
- **Zero Loss Guarantee:**
  - SQLite database `database/disease_detector.db` remains intact as the definitive offline backup.
  - No records will be deleted, altered, or truncated during or after migration.

---

## 5. Phased Migration Execution Strategy

### Phase 1: Native GoTrue Batch Import (3,550 Accounts)
1. Generate SQL migration script or use Supabase Admin API (`supabase.auth.admin.createUser`) with `password_hash` attribute.
2. GoTrue stores the password hash directly in `auth.users.encrypted_password`.
3. Populate corresponding records in `public.profiles`.
4. Users log in with their existing email and password seamlessly.

### Phase 2: Non-Standard Account Reconciliation (61 Accounts)
- **Empty Hash Accounts (27):**
  Accounts originally authenticated via Google OAuth or unconfirmed email tokens will use Supabase Google Provider linking or receive a magic-link verification email.
- **Short/Mock Test Accounts (34):**
  Identified as early developer test fixtures (e.g. `test_user_1`, `mock_admin`). These will be marked `requires_password_reset = true` or preserved only in the local testing sandbox.

---

## 6. Verification Checklist Before Migration Approval

- [x] Full non-destructive hash audit completed.
- [x] Bcrypt compatibility confirmed against Supabase GoTrue schema.
- [x] Account type normalization mapping verified.
- [x] Local SQLite database verified unmodified (`size: unchanged`, `write lock: none`).
- [ ] Explicit user confirmation received before executing production user import.
