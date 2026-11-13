# GARI AgriTech AI Lab — Supabase Auth Architecture

**Document ID:** GARI-ARCH-SUPABASE-AUTH-2026-01  
**Project:** GARI AgriTech AI Lab  
**Target Environment:** Preview Channel Only (Vercel + Supabase + Local FastAPI)  
**Architecture Pattern:** Hybrid Database Architecture (Supabase Auth/PostgreSQL + SQLite Business Core)  
**Date:** 2026-11-11  
**Architect:** Antigravity AI Senior Systems Architect  

---

## 1. Architectural Overview & Design Motivation

The GARI platform is modernizing its authentication system by replacing fragmented legacy authorities (Firebase Auth SDK + local PBKDF2 hash tables) with **Supabase Auth**.

### 1.1 The Hybrid Database Rationale
* **GARI Business Domain in SQLite (`database/disease_detector.db`):** Contains **59 tables** (e.g. `farms`, `farm_plots`, `crops`, `diagnoses`, `predictions`, `cultivation_tasks`, `organizations`, `expert_cases`, `payment_orders`) deeply keyed to internal integer user IDs (`user_id INTEGER`). Overwriting or migrating this schema to a distributed database risks data corruption, complex migration downtime, and foreign-key breakage across thousands of agricultural records.
* **Supabase PostgreSQL Identity Subsystem:** Modernizes user registration, asymmetric JWT authentication, row-level security (RLS), password recovery, and email verification in a dedicated identity schema.
* **The Bridge (`gari_identity_links`):** Connects `supabase_uid (UUID)` with `sqlite_user_id (INTEGER)` safely and idempotently.

---

## 2. End-to-End System Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                                 CLIENT TIER                                       |
|  [ frontend2/login.html ]      [ frontend2/register.html ]      [ Dashboard UI ] |
|            |                                |                           |         |
|            | 1. Supabase Auth               |                           |         |
|            |    signUp / signInWithPassword |                           |         |
|            v                                |                           |         |
|  +---------------------+                    |                           |         |
|  |  Supabase Auth SDK  |                    |                           |         |
|  |  (@supabase/js v2)  |                    |                           |         |
|  +---------------------+                    |                           |         |
|            |                                |                           |         |
|            | 2. Receives Asymmetric JWT     |                           |         |
|            |    (RS256/ES256, exp 3600s)    |                           |         |
|            +--------------------------------+---------------------------+         |
|                                             |                                     |
|                                             | 3. HTTPS with Bearer <JWT>          |
+---------------------------------------------|-------------------------------------+
                                              |
                                              v
+-----------------------------------------------------------------------------------+
|                           EDGE GATEWAY (Vercel)                                   |
|  [ api/[...path].js ]                                                             |
|  - Request Body Buffering (Prevents stream deadlock)                              |
|  - Pure Reverse Proxy (Zero auth authority, zero token minting)                   |
|  - Fail-Closed: Returns HTTP 503 BACKEND_UNAVAILABLE if FastAPI offline           |
+-----------------------------------------------------------------------------------+
                                              |
                                              | 4. Proxied Request
                                              v
+-----------------------------------------------------------------------------------+
|                        AUTHORITATIVE BACKEND (FastAPI)                            |
|                                                                                   |
|  [ gari_auth.py: get_current_user ] <------------------+                          |
|         │                                               │                         |
|         ├──> A. Fetch / Cache JWKS (public keys)        │                         |
|         │    from https://<proj>.supabase.co/auth/v1/.well-known/jwks.json        |
|         │                                                                         |
|         ├──> B. Cryptographically Verify JWT:                                     |
|         │    - Valid signature against JWK matching 'kid'                         |
|         │    - Issuer: https://<proj>.supabase.co/auth/v1                         |
|         │    - Audience: 'authenticated'                                          |
|         │    - Expiration: exp > now()                                            |
|         │    - Subject: sub (UUID)                                                |
|         │                                                                         |
|         └──> C. Resolve Identity Bridge:                                          |
|              Query gari_identity_links for supabase_uid                           |
|              - Found: Inject SQLite user record into Request Context              |
|              - Not Found: Execute Idempotent Provisioning State Machine           |
+-----------------------------------------------------------------------------------+
         │                                                        │
         │ 5a. Profile / Bridge Sync                              │ 5b. Business Data
         v                                                        v
