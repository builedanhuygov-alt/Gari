# GARI AgriTech AI Lab — Supabase Auth Discovery Report

**Document ID:** GARI-DISC-SUPABASE-AUTH-2026-01  
**Project:** GARI AgriTech AI Lab  
**Repository:** `D:\leaf-diseases-detector-main`  
**Phase:** Phase 0 — Read-Only Discovery  
**Audit Date:** 2026-11-11  
**Auditor:** Antigravity AI Systems Architect & Security Specialist  
**Mode:** READ-ONLY COMPREHENSIVE DISCOVERY (Zero Code Modifications)  

---

## 1. Executive Summary

This discovery audit investigates the current authentication and authorization architecture of GARI AgriTech AI Lab across frontend, edge gateway, API server, and SQLite database tiers.

The target architecture introduces **Supabase Auth** and a **Hybrid Database Architecture**:
- **Identity & Profiles:** Supabase Auth + Supabase PostgreSQL (`profiles`, `user_preferences`, `gari_identity_links`, `account_provisioning`).
- **Business Operations & Intelligence:** Existing SQLite (`database/disease_detector.db`, 59 user-linked tables) preserving all farm records, AI predictions, cultivation schedules, and payments.
- **Backend Core:** Python FastAPI (`api_server.py`, `gari_auth.py`).
- **Edge Gateway:** Vercel reverse proxy only (`api/[...path].js`).

---

## 2. Inventory of Current Registration, Login & Logout

