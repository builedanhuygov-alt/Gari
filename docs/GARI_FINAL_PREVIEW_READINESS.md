# GARI AgriTech AI Lab — Final Login Security & Preview Readiness Audit

**Document ID:** GARI-AUDIT-FINAL-PREVIEW-READINESS-2026-02  
**Date:** 2026-11-11  
**Project:** `D:\leaf-diseases-detector-main`  
**Security Posture:** FAIL-CLOSED / ZERO BYPASS / ZERO PHP / IMMUTABLE PASSWORD INTEGRITY  

---

## 1. Executive Summary

This comprehensive audit evaluates the final state of authentication, session management, provider routing, edge gateway configuration, and AI inference readiness for the GARI AgriTech AI Lab platform.

Every security check has been verified through automated unit tests, backend integration tests, and live Playwright browser forensic tests.

| Audit Area | Scope | Verification Method | Status |
| :--- | :--- | :--- | :--- |
| **1. Session Tokens** | Token generation, validation, expiration, revocation | Unit test & database verification | **PASS** (Cryptographic Opaque Token / JWT dual-check) |
| **2. Provider Routing** | Firebase vs SQLite, Rule A–E enforcement | 10/10 scenario test suite (`test_login_provider_routing.js`) | **PASS** (Zero fallback bypass) |
| **3. Provider Lookup** | Data minimization, IP rate limiting, hash isolation | Endpoint flood test & schema audit | **PASS** (Rate limited at 60 req/min/IP; 429 enforced) |
| **4. Vercel Gateway** | Path routing, fail-closed behavior, localhost isolation | Source audit & environment gate review | **PASS** (No localhost fallback on Vercel) |
| **5. AI Inference** | `POST /api/predict`, auth enforcement, timeout compatibility | Live authenticated diagnosis execution | **PASS** (Auth enforced with 401; warm inference ~2s) |

---

## 2. Token Architecture & Verification

### 2.1. Token Type
FastAPI returns a **cryptographically secure opaque session token** (48 URL-safe characters) generated using Python's `secrets.token_urlsafe(36)`.
- *Format:* 36 cryptographically random bytes encoded into 48 base64url characters.
- *Dual Architecture:* The backend also natively supports standard asymmetric Supabase JWTs if Supabase authentication is enabled. If a token contains two dots (`.`), it is verified as a JWT; otherwise, it is validated against the active SQLite session store.

### 2.2. Generation and Persistence
- **Method:** `gari_auth.create_session(user_id, remember_me, ip_address, user_agent)`
- **Storage:** Persisted directly in SQLite table `user_sessions`:
  ```sql
  INSERT INTO user_sessions (token, user_id, expires_at, ip_address, user_agent)
  VALUES (?, ?, ?, ?, ?)
  ```
- **Lifespan:**
  - Standard session: 7 days (`SESSION_DURATION_DAYS = 7`).
  - Remember Me session: 30 days (`REMEMBER_ME_DURATION_DAYS = 30`).

### 2.3. Validation Flow
- **Dependency:** Every protected route utilizes `Depends(get_current_user)`.
- **Extraction:** Token is read from `Authorization: Bearer <token>` or `gari_session` HttpOnly cookie.
- **Verification Query:**
  ```sql
  SELECT s.token, s.expires_at, u.id, u.full_name, u.email, u.account_type, u.is_active, u.moderation_status
  FROM user_sessions s
  JOIN users u ON s.user_id = u.id
  WHERE s.token = ? AND s.expires_at > ?
  ```
- **Integrity Checks:**
  - Token must exist in `user_sessions`.
  - Current UTC time must be strictly less than `expires_at`.
  - User record must be active (`u.is_active == 1`).
  - User moderation status must not be banned (`u.moderation_status != 'banned'`).

### 2.4. Expiration and Revocation
- **Expiration:** Once `expires_at <= UTC NOW()`, `validate_session(token)` returns `None`, causing `get_current_user` to raise `HTTP 401 Unauthorized` (`Phiên đăng nhập đã hết hạn hoặc không hợp lệ`).
- **Revocation:** `POST /api/auth/logout` calls `destroy_session(token)`, executing:
  ```sql
  DELETE FROM user_sessions WHERE token = ?
  ```
  Immediately invalidating the session token across all subsequent requests.

### 2.5. Profile Endpoint Dependency
- The authoritative endpoint `GET /api/user/profile` strictly depends on `get_current_user`:
  ```python
  @app.get("/api/user/profile")
  @app.get("/api/auth/profile")
  async def get_user_profile_api(current_user: Dict[str, Any] = Depends(get_current_user)):
      return gari_auth.get_centralized_user_profile(current_user["id"])
  ```
  Unauthenticated or expired requests are rejected with 401 before any profile logic executes.

