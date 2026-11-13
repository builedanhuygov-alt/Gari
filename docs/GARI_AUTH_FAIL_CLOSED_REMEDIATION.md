# GARI AgriTech AI Lab — Authentication Fail-Closed Architecture Remediation Report

**Document ID:** GARI-REMED-AUTH-FAILCLOSED-2026-01  
**Project:** GARI AgriTech AI Lab  
**Branch:** `gari-2.0-redesign`  
**Git Baseline:** `2318ee75`  
**Status:** **IMPLEMENTED & VERIFIED**  
**Remediation Scope:** Complete elimination of independent Edge Gateway authentication authority in favor of a strictly Fail-Closed reverse proxy model.  

---

## 1. Executive Summary

In response to the critical findings in `docs/GARI_FINAL_AUTH_SECURITY_GATE.md` (which rejected the previous Edge Fallback architecture due to arbitrary unauthenticated logins, phantom registrations, and non-durable in-memory token revocation), the Vercel Edge Gateway has undergone a complete **Fail-Closed Architectural Remediation**.

All independent authentication authority, ephemeral user stores (`edgeUserStore`), in-memory revocation sets (`revokedEdgeTokens`), HMAC token minters (`signToken`), and unverified login branches have been **permanently eliminated**.

The Edge Gateway now acts strictly as a secure, buffering reverse proxy:
- **Authentication SSOT:** FastAPI + SQLite (`users`, `user_sessions`) is the single authoritative source of truth.
- **Fail-Closed Behavior:** If the backend is unavailable, timed out (>6s), or unconfigured, the gateway immediately returns **HTTP 503 `BACKEND_UNAVAILABLE`**. It **never** issues synthetic tokens, fabricated profiles, or phantom registrations.
- **Client Resilience:** The frontend handles HTTP 503 gracefully, displaying a localized maintenance notification without leaving UI elements locked.

---

## 2. Exact Files & Functions Changed

### 2.1 Files Modified & Synchronized
1. `api/[...path].js` (Vercel Root Serverless Function)
2. `frontend2/api/[...path].js` (Synchronized Subtree Copy)
   - **SHA-256 Checksum:** `DF42964FE3C90844BC9F13CBADA1F877ED029E80F99D34F95E75B9A49ED91673` (100% byte-for-byte identical).

### 2.2 Eliminated Edge Authority Constructs
The following functions and variables were completely deleted:

| Removed Identifier | Previous Role | Security Hazard Eliminated |
|---|---|---|
| `SIGNING_SECRET` | Secret key used to sign edge HMAC tokens | Gateway no longer acts as an independent token issuer. |
| `revokedEdgeTokens` | In-memory `Set` of revoked tokens | Non-durable process-bound blacklist eliminated. |
| `edgeUserStore` | In-memory `Map` of ephemeral users | Phantom account creation without database persistence eliminated. |
| `signToken()` | Generated `gari_edge_` HMAC tokens | Eliminated rogue token generation. |
| `verifyToken()` | Validated `gari_edge_` tokens locally | Eliminated edge-only session validation. |
| `buildUserProfile()` | Synthesized stub user objects | Eliminated unverified default role assignments. |
| `handleEdgeAuth()` | Routines handling auth fallback | Replaced by `handleBackendUnavailable()`. |
| *Dynamic Recovery Session* | Unconditionally authenticated any email/password | Eliminated critical authentication bypass (`VULN-EDGE-02`). |

### 2.3 Preserved Non-Auth Gateway Capabilities
The following non-authenticating utilities were strictly preserved:
- `module.exports.config = { api: { bodyParser: false } }`: Preserves raw stream handling for Vercel.
- `readRawBody(req, limit = 1MB)`: Buffers authentication payloads before proxying to prevent request-stream consumption deadlocks.
- `OPTIONS` Handler: Responds to CORS preflights with HTTP 204 and authorized headers.
- `GET /api/auth/firebase-config`: Public client SDK configuration bootstrap (does not grant sessions).
- `GET /api/health`: Platform infrastructure health probe.

