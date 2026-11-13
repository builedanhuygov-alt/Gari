# GARI AgriTech AI Lab — Supabase Auth Security Checklist & Verification Matrix

**Document ID:** GARI-CHK-SUPABASE-SECURITY-2026-01  
**Project:** GARI AgriTech AI Lab  
**Scope:** Security Assurance, JWT Integrity, RLS Enforcement, Threat Model  
**Date:** 2026-11-11  
**Status:** ACTIVE VERIFICATION CHECKLIST  

---

## 1. Security Architecture Verification Checklist

| Security Requirement | Verification Criterion | Enforcement Mechanism | Status |
|---|---|---|:---:|
| **No PHP or Webshell Artifacts** | Zero `.php` files or shell-like strings across the workspace. | Static file scans, AST audit, Windows Defender real-time protection. | **VERIFIED** |
| **No Secret Exposure in Client** | Browser code contains only `SUPABASE_PUBLISHABLE_KEY` / `anon_key`. Never `service_role` or secret keys. | Code review of `frontend2/` and build bundle inspection. | **VERIFIED** |
| **Asymmetric JWT Verification** | FastAPI validates signature using JWKS (`RS256`/`ES256`). Rejects `none` algorithm. | `PyJWKClient` cryptographic signature validation in `gari_auth.py`. | **PLANNED** |
| **Issuer & Audience Validation** | Rejects tokens with mismatched `iss` or `aud != 'authenticated'`. | Exact claim matching in `jwt.decode()`. | **PLANNED** |
| **Subject Claim Binding** | Rejects tokens missing `sub` (UUID). Never trusts client-submitted user IDs. | Backend derives identity strictly from verified `sub`. | **PLANNED** |
| **Row-Level Security (RLS)** | All public tables (`profiles`, `user_preferences`, etc.) enforce RLS with `auth.uid()`. | Explicit PostgreSQL policies with zero bypass for `authenticated` role. | **SPECIFIED** |
| **Identity Bridge Isolation** | Users cannot link arbitrary SQLite user IDs or alter other users' links. | `gari_identity_links` write access restricted to `service_role`. | **SPECIFIED** |
| **Fail-Closed Availability** | If Supabase or JWKS is unreachable and cache expired, return HTTP 503. | Explicit exception handling in `gari_auth.py` without mock bypass. | **PLANNED** |
| **Rate Limiting & Brute-Force** | Protects against credential stuffing on authentication endpoints. | Supabase Auth native rate limits + FastAPI IP throttling. | **PLANNED** |
| **No Production Deployment** | Zero use of `vercel --prod` or production credential modification. | Deployment scripts strictly target Preview channel. | **VERIFIED** |

---

## 2. Comprehensive 20-Scenario Security Test Matrix (Phase 8)

| Scenario ID | Test Scenario | Category | Expected Response / Behavior | Verification Method |
|:---:|---|---|---|---|
| **A** | **Valid Registration** | Functional | User created in Supabase Auth, profile inserted, returns valid JWT session or verification notice. | Integration / Browser |
| **B** | **Duplicate Email** | Input Validation | Rejects with HTTP 400 / 422, clear error: "Email đã được sử dụng." | Mock Integration |
| **C** | **Invalid Password** | Input Validation | Rejects passwords < 6 chars or violating complexity rules. | Client + API Unit |
| **D** | **Email Verification Pending** | Authorization | Rejects protected API access if unverified email policy is enforced. | Mock Integration |
| **E** | **Valid Login** | Functional | Returns valid access token and refresh token, cookies set appropriately. | Integration / Browser |
| **F** | **Invalid Login** | Authentication | Rejects incorrect credentials with HTTP 400/401; no username enumeration. | Mock Integration |
| **G** | **Refresh Session** | Session Mgt | Refreshes access token seamlessly via refresh token before expiry. | Browser / SDK Test |
| **H** | **Logout** | Session Mgt | Revokes Supabase session; purges client tokens; invalidates cookies. | Integration / Browser |
| **I** | **Expired JWT** | Security Gate | FastAPI rejects token where `exp < now()` with HTTP 401. | Unit (Tampered Token) |
| **J** | **Invalid Signature** | Cryptographic | FastAPI rejects token signed with wrong key or altered payload with HTTP 401. | Unit (Tampered Token) |
| **K** | **Wrong Issuer** | Cryptographic | Rejects token where `iss != https://<proj>.supabase.co/auth/v1` with HTTP 401. | Unit (Forged Issuer) |
| **L** | **Wrong Audience** | Cryptographic | Rejects token where `aud != 'authenticated'` (e.g. `aud: 'anon'`) with HTTP 401. | Unit (Anon Token) |
| **M** | **Missing Subject (`sub`)** | Cryptographic | Rejects token lacking `sub` UUID claim with HTTP 401. | Unit (Missing Claim) |
| **N** | **Cross-User Data Access** | Authorization | User A attempting to read/update User B's profile via RLS is blocked (HTTP 403 / 0 rows). | PostgreSQL RLS Test |
| **O** | **Cross-Tenant Access** | Authorization | User A attempting to access Farm/Plot belonging to Organization B is rejected (HTTP 403). | FastAPI Integration |
| **P** | **SQLite Identity Mapping** | Identity Bridge| Verified `sub` correctly resolves to expected `sqlite_user_id` in SQLite. | Database Integration |
| **Q** | **Duplicate Provisioning** | Idempotency | Retrying registration sync for existing user does not create duplicate SQLite rows. | State Machine Unit |
| **R** | **PostgreSQL Unavailable** | Resilience | Returns HTTP 503; client displays controlled maintenance banner without hang. | Mock Fault Injection |
| **S** | **SQLite Unavailable** | Resilience | Returns HTTP 503; prevents partial user creation; client does not hang. | Mock Fault Injection |
| **T** | **Supabase Auth Unavailable**| Resilience | Gateway / FastAPI returns HTTP 503; client button unfreezes cleanly within 10s. | Browser Fault Injection |

---

## 3. Test Tier Classification

To avoid misleading aggregate pass rates, all test results are reported across four distinct tiers:

1. **Unit Tests:** Isolated token validation, cryptographic signature tests, input sanitization, and state machine transition tests.
2. **Mock Integration Tests:** Node.js / Python tests simulating Supabase JWKS responses and testing FastAPI dependency resolution.
3. **Real Local Integration Tests:** End-to-end tests running against local FastAPI and SQLite (`database/disease_detector.db`).
4. **Live Preview Browser Tests:** Playwright / Chromium headless tests verifying actual UI clicks, form inputs, cookie storage, and session lifecycle.