---

## 3. Provider Routing Verification

The system enforces strict, provider-aware login routing rules (Rules A – E) in `frontend2/firebase-client.js`:

```
                       [ Login Form Submission ]
                                  │
                                  ▼
                     Attempt Firebase Auth First
                                  │
         ┌────────────────────────┼────────────────────────┐
         │ (Success)              │ (auth/wrong-password)  │ (auth/user-not-found OR
         ▼                        ▼                        │  auth/invalid-credential)
 [Exchange Firebase Token]  [RULE C: REJECT]               ▼
         │                  "Email/mật khẩu sai"    POST /api/auth/provider-lookup
         ▼                                                 │
 [Issue Authoritative Session]             ┌───────────────┴───────────────┐
                                           │ exists: true                  │ exists: false OR
                                           │ provider: sqlite_only         │ provider != sqlite
                                           ▼                               ▼
                             POST /api/auth/login                  [RULE B: REJECT]
                             (FastAPI + SQLite bcrypt)             "Email/mật khẩu sai"
                                           │
                        ┌──────────────────┴──────────────────┐
                        │ 200 OK                              │ 401 Unauthorized / 503
                        ▼                                     ▼
             [Issue Authoritative JWT]                 [RULE D / E: REJECT]
             - Save to localStorage                   - Never issue token
             - Redirect to index.html                 - Show exact error banner
```

### 3.1. Verification Criteria
1. **Firebase Accounts:** Users registered with Firebase authenticate via Firebase SDK; their Firebase ID token is exchanged via `/api/auth/firebase-login` to issue an authoritative session.
2. **SQLite-only Accounts:** When Firebase returns `auth/invalid-credential` or `auth/user-not-found`, the client queries `/api/auth/provider-lookup`. Only if the account is confirmed `sqlite_only` or `hybrid` does it proceed to `/api/auth/login`.
3. **Wrong Password Rejection (Rule C & D):**
   - If Firebase returns `auth/wrong-password`, the client immediately throws `INVALID_CREDENTIALS` without calling SQLite.
   - If SQLite password verification fails, FastAPI returns `HTTP 401 Unauthorized`. Zero tokens or fallback identities are ever created.
4. **Unknown Accounts (Rule B):**
   - For an unknown email, `/api/auth/provider-lookup` returns `{"exists": false, "provider": "unknown"}`.
   - The client stops immediately and shows an error banner. No native login request is triggered.

---

## 4. Provider Lookup Endpoint Security Audit

### 4.1. Endpoint Specification (`POST /api/auth/provider-lookup`)
```python
class ProviderLookupPayload(BaseModel):
    email: str

_PROVIDER_LOOKUP_RATE_LIMIT: Dict[str, list] = {}
PROVIDER_LOOKUP_RATE_LIMIT_MAX = 60
PROVIDER_LOOKUP_RATE_LIMIT_WINDOW = 60  # Max 60 requests per 60 seconds per IP

@app.post("/api/auth/provider-lookup")
async def provider_lookup_endpoint(payload: ProviderLookupPayload, request: Request):
    client_ip = request.client.host if request.client else "0.0.0.0"
    now = time.time()
    attempts = _PROVIDER_LOOKUP_RATE_LIMIT.get(client_ip, [])
    attempts = [t for t in attempts if now - t < PROVIDER_LOOKUP_RATE_LIMIT_WINDOW]
    if len(attempts) >= PROVIDER_LOOKUP_RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu tra cứu từ địa chỉ IP này. Vui lòng thử lại sau 1 phút."
        )
    attempts.append(now)
    _PROVIDER_LOOKUP_RATE_LIMIT[client_ip] = attempts

    res = gari_auth.resolve_account_provider(payload.email)
    return {"success": True, **res}
```

### 4.2. Security Assessment
- **Data Minimization:** Response payload is strictly limited to:
  ```json
  { "success": true, "exists": true, "provider": "sqlite_only" }
  ```
  It does **not** reveal user IDs, full names, creation timestamps, roles, or organization data.
- **Hash Isolation:** The SQL query evaluates boolean presence only:
  ```python
  has_pwd = bool(row["password_hash"])
  has_fb = bool(row["firebase_uid"])
  ```
  The bcrypt `password_hash` is never serialized, logged, or exposed.
- **Rate Limiting:** Sliding-window rate limiting is actively enforced per client IP (60 requests / minute). Verified with 65 sequential requests:
  - Requests 1–60: `HTTP 200 OK`
  - Request 61+: `HTTP 429 Too Many Requests`
  - Client handles 429 with user-friendly notification: `"Bạn đã gửi quá nhiều yêu cầu xác thực. Vui lòng thử lại sau 1 phút."`

