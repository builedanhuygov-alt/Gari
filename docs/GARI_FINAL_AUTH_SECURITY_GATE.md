# GARI AgriTech AI Lab — Final Auth Security Gate Report
## Edge Fallback, Token Revocation, and Single Source of Truth Audit

**Document ID:** GARI-GATE-AUTH-SEC-2026-02  
**Project:** GARI AgriTech AI Lab  
**Branch:** `gari-2.0-redesign`  
**Git Baseline:** `2318ee75`  
**Audit Date:** 2026-11-11  
**Gate Evaluation:** **REJECTED (FAIL) — CRITICAL SECURITY DEFECTS DETECTED**  
**Audit Mode:** READ-ONLY SECURITY AUDIT & SAFE MOCK VERIFICATION  

---

## 1. Executive Summary

This security audit evaluated the Edge Fallback architecture implemented in `api/[...path].js` and `frontend2/api/[...path].js`. While the previous remediation successfully eliminated Node.js stream deadlocks and client-side UI freezes, this deep architectural inspection identified **three critical security vulnerabilities** in the Edge Fallback mechanism:

1. **Authentication Bypass on Login (`VULN-EDGE-02` — CRITICAL):** When the backend is offline or slow (>6s), the Edge Gateway automatically issues authenticated session tokens for **any email address with any arbitrary password** via an unverified "dynamic recovery" routine.
2. **Ephemeral Phantom Registrations (`VULN-EDGE-01` — CRITICAL):** The Edge Gateway reports registration success (HTTP 200) without persisting the user in SQLite or Firebase. The account exists only in container RAM and is permanently destroyed upon container recycling.
3. **Non-Durable Distributed Revocation (`VULN-EDGE-03` — HIGH):** The token revocation blacklist (`revokedEdgeTokens`) exists solely in the process memory of an individual serverless container. It is not shared across Vercel instances and is erased on every cold start, allowing revoked tokens to be reused.
4. **Split-Brain Authentication Authority:** The Edge Gateway acts as an unverified, secondary token issuer. Tokens generated at the edge (`gari_edge_...`) are **completely unrecognized** by FastAPI and SQLite `user_sessions`, causing all subsequent application requests to fail with HTTP 401 Unauthorized.

**Gate Decision:** **DO NOT DEPLOY TO PRODUCTION** until the Edge Gateway is refactored to **fail closed** (HTTP 503) rather than minting synthetic authenticated sessions.

---

## 2. Edge Fallback Authentication Audit

### 2.1 Technical Analysis of `handleEdgeAuth()`

The fallback logic in `api/[...path].js` (and `frontend2/api/[...path].js`) was designed to provide graceful degradation when `VERCEL_BACKEND_API_URL` is unavailable or upstream requests exceed 6 seconds. However, the implementation violates the fundamental security principle of **Failing Closed**.

#### Specific Code Invasions:

**A. Unauthenticated Login Bypass (`api/[...path].js:250-256`):**
```javascript
// Dynamic recovery session for existing valid credentials
const uid = `usr_${crypto.createHash('md5').update(email).digest('hex').slice(0, 16)}`;
const fullName = email.split('@')[0];
const profile = buildUserProfile(uid, email, fullName, 'farmer');
const token = signToken({ uid, email, fullName, accountType: 'farmer', created: Date.now() });
return sendJson(res, 200, 'SUCCESS', 'Đăng nhập thành công.', { token, user: profile });
```
- **Vulnerability Mechanics:** If an incoming email is not found in the ephemeral `edgeUserStore`, the gateway **does not reject the request**. Instead, it synthesizes an account on the fly, hashes nothing, verifies no credentials, and issues an HMAC-signed token.
- **Exploitation Impact:** An attacker can submit any victim's email (e.g., `admin@gari.vn`) with password `"wrongpassword"` when the backend is offline or during high latency, and receive an authenticated token and profile.

**B. Ephemeral Phantom Registrations (`api/[...path].js:215-228`):**
```javascript
const salt = crypto.randomBytes(16).toString('hex');
const hash = crypto.pbkdf2Sync(password, salt, 10000, 64, 'sha512').toString('hex');
const uid = `usr_${crypto.randomBytes(8).toString('hex')}`;
const profile = buildUserProfile(uid, email, fullName, accountType, phone, province);
edgeUserStore.set(email, { uid, email, hash, salt, profile });

const token = signToken({ uid, email, fullName, accountType, created: Date.now() });
return sendJson(res, 200, 'SUCCESS', 'Đăng ký tài khoản thành công.', { token, user: profile });
```
- **Vulnerability Mechanics:** The user is saved only into `edgeUserStore = new Map()`.
- **Exploitation Impact:** When the serverless worker restarts or handles traffic in another Vercel region, the user's account ceases to exist. The user cannot log back in, and their data is lost.