+-----------------------------------+    +------------------------------------------+
|      SUPABASE POSTGRESQL          |    |          GARI SQLITE DATABASE            |
|  - auth.users (Managed by Auth)   |    |  [ database/disease_detector.db ]        |
|  - public.profiles (RLS protected)|    |  - users (id INTEGER, role, status)      |
|  - public.user_preferences (RLS)  |    |  - farms, farm_plots, crops              |
|  - public.gari_identity_links     |    |  - diagnoses, predictions, AI history    |
|  - public.account_provisioning    |    |  - 59 user-linked business tables        |
+-----------------------------------+    +------------------------------------------+
```

---

## 3. Database Ownership & Separation of Concerns

| Data Domain | Database Engine | Tables Owned | Access Control / Security |
|---|---|---|---|
| **Identity & Credentials** | Supabase Auth (`auth`) | `auth.users`, `auth.identities`, `auth.sessions` | Managed exclusively by Supabase Auth engine. Never queried directly via public client. |
| **User Profile & Settings** | Supabase PostgreSQL (`public`) | `profiles`, `user_preferences` | Strict Row-Level Security (RLS). Users can only `SELECT` and `UPDATE` their own row where `id = auth.uid()`. |
| **Identity Bridge** | Supabase PostgreSQL (`public`) | `gari_identity_links`, `account_provisioning` | RLS: Service Role / Backend only for writes; user read-only for provisioning status. |
| **Agricultural Business Operations** | Local SQLite (`database/disease_detector.db`) | 59 business tables (`farms`, `crops`, `diagnoses`, `tasks`, etc.) | Controlled exclusively by FastAPI backend using verified `sqlite_user_id`. Zero direct client exposure. |

---

## 4. Identity Mapping & Resolution Sequence

```
[ Incoming Request with Bearer JWT ]
           │
           ▼
[ Cryptographic JWT Verification (gari_auth.py) ]
           │
           ├── Invalid Signature / Expired ──> Return HTTP 401 Unauthorized
           │
           ▼ (Valid JWT, sub = <supabase_uid>)
[ Query gari_identity_links(supabase_uid) ]
           │
     ┌─────┴─────────────────────────────────┐
     ▼                                       ▼
[ Record Exists ]                     [ Record Does Not Exist ]
     │                                       │
     │ Read sqlite_user_id                   ▼
     │                                [ Provisioning Flow ]
     ▼                                       │
[ Fetch SQLite User ]                        ├── Create/Verify SQLite User
     │                                       ├── Insert gari_identity_links
     ├── User banned / inactive?             └── Insert account_provisioning (ACTIVE)
     │   └── Return HTTP 401/403             │
     │                                       ▼
     ▼                                [ Return Valid Context ]
[ Execute Route Handler ]
```

---

## 5. Security Invariants

1. **Zero Client Trust for User IDs:** The frontend never sends `sqlite_user_id`. The backend exclusively derives `sqlite_user_id` from the verified `sub` claim of the Supabase JWT.
2. **Asymmetric Key Verification:** Fast verification using public JWKS. No shared secrets or symmetric HMAC keys stored on edge proxies.
3. **Fail-Closed Principle:** If Supabase Auth or the JWKS endpoint is unreachable and cache expires, backend returns **HTTP 503** — it never defaults to a mock or synthetic user.
4. **No Fallback Authentication:** GARI custom token minting and legacy password verifiers are removed from the active path.
5. **Preview Isolation:** Runs on a dedicated Supabase Preview project and Vercel Preview URL. Production SQLite database and live user sessions are never altered.