### 2.1 Registration Paths
1. **Frontend UI:** [`frontend2/register.html`](file:///d:/leaf-diseases-detector-main/frontend2/register.html)
   - Invokes `window.gariAuth.register(name, email, password, phone, province, accountType)`.
   - Primary path: Firebase Auth SDK `createUserWithEmailAndPassword()` via [`frontend2/firebase-client.js`](file:///d:/leaf-diseases-detector-main/frontend2/firebase-client.js).
   - Post-creation token exchange: Calls `/api/auth/firebase-login` with `id_token`.
   - Fallback path: Direct POST to `/api/auth/register` (Fail-Closed, requires backend).
2. **Backend API:** `POST /api/auth/register` in [`api_server.py:751`](file:///d:/leaf-diseases-detector-main/api_server.py#L751)
   - Handler: `gari_auth.register_user(payload)`.
   - Password hashing: PBKDF2-SHA256 (100,000 iterations) with unique salt.
   - Database writes: `users`, `user_account_type_audit`, `user_subscriptions`.
   - Session creation: Issues local cryptographically secure random token (`secrets.token_urlsafe(36)`).

### 2.2 Login Paths
1. **Frontend UI:** [`frontend2/login.html`](file:///d:/leaf-diseases-detector-main/frontend2/login.html)
   - Form submit handler calls `window.gariAuth.login(email, password, rememberMe)`.
   - Primary path: `signInWithEmailAndPassword()` via Firebase Auth SDK, followed by `_exchangeFirebaseToken()`.
   - Secondary path: Direct POST `/api/auth/login` returning session token.
2. **Host Admin Login:** [`frontend2/host-login.html`](file:///d:/leaf-diseases-detector-main/frontend2/host-login.html)
   - Dedicated console for host administrators (`POST /api/auth/host-login`).
   - Requires explicit `is_host_admin == 1` authorization flag.
3. **Backend API:** `POST /api/auth/login` in [`api_server.py:810`](file:///d:/leaf-diseases-detector-main/api_server.py#L810)
   - Handler: `gari_auth.authenticate_user()`.
   - Rate limiting: Max 5 failed attempts per 300 seconds (`_FAILED_ATTEMPTS`).
   - Validates PBKDF2 hash, verifies `is_active == 1` and `moderation_status != 'banned'`.
   - Sets HttpOnly cookie `gari_session` and returns `{ success: true, token, user }`.

### 2.3 Logout Paths
1. **Frontend Client:** `window.gariAuth.logout()` in [`frontend2/firebase-client.js:512`](file:///d:/leaf-diseases-detector-main/frontend2/firebase-client.js#L512)
   - Executes Firebase `signOut(this.firebaseAuth)` if initialized.
   - Purges local storage: removes all keys prefixed with `gari_` and `firebase:authUser`.
   - Purges session storage: removes all keys prefixed with `gari_` and `firebase:authUser`.
   - Notifies client listeners with `null` user.
   - Dispatches async call to `POST /api/auth/logout` with bounded 2.5s timeout.
2. **Backend API:** `POST /api/auth/logout` in [`api_server.py:867`](file:///d:/leaf-diseases-detector-main/api_server.py#L867)
   - Invokes `gari_auth.destroy_session(token)`.
   - Deletes session row from SQLite table `user_sessions`.
   - Clears `gari_session` cookie on response.

---

## 3. Firebase Auth Dependencies & Usage

### 3.1 Client-Side Firebase Dependencies
- [`frontend2/firebase-client.js`](file:///d:/leaf-diseases-detector-main/frontend2/firebase-client.js):
  - Dynamically imports ESM bundles from Google CDN:
    - `https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js`
    - `https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js`
  - Uses `onIdTokenChanged` and `onAuthStateChanged` listeners.
  - Interacts with `/api/auth/firebase-config` to retrieve public client credentials (`apiKey`, `projectId`, `authDomain`).

### 3.2 Server-Side Firebase Dependencies
- [`gari_firebase.py`](file:///d:/leaf-diseases-detector-main/gari_firebase.py):
  - Imports `firebase_admin` (`auth`, `credentials`).
  - Reads `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_CREDENTIALS_JSON`.
  - In absence of service account credentials, falls back to test/development mock verification (`firebase_test_*`).
  - `verify_firebase_id_token(id_token)` verifies cryptographically via Google's public certs.
  - `get_or_sync_firebase_user(token_data)` syncs `firebase_uid` to SQLite `users` table.

---

## 4. GARI-Issued Token Mechanisms

1. **Format:** URL-safe Base64 string generated by `secrets.token_urlsafe(36)` (~48 characters).
2. **Storage:** Stored in SQLite table `user_sessions` with fields:
   - `token` (TEXT PRIMARY KEY)
   - `user_id` (INTEGER REFERENCES users(id))
   - `expires_at` (DATETIME)
   - `ip_address` (TEXT)
   - `user_agent` (TEXT)
   - `created_at` (DATETIME)
3. **Transport:** Transmitted via either:
   - Header: `Authorization: Bearer <token>`
   - Cookie: `gari_session=<token>` (HttpOnly, SameSite=Lax)
4. **Validation:** `gari_auth.validate_session(token)` queries `user_sessions` joined with `users` where `token = ?` and `expires_at > CURRENT_TIMESTAMP`.

---

## 5. Protected FastAPI Endpoints & Authorization Logic

A full AST audit of [`api_server.py`](file:///d:/leaf-diseases-detector-main/api_server.py) identified **280 protected endpoints** relying on `gari_auth`:

| Dependency | Count | Security Policy |
|---|:---:|---|
| `get_current_user` | **182** | Enforces valid authenticated user session. Rejects unauthenticated requests with HTTP 401. |
| `get_current_host_admin` | **52** | Enforces Host Server Admin (`is_host_admin == 1`). Rejects regular users with HTTP 403 Forbidden. Records immutable audit in `host_audit_logs`. |
| `get_current_admin_user` | **32** | Enforces Platform Admin (`is_admin == 1` or account type admin). Rejects standard users with HTTP 403 Forbidden. |
| `get_current_user_optional` | **10** | Contextual authentication (e.g. public diagnosis where user quota tracking applies if signed in). |
| `get_current_expert_user` | **4** | Enforces verified agronomist role (`is_expert == 1` or `is_host_admin == 1`). Rejects with HTTP 403 Forbidden. |

### 5.1 Account Types & Single Active Account Type Invariant
GARI enforces four canonical account types in `users.account_type`:
- `farmer` (Nông Hộ Cá Thể)
- `cooperative` (Hợp Tác Xã)
- `expert` (Chuyên Gia BVTV)
- `enterprise` (Doanh Nghiệp / Đơn Vị Dịch Vụ Nông Nghiệp)

---

## 6. SQLite Schema & User-Linked Business Tables

Inspection of [`database/disease_detector.db`](file:///d:/leaf-diseases-detector-main/database/disease_detector.db) revealed **84 total tables**, of which **59 tables link to internal `user_id` (`INTEGER`)**:

```
users (id INTEGER PRIMARY KEY AUTOINCREMENT)
  ├── farms (user_id)
  │    ├── farm_plots (user_id, farm_id)
  │    │    └── plot_timeline_events (user_id, plot_id)
  │    └── crops (user_id, farm_id)
  ├── diagnoses (user_id)
  │    └── diagnosis_feedbacks (user_id, diagnosis_id)
  ├── predictions (user_id)
  ├── cultivation_tasks (user_id, creator_user_id, assignee_user_id, completed_by_user_id)
  ├── organizations (owner_id)
  │    ├── organization_members (user_id, org_id)
  │    ├── organization_invitations (invited_by_user_id, accepted_by_user_id, ...)
  │    └── organization_audit_log (actor_user_id, org_id)
  ├── expert_cases (user_id)
  │    ├── expert_case_messages (sender_user_id, case_id)
  │    └── expert_case_activities (actor_user_id, case_id)
  ├── payment_orders (user_id)
  │    └── payment_attempts (initiated_by_user_id, order_id)
  ├── user_subscriptions (user_id)
  ├── user_quotas (user_id)
  ├── smart_alerts (assigned_user_id)
  ├── chat_history (user_id)
  └── community_posts (user_id)
       ├── community_comments (user_id, post_id)
       └── community_likes (user_id, post_id)
```

### 6.1 Critical Architectural Finding
Because **59 business tables** contain millions/thousands of relationships keyed on `INTEGER user_id`, changing the primary key of `users` to UUID would break dozens of queries and foreign keys.
**The Hybrid Architecture solves this cleanly:**
- Supabase Auth manages identity with `UUID` (`sub`).
- Supabase PostgreSQL maintains `gari_identity_links (supabase_uid UUID UNIQUE, sqlite_user_id INTEGER UNIQUE)`.
- FastAPI resolves `supabase_uid -> sqlite_user_id` once per request in `gari_auth.get_current_user`, seamlessly preserving all 59 existing SQLite business tables!

---

## 7. Edge Gateway & Vercel Configuration

1. **Configuration:** [`vercel.json`](file:///d:/leaf-diseases-detector-main/vercel.json)
   - Custom HTTP headers (nosniff, SAMEORIGIN, Strict Referrer Policy).
   - Clean URL rewrites mapping `/login` -> `/frontend2/login.html`, `/register` -> `/frontend2/register.html`, etc.
   - API wildcard routing: Vercel routes `/api/*` to the serverless entrypoint `api/[...path].js`.
2. **Gateway Script:** [`api/[...path].js`](file:///d:/leaf-diseases-detector-main/api/[...path].js)
   - SHA-256: `DF42964FE3C90844BC9F13CBADA1F877ED029E80F99D34F95E75B9A49ED91673`.
   - Acts strictly as a Fail-Closed reverse proxy with body buffering.
   - Forwards client headers including `Authorization` and `Cookie` to upstream FastAPI.
   - Contains zero token minting or account storage logic.

---

## 8. Summary of Discovery Findings

| Dimension | Current State | Target Supabase Hybrid State |
|---|---|---|
| **Identity Authority** | Fragmented: Firebase Auth SDK + local GARI PBKDF2 hash table | **Unified: Supabase Auth (Asymmetric JWT)** |
| **Profile Storage** | SQLite `users` table | **Supabase PostgreSQL `profiles` with RLS** |
| **Business Storage** | SQLite `database/disease_detector.db` (59 tables) | **Unchanged: SQLite (Preserves all business data)** |
| **Session Model** | Opaque random token in SQLite `user_sessions` | **Stateless Supabase JWT verified via JWKS** |
| **Identity Bridge** | None | **`gari_identity_links` (`supabase_uid` <-> `sqlite_user_id`)** |
| **Edge Gateway** | Fail-Closed reverse proxy (`api/[...path].js`) | **Unchanged: Pure reverse proxy** |