**C. Unverified Firebase Token Exchange (`api/[...path].js:265-273`):**
```javascript
// Attempt decode JWT payload without verification in development fallback
try {
  const parts = idToken.split('.');
  if (parts.length === 3) {
    const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf-8'));
    if (payload.sub || payload.user_id) uid = payload.sub || payload.user_id;
    if (payload.email) email = payload.email;
    if (payload.name) name = payload.name;
  }
} catch (_) {}
```
- **Vulnerability Mechanics:** Decodes the unverified base64url payload of a JWT string without verifying the cryptographic signature against Google's public certificates. Anyone can forge a JWT payload with an arbitrary UID and email.

---

### 2.2 Answers to Specific Gate Inquiries

| Inquiry | Finding | Security Verdict |
|---|---|---|
| **1. Can Edge Gateway create an authenticated session when FastAPI is unavailable?** | **YES.** `handleEdgeAuth()` responds with HTTP 200 and issues `gari_edge_` HMAC tokens for both registration and login. | **VIOLATION (Fail-Open)** |
| **2. Can it issue a token without verifying credentials against authoritative auth?** | **YES.** Lines 250–256 issue a valid token for **any password** if the email is not in memory. | **CRITICAL DEFECT** |
| **3. Can a newly registered user receive a session without persistent creation?** | **YES.** User data is saved in container memory (`edgeUserStore`), never reaching SQLite or Firebase. | **CRITICAL DEFECT** |
| **4. Does the fallback create a different identity or authorization model?** | **YES.** Generates `usr_<hex8>` instead of integer database IDs, lacks organization memberships, and strips all verified roles. | **ARCHITECTURAL SPLIT** |
| **5. Are role, organization, and farm permissions independently enforced?** | **NO.** Hardcodes default `'farmer'` role with empty organizations. When passed to FastAPI, the backend rejects it completely. | **SYSTEM BREAKDOWN** |

---

## 3. Token Revocation Audit

### 3.1 Architectural Deficiencies of `revokedEdgeTokens`

The token revocation mechanism in `api/[...path].js` relies on an in-memory set:
```javascript
const revokedEdgeTokens = new Set();
```

#### Deficiencies Identified:

1. **Process-Bound Storage:** `revokedEdgeTokens` resides solely in the heap memory of the specific Node.js process executing the Lambda function.
2. **Multi-Instance Isolation in Vercel:** Vercel serverless functions scale across multiple independent instances and edge points of presence (PoPs). An instance in Singapore has zero visibility into the memory of an instance in Washington, D.C. or a sibling container in the same region.
3. **Cold Start Data Loss:** Serverless containers are ephemeral, shutting down after brief periods of inactivity. A cold start completely flushes `revokedEdgeTokens`.
4. **Replay Window:** A revoked token remains fully valid against any parallel container or newly initialized container until the 24-hour expiration window closes.
5. **No Authoritative State Verification:** `verifyToken()` only evaluates the HMAC signature and timestamp; it never checks SQLite `user_sessions` or Firebase token revocation status.

---

## 4. Single Source of Truth (SSOT) Analysis

### 4.1 Divergent Authentication Authorities

The system currently exhibits a dangerous dual-authority architecture:

```
                      [Farmer Browser]
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   [Authoritative Path]              [Rogue Edge Path]
   FastAPI + SQLite                  Vercel Edge Gateway
   - Table: users                    - In-memory: edgeUserStore
   - Table: user_sessions            - In-memory: revokedEdgeTokens
   - Token: 64-char Hex              - Token: gari_edge_<payload>.<hmac>
   - Password: PBKDF2/Salt           - Password: NO VERIFICATION (L250)
   - Scope: Farms, Orgs, Quotas      - Scope: None (Static stub)
```

### 4.2 Downstream Breakdown upon Upstream Recovery

When a user receives a `gari_edge_` token from the gateway fallback:
1. The frontend stores `localStorage.setItem('gari_token', 'gari_edge_...')`.
2. The frontend attempts to load data: `GET /api/farms`, `GET /api/diagnoses`, `POST /api/predict`.
3. The request reaches FastAPI backend:
   ```python
   # gari_auth.py:384-395
   cursor.execute(
       "SELECT s.token ... FROM user_sessions s WHERE s.token = ? AND s.expires_at > ?",
       (token, now_iso)
   )
   ```
4. SQLite contains no record of `gari_edge_...`.
5. FastAPI returns **HTTP 401 Unauthorized (`Could not validate credentials`)**.
6. **Result:** The user is told login succeeded, but every screen in the application immediately crashes, shows empty states, or throws authentication errors.

---

## 5. Empirical Security Verification