---

## 5. Vercel Configuration & Deployment Architecture

### 5.1. Gateway Files and Directory Alignment
- **Root Gateway:** `api/[...path].js` (configured at repository root).
- **Frontend Gateway Mirror:** `frontend2/api/[...path].js` (100% byte-for-byte identical, verified via binary diff).
- **Vercel Project Root:** `.vercel/project.json` confirms `rootDirectory: null` (repository root is project root).
- **Route Rewrites (`vercel.json`):**
  - `/` -> `/frontend2/index.html`
  - `/login` -> `/frontend2/login.html`
  - `/predict` -> `/frontend2/predict.html`
  - Dynamic API requests `/api/*` are handled by `api/[...path].js`.

### 5.2. Fail-Closed Gateway Logic (No Localhost Fallback in Cloud)
In `api/[...path].js`:
```javascript
const configuredOrigin = process.env.VERCEL_BACKEND_API_URL || 
  (process.env.NODE_ENV !== 'production' && !process.env.VERCEL_ENV ? 'http://127.0.0.1:8000' : '');

if (!configuredOrigin) {
  return handleBackendUnavailable(pathStr, res);
}
```

- When deployed on Vercel Preview or Production, Vercel automatically populates `process.env.VERCEL_ENV` (`"preview"` or `"production"`).
- Because `process.env.VERCEL_ENV` is set, `!process.env.VERCEL_ENV` evaluates to `false`.
- **Zero Localhost Fallback:** The gateway will **never** attempt to reach `http://127.0.0.1:8000` in any cloud environment.
- **Fail-Closed 503:** If `VERCEL_BACKEND_API_URL` is missing in the Vercel Dashboard, all `/api/auth/*` and protected routes cleanly return `HTTP 503 Service Unavailable` with `BACKEND_UNAVAILABLE` error message. No hangs, no token minting.

---

## 6. AI Inference Verification

### 6.1. Endpoint Testing (`POST /api/predict`)
Verified against the live FastAPI instance using `tests/fixtures/test_leaf.jpg`:

```text
[TEST 1] Unauthenticated request -> HTTP 401 Unauthorized (PASS)
[TEST 2] Invalid/tampered token   -> HTTP 401 Unauthorized (PASS)
[TEST 3] Authenticated request    -> HTTP 200 OK (PASS)
         Diagnosis success: True
         Output keys: ['success', 'status', 'validation_state', 'validation', 'mode', 'crop']
         Inference latency: 2.1 seconds
```

### 6.2. Authentication & Moderation Enforcement
- `/api/predict` strictly enforces `Depends(get_current_user)`.
- It executes `gari_moderation.enforce_user_moderation_access(current_user, required_feature="upload")` before allocating inference buffers.
- Banned or suspended accounts are immediately blocked from consuming AI compute.

### 6.3. Timeout Compatibility
- Upstream proxy timeout in `api/[...path].js` for general API calls is `15,000ms` (configurable via `VERCEL_BACKEND_TIMEOUT_MS`).
- Active model inference on CPU requires **2.1 seconds**, leaving a **12.9-second buffer** before any gateway timeout could occur.

---

## 7. Compliance Checklist

- [x] **Zero PHP:** Verified. No PHP files, scripts, test cases, or payloads exist in the workspace.
- [x] **Zero Defender Interference:** Windows Defender real-time protection was never touched; no exclusions were added.
- [x] **No Account or Database Deletion:** SQLite database `disease_detector.db` and all existing user records/hashes are intact.
- [x] **No Production Deployment:** `vercel --prod` was not executed.
- [x] **No Git Push:** No commits or pushes made to remote repository.

---

## 8. Final Verdict

### Status: **BLOCKED — CONFIGURATION MISSING**

#### Justification:
1. **Code & Security State:** **100% READY.** All 10/10 provider routing test scenarios pass, live Playwright browser login succeeds, rate limiting is active, token validation is tamper-proof, and AI inference is verified.
2. **Configuration Blocker:** The environment variable `VERCEL_BACKEND_API_URL` is currently **NOT configured** in the Vercel Preview environment.

#### Unblocking Steps for Operator:
To promote to **READY FOR CONTROLLED PREVIEW**:
1. Open the [Vercel Project Dashboard](https://vercel.com).
2. Navigate to **Project Settings** > **Environment Variables**.
3. Add the variable:
   - **Key:** `VERCEL_BACKEND_API_URL`
   - **Value:** Public URL of your running FastAPI backend (e.g., Cloudflare Tunnel endpoint `https://api.gari.vn` or Oracle VM IP/domain).
   - **Environment:** Select `Preview`.
4. Run the preview deployment:
   ```bash
   vercel
   ```
   *(Never use `vercel --prod`)*.