### 2.4 New Fail-Closed Handler: `handleBackendUnavailable()`
```javascript
function handleBackendUnavailable(pathStr, res) {
  // 1. Health check - public status only, does not grant authenticated access
  if (pathStr === 'health') {
    res.statusCode = 200;
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    res.setHeader('Access-Control-Allow-Origin', '*');
    return res.end(JSON.stringify({
      status: 'healthy',
      service: 'Gari AI Lab AgriTech Platform (Edge Gateway)',
      environment: process.env.NODE_ENV || 'production',
      version: '2.6.0',
      services: {
        gateway: 'healthy',
        backend_runtime: process.env.VERCEL_BACKEND_API_URL ? 'standby' : 'not_configured',
        firebase_admin: process.env.FIREBASE_PROJECT_ID ? 'configured' : 'standby'
      }
    }));
  }

  // 2. AI Inference routes when backend is not connected
  if (pathStr.startsWith('predict') || pathStr.startsWith('diagnose') || pathStr.includes('inference')) {
    return sendJson(
      res,
      503,
      'AI_INFERENCE_STANDBY',
      'Hệ thống chẩn đoán AI nông nghiệp đang trong trạng thái chờ hoặc đang nâng cấp mô hình. Vui lòng thử lại sau giây lát.'
    );
  }

  // 3. Fail-Closed for all authentication and application routes:
  // Never create unverified accounts, never issue synthetic tokens, never bypass credentials.
  return sendJson(
    res,
    503,
    'BACKEND_UNAVAILABLE',
    'Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì. Vui lòng thử lại sau giây lát.'
  );
}
```

---

## 3. Before vs. After Authentication Architecture

### 3.1 Before (Insecure Split-Brain Architecture)
```
[User Login Request]
        │
        ▼
[Vercel Edge Gateway] ──(Backend Offline / Timeout >6s)──┐
        │                                                ▼
        │ (Normal)                             [handleEdgeAuth]
        ▼                                                │
[FastAPI + SQLite]                             - No password check!
- Table: users                                 - No DB persistence!
- Table: user_sessions                         - In-memory edgeUserStore
- 64-char Hex Token                            - Token: gari_edge_...
        │                                                │
        ▼                                                ▼
[Persistent User Session]                      [Ephemeral Fake Session]
                                                         │
                                                         ▼
                                               [Downstream API Calls]
                                               FastAPI receives gari_edge_
                                               Returns HTTP 401 Unauthorized!
```

### 3.2 After (Strict Fail-Closed Architecture)
```
[User Login / Register Request]
        │
        ▼
[Vercel Edge Gateway]
        │
        ├── (Backend Healthy) ──> [FastAPI + SQLite (SSOT)]
        │                                 │
        │                                 ├── Verify Password / PBKDF2
        │                                 ├── Persist User in SQLite
        │                                 ├── Issue 64-char Hex Token in user_sessions
        │                                 └── Return HTTP 200 to Client
        │
        └── (Backend Offline / Timeout >6s)
                │
                ▼
        [Fail-Closed Enforcement]
        - NEVER issue synthetic token
        - NEVER bypass password verification
        - Immediately return HTTP 503 BACKEND_UNAVAILABLE
                │
                ▼
        [Farmer Client UI]
        - Catches HTTP 503 cleanly
        - Displays: "Máy chủ xác thực hiện chưa sẵn sàng hoặc đang bảo trì."
        - Unblocks submit button (finally block)
        - Leaves local storage clean
```

---

## 4. Authoritative Session Lifecycle (Single Source of Truth)

All session states are strictly managed by **FastAPI and SQLite**:

1. **Authentication:**
   - Handled in `api_server.py:login` -> `gari_auth.authenticate_user()`.
   - Validates email, password hash, account status, and rate limits.
2. **Session Creation:**
   - Handled in `gari_auth.create_session()`.
   - Generates cryptographically secure token via `secrets.token_hex(32)`.
   - Inserts record into `user_sessions` with `expires_at` (7 days or 30 days), client IP, and User-Agent.
3. **Session Validation:**
   - Handled in `gari_auth.validate_session()`.
   - Validates `WHERE s.token = ? AND s.expires_at > CURRENT_TIMESTAMP`.
   - Checks user moderation status and active flags.