The vulnerabilities were proven via isolated mock execution ([`scratch/test_edge_auth_security_audit.js`](file:///d:/leaf-diseases-detector-main/scratch/test_edge_auth_security_audit.js)):

| Test Case | Scenario | Expected Secure Behavior | Actual Observed Gateway Behavior | Status |
|---|---|---|---|:---:|
| **Test 1** | Registration when backend is offline | Return HTTP 503 / 502 (Fail closed) | Returned **HTTP 200** with synthetic token | **FAIL (VULN-01)** |
| **Test 2** | Login with arbitrary wrong password | Return HTTP 401 or 503 | Returned **HTTP 200 SUCCESS** with valid token | **FAIL (VULN-02)** |
| **Test 3** | Logout when backend is offline | Clear client state, serverRevoked: false | Returned HTTP 200 at edge | **PASS (Acceptable)** |
| **Test 4** | Expired token verification (>24h) | Return HTTP 401 Unauthorized | Returned **HTTP 401** | **PASS** |
| **Test 5** | Token reuse across multiple containers | Revoked token rejected everywhere | Revoked token **ACCEPTED (HTTP 200)** on new instance | **FAIL (VULN-03)** |
| **Test 6** | Tampered HMAC signature | Return HTTP 401 Unauthorized | Returned **HTTP 401** | **PASS** |
| **Test 7** | Tampered payload claims (Privilege escalation)| Return HTTP 401 Unauthorized | Returned **HTTP 401** (Signature mismatch) | **PASS** |

---

## 6. Architectural Risk Register

| Risk ID | Title | Severity | Impact | Attack Vector / Trigger |
|---|---|:---:|---|---|
| **RSK-SEC-01** | Arbitrary Account Takeover on Edge Login | **CRITICAL** | Attacker impersonates any email address with zero credentials. | Attacker triggers or waits for backend latency/downtime and posts to `/api/auth/login`. |
| **RSK-SEC-02** | Phantom Account Data Loss | **CRITICAL** | Farmers lose newly registered accounts and associated farm data. | Farmers register while edge fallback is active; container restarts; account vanishes. |
| **RSK-SEC-03** | Persistent Session after Revocation | **HIGH** | Logged-out users remain authenticated on sibling edge nodes. | User logs out on Node A; attacker replays token on Node B before 24h expiration. |
| **RSK-SEC-04** | Total UI Failure Cascades | **HIGH** | Users experience broken dashboards and 401 errors on every page. | Any session minted at the edge is unconditionally rejected by backend SQLite. |

---

## 7. Recommended Remediation Plan (Fail-Closed Architecture)

To achieve enterprise-grade security and eliminate all split-brain vulnerabilities, the following architectural fixes must be executed:

### Phase 1: Eliminate Edge Auth Authority (Enforce Fail-Closed)
1. **Remove `handleEdgeAuth()` for Registration and Login:**
   - Remove `edgeUserStore`, `signToken()`, and fake password verification from `api/[...path].js` and `frontend2/api/[...path].js`.
   - When the backend upstream is unreachable, timed out (>6s), or unconfigured, the Edge Gateway must immediately return:
     ```json
     {
       "success": false,
       "code": "BACKEND_UNAVAILABLE",
       "detail": "Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát."
     }
     ```
     with **HTTP 503 Service Unavailable**.
2. **Never Mint Tokens at the Edge:**
   - The Edge Gateway must strictly act as a reverse proxy. Only the authoritative FastAPI backend (and SQLite `user_sessions`) or Firebase Auth may issue authentication tokens.

### Phase 2: Restrict Edge Gateway Responsibilities
The Edge Gateway should handle only three specific operations directly:
1. `GET /api/health`: Platform health status.
2. `GET /api/auth/firebase-config`: Public Firebase configuration for client SDK bootstrap.
3. CORS `OPTIONS` preflight requests.
All other requests (including all `/api/auth/*` and business APIs) must be proxied directly to the upstream FastAPI backend.

### Phase 3: Client Resilience on HTTP 503
Update `frontend2/firebase-client.js`:
- When receiving HTTP 503 or `BACKEND_UNAVAILABLE`, present a clear, graceful notice to the user:
  *"Hệ thống xác thực đang bảo trì kết nối. Vui lòng thử lại sau vài giây."*
- Ensure buttons are unblocked and no invalid token is stored in `localStorage`.

---

## 8. Final Gate Assessment & Acceptance Matrix

| Acceptance Criteria | Status | Notes |
|---|:---:|---|
| Backend unavailable cannot create an authenticated session | **FAIL** | Gateway currently returns HTTP 200 with `gari_edge_` token. |
| Registration cannot report success without persistent creation | **FAIL** | Gateway currently reports success using ephemeral `Map()`. |
| Revocation remains effective across gateway instances | **FAIL** | In-memory `Set` fails across Vercel instances and cold starts. |
| Expired and revoked tokens are rejected | **PARTIAL** | Expired tokens are rejected; revoked tokens can be replayed across containers. |
| No cross-tenant access | **PASS** | HMAC tampering is prevented, but arbitrary login exists in fallback. |
| No anonymous User 1 fallback | **FAIL** | Arbitrary login bypass generates unverified farmer profiles. |
| Logout never falsely reports server-side revocation | **PASS** | Client reports `serverRevoked: false` when backend unreachable. |

**OVERALL AUDIT VERDICT:** **REJECTED (GATE FAILED)**  
*Deployment to production is blocked until the Fail-Closed remediation is implemented and verified.*