4. **Session Revocation (Logout):**
   - Handled in `gari_auth.destroy_session()`.
   - Executes `DELETE FROM user_sessions WHERE token = ?`.
   - Distributed persistence: Because sessions exist in the shared database, revocation is immediate across all Vercel instances, regions, and cold starts.
   - Client returns `{ success: true, localCleared: true, serverRevoked: Boolean(res && res.ok) }`.

---

## 5. Verification Test Evidence

All 12 critical security scenarios were verified via [`tests/test_auth_fail_closed_gate.js`](file:///d:/leaf-diseases-detector-main/tests/test_auth_fail_closed_gate.js):

```
================================================================
GARI AUTHENTICATION FAIL-CLOSED SECURITY GATE (12 SCENARIOS)
================================================================

[SCENARIO 1] Backend offline during registration -> HTTP 503 (Fail-Closed)...
  -> PASS: Scenario 1 verified.

[SCENARIO 2] Backend offline during login -> HTTP 503 (Fail-Closed)...
  -> PASS: Scenario 2 verified.

[SCENARIO 3] Incorrect password rejection -> HTTP 401 from backend...
  -> PASS: Scenario 3 verified.

[SCENARIO 4] Valid password -> backend-issued session token...
  -> PASS: Scenario 4 verified.

[SCENARIO 5] Registration without database persistence -> never report success...
  -> PASS: Scenario 5 verified.

[SCENARIO 6] Logout while backend offline -> local logout succeeds, serverRevoked=false...
  -> PASS: Scenario 6 verified.

[SCENARIO 7] Revoked token rejection -> HTTP 401 from backend...
  -> PASS: Scenario 7 verified.

[SCENARIO 8] Expired token rejection -> HTTP 401 from backend...
  -> PASS: Scenario 8 verified.

[SCENARIO 9] Token issued by unauthorized issuer (e.g. gari_edge_) -> HTTP 401...
  -> PASS: Scenario 9 verified.

[SCENARIO 10] Cross-tenant access rejection -> HTTP 403 (Tenant isolation)...
  -> PASS: Scenario 10 verified.

[SCENARIO 11] Anonymous access to protected endpoints -> HTTP 401 Unauthorized...
  -> PASS: Scenario 11 verified.

[SCENARIO 12] Backend recovery after outage -> authentication restored...
  -> PASS: Scenario 12 verified.

================================================================
FAIL-CLOSED SECURITY GATE RESULT: 12/12 SCENARIOS PASSED (100%)
STATUS: VERIFIED SECURE & PRODUCTION READY
================================================================
```

### Full Regression Suite Inventory
- `tests/test_auth_fail_closed_gate.js`: **12/12 PASSED**
- `tests/test_auth_integration_gate.js`: **12/12 PASSED**
- `tests/test_safe_auth_reproduction.js`: **13/13 PASSED**
- `tests/test_phase5_8_remediation.py`: **9/9 PASSED**
- `tests/test_sprint6_1_dual_gate.py`: **10/10 PASSED**
- `tests/test_sprint6_2_evidence_foundation.py`: **13/13 PASSED**
- `tests/test_sprint6_2_staging_migration.py`: **13/13 PASSED**
- **Total Test Coverage:** **82 / 82 tests passed (100% success rate)**.

---

## 6. Residual Risk Assessment

| Risk ID | Risk Description | Severity | Probability | Residual Mitigation |
|---|---|:---:|:---:|---|
| **RSK-RES-01** | Backend Python process cold start causes temporary 503 | Low | Low | Upstream timeout is bounded to 6,000ms. If cold start exceeds 6s, user receives clean 503 and retry succeeds immediately once container is warm. |
| **RSK-RES-02** | Network blip during logout prevents server revocation | Low | Very Low | Local credentials are wiped immediately on client (`localCleared: true`), and UI accurately indicates server revocation was incomplete (`serverRevoked: false`). Token will naturally expire in SQLite after TTL. |

---

## 7. Conclusion & Next Steps

The critical authentication vulnerabilities have been fully eradicated. The Edge Gateway can no longer act as a rogue authentication authority, never fabricates tokens or identities, and fails closed with HTTP 503 when the backend is offline. The system is structurally sound for production cutover.

