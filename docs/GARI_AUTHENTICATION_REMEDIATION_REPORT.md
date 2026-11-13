# GARI AGRITECH AI LAB — AUTHENTICATION REMEDIATION REPORT
## ROOT CAUSE DIAGNOSIS, DEFENSIVE REPRODUCTION & IMPLEMENTATION BLUEPRINT

- **Project:** GARI AgriTech AI Lab
- **Repository:** `D:\leaf-diseases-detector-main`
- **Branch:** `gari-2.0-redesign`
- **Baseline Commit:** `2318ee75`
- **Audit Date:** 2026-11-11
- **Status:** DIAGNOSIS COMPLETE & EMPIRICALLY CONFIRMED (READY FOR AUTHORIZED REMEDIATION)
- **Safety Mode:** STRICT DEFENSIVE COMPLIANCE (No PHP, No Webshells, Harmless Mock Data)

---

## 1. EXECUTIVE SUMMARY

The GARI production frontend deployed on Vercel (`https://gari-team.vercel.app`) experienced a hang during account registration, where the submit button remained permanently disabled displaying:
> `"Đang khởi tạo tài khoản..."`

A comprehensive, read-only forensic inspection was conducted across the full authentication chain:
1. Client form handlers (`frontend2/register.html`, `frontend2/login.html`)
2. Client auth orchestration engine (`frontend2/firebase-client.js`)
3. Vercel Serverless Edge Gateway (`api/[...path].js` and `frontend2/api/[...path].js`)
4. Backend API endpoints (`api_server.py`, `gari_auth.py`, `gari_firebase.py`)

### Primary Findings:
1. **The Root Cause is Confirmed:** The hang is caused by a **Node.js stream consumption deadlock** inside the Vercel Serverless Function (`api/[...path].js`) combined with **missing client-side fetch timeouts** in `frontend2/firebase-client.js`.
2. **Empirical Reproduction:** A clean, safe reproduction test suite (`tests/test_safe_auth_reproduction.js`) was constructed using synthetic in-memory streams and mock responses. The test empirically verified that calling `readBody(req)` after `req.pipe(upstream)` encounters an error **hangs indefinitely** because the stream has already emitted `'end'`.
3. **Security & Defender Isolation:** Zero malicious code exists in any authentication component. The Windows Defender alert (`Backdoor:PHP/Perhetshell.B!dha`) was triggered strictly by residual transcript text in `transcript_full.jsonl` from Phase 5.9 simulation prompts. No threat executed (`DidThreatExecute: False`), and all workspace source files are 100% clean.
4. **Zero Regression:** All existing security fixes (Phase 5.8 SEC-01 through SEC-05), Sprint 6.1 Dual-Gate inference tests (10/10), and Sprint 6.2 Evidence & Migration tests (26/26) remain intact and fully passing.

---

## 2. ROOT CAUSE EVIDENCE & TECHNICAL ANALYSIS

### Finding 1: Node.js Stream Consumption Deadlock in `api/[...path].js` (Primary Edge Cause)

**Location:** `api/[...path].js` (lines 367–401)
```javascript
  const transport = origin.protocol === 'https:' ? https : http;
  let upstream;
  try {
    upstream = transport.request({
      protocol: origin.protocol,
      hostname: origin.hostname,
      ...
      timeout: Number(process.env.VERCEL_BACKEND_TIMEOUT_MS || 90000),
    }, (upstreamResponse) => { ... });

    upstream.on('error', () => {
      if (isAuthOrHealthRoute) {
        return handleEdgeAuth(pathStr, req, res);
      }
      sendJson(res, 502, 'BACKEND_UNAVAILABLE', ...);
    });

    req.pipe(upstream);
  } catch (err) { ... }
```

**The Mechanism of Failure:**
1. When a client submits a registration request (`POST /api/auth/register`), Vercel routes the request to `api/[...path].js`.
2. Line 400 executes `req.pipe(upstream)` to proxy the request to `VERCEL_BACKEND_API_URL`.
3. As the request body streams to `upstream`, `req` emits `'data'` and ultimately `'end'`. In Node.js `stream.Readable`, once `'end'` is emitted, `readableEnded = true`.
4. When `VERCEL_BACKEND_API_URL` is offline, unreachable, or rejects the connection (e.g. ECONNREFUSED, DNS error, or timeout), `upstream` emits `'error'`.
5. The error listener activates line 390:
   `if (isAuthOrHealthRoute) return handleEdgeAuth(pathStr, req, res);`
6. Inside `handleEdgeAuth`:
   ```javascript
   if (pathStr === 'auth/register' && req.method === 'POST') {
     const body = await readBody(req);
     ...
   }
   ```
7. Inside `readBody(req)`:
   ```javascript
   function readBody(req) {
     return new Promise((resolve) => {
       let data = '';
       req.on('data', chunk => { ... });
       req.on('end', () => { resolve(...); });
       req.on('error', () => resolve({}));
     });
   }
   ```
8. **The Deadlock:** Because `req` has *already ended*, `req.on('end')` will **NEVER be called**. The Promise returned by `readBody(req)` stays permanently in the `pending` state.
9. As a result, `handleEdgeAuth` pauses indefinitely at `await readBody(req)`. No HTTP response is ever written, and no error status is sent back to the browser.
10. The browser's `fetch()` call awaits the response until Vercel's serverless function is forcefully terminated by Vercel after 10–15 seconds (Hobby plan limit) or browser default timeout (300s).

---

### Finding 2: Missing Client-Side Fetch Timeouts in `frontend2/firebase-client.js` (Primary Frontend Cause)

**Location:** `frontend2/firebase-client.js`
In the client authentication module, every asynchronous HTTP request is executed using bare `fetch()` without an `AbortSignal.timeout`:
- Line 36: `await fetch('/api/auth/firebase-config')`
- Line 160: `await fetch('/api/user/profile', ...)`
- Line 240: `await fetch('/api/auth/firebase-login', ...)`
- Line 304: `await fetch('/api/auth/login', ...)`
- Line 410: `await fetch('/api/auth/register', ...)`
- Line 457: `await fetch('/api/auth/forgot-password', ...)`
- Line 484: `await fetch('/api/auth/logout', ...)`

**Consequence on User Experience:**
- In `frontend2/register.html`:
  Line 343 disables the submit button and sets:
  `btnSubmit.disabled = true; btnSubmit.textContent = 'Đang khởi tạo tài khoản...';`
- If the backend or Vercel Edge proxy hangs due to Finding 1, the promise returned by `fetch()` never resolves or rejects.
- Because `catch(err)` is never triggered, the button remains permanently stuck at `'Đang khởi tạo tài khoản...'`.
- The user cannot re-click, cannot cancel, and receives zero feedback.

---

### Finding 3: Blocking Logout Execution

**Location:** `frontend2/firebase-client.js` (lines 481–496)
```javascript
async logout() {
    if (this.isFirebaseReady && this.firebaseAuth && this._fbMethods) {
        try { await this._fbMethods.signOut(this.firebaseAuth); } catch (e) {}
    }

    try {
        const token = this.idToken || localStorage.getItem('gari_token');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
        await fetch('/api/auth/logout', { ... });
    } catch (e) {}

    localStorage.removeItem('gari_token');
    localStorage.removeItem('gari_user');
    ...
}
```
**Consequence:**
If the network is degraded or `/api/auth/logout` hangs at the edge, `await fetch('/api/auth/logout')` blocks.
The cleanup code (`localStorage.removeItem('gari_token')`) is placed *after* the `await fetch()`. Therefore, the user is never logged out on the client until the long network timeout expires.

---

## 3. SAFE REPRODUCTION & TEST RESULTS

To prove these findings without risk to production or Defender triggers, a clean reproduction test suite was executed:
`tests/test_safe_auth_reproduction.js`

### Test Results Summary:

| Test ID | Objective | Mechanism | Result |
| :--- | :--- | :--- | :--- |
| **TEST-01** | Stream Consumption Deadlock | Pipe mock `Readable` stream to PassThrough, wait for end, then invoke `readBody()` | **CONFIRMED HANG (Indefinite pending promise)** |
| **TEST-02** | Stream Buffering Remediation | Buffer request body chunks into `Buffer` before proxying; reuse buffer on edge fallback | **PASSED (Zero hang, reliable multi-read)** |
| **TEST-03** | Client Fetch Timeout Protection | Wrap request in `AbortSignal.timeout(10000)`; verify immediate client error handling | **PASSED (Clean abort, user alert displayed)** |
| **TEST-04** | Non-blocking Logout Guarantee | Run network logout in `Promise.race` with 2s timeout; clear `localStorage` unconditionally | **PASSED (Client session cleared instantly)** |
| **TEST-05** | Auth Client Init Recovery | Simulate initial initialization failure; verify `_initPromise` reset enables subsequent success | **PASSED (Idempotent recovery verified)** |

**Suite Result:** **5/5 Tests Passed (100% Success)**

---

## 4. WINDOWS DEFENDER OBSERVATIONS & REMEDIATION

### Forensic Details:
- **Threat Detected:** `Backdoor:PHP/Perhetshell.B!dha` (ThreatID: `2147891542`)
- **Category:** Signature-based heuristic match.
- **Affected File:** `C:\Users\danhu\.gemini\antigravity\brain\003f99f4-631c-44e9-b8ab-c58475dc5fcc\.system_generated\logs\transcript_full.jsonl`
- **Execution Status:** `DidThreatExecute: False`, `IsActive: False`.
- **Reason for Quarantine Error (`-2142207965`):**
  Windows Defender attempted to quarantine `transcript_full.jsonl` while `agy.exe` held an active write lock during transcript log generation.
- **Corroborating Evidence:**
  Zero `.php`, `.phtml`, or webshell files exist anywhere in the GARI repository workspace. All workspace files modified on 2026-11-11 are standard project files (`.py`, `.js`, `.md`, `.json`, `.db`).

### Safe Compliance Rules Strictly Maintained:
- Zero PHP code generated.
- Zero webshell strings or exploit simulations introduced.
- Defender settings, exclusions, and real-time scanning remain untouched.
- All test fixtures use harmless mock records (`farmer_test@gari.local`).

---

## 5. PROPOSED CODE REMEDIATION (READY FOR APPROVAL)

### Change 1: `api/[...path].js` & `frontend2/api/[...path].js` (Buffer Request Stream)

**Before:**
`req.pipe(upstream)` consumes `req`, causing `readBody(req)` in `handleEdgeAuth()` to hang if `upstream` errors.

**Proposed Safe Implementation:**
```javascript
// Buffer the body once so it can be safely used for upstream proxying AND edge fallback
const bodyBuffer = await new Promise((resolve) => {
  const chunks = [];
  let size = 0;
  req.on('data', chunk => {
    size += chunk.length;
    if (size <= 5 * 1024 * 1024) chunks.push(chunk);
  });
  req.on('end', () => resolve(Buffer.concat(chunks)));
  req.on('error', () => resolve(Buffer.alloc(0)));
});

// Pass buffered body directly to upstream:
upstream.write(bodyBuffer);
upstream.end();

// On upstream error, pass bodyBuffer directly to handleEdgeAuth without re-reading stream:
upstream.on('error', () => {
  if (isAuthOrHealthRoute) {
    return handleEdgeAuth(pathStr, req, res, bodyBuffer);
  }
  sendJson(res, 502, 'BACKEND_UNAVAILABLE', ...);
});
```

---

### Change 2: `frontend2/firebase-client.js` (Client-Side Fetch Timeout & Safe Fetch Wrapper)

**Proposed Safe Implementation:**
Add a standardized `safeFetch(url, options, timeoutMs = 10000)` utility:
```javascript
async function safeFetch(url, options = {}, timeoutMs = 10000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        return response;
    } catch (err) {
        if (err.name === 'AbortError') {
            throw new GariAuthError(
                'NETWORK_TIMEOUT',
                'Kết nối đến máy chủ quá thời gian chờ (10s). Vui lòng thử lại.',
                'FETCH_TIMEOUT'
            );
        }
        throw err;
    } finally {
        clearTimeout(timeoutId);
    }
}
```
Replace all bare `fetch(...)` calls with `safeFetch(...)`.

---

### Change 3: `frontend2/firebase-client.js` (Non-Blocking Logout)

**Proposed Safe Implementation:**
```javascript
async logout() {
    // 1. Sign out Firebase
    if (this.isFirebaseReady && this.firebaseAuth && this._fbMethods) {
        try { await this._fbMethods.signOut(this.firebaseAuth); } catch (_) {}
    }

    // 2. Unconditionally clear local credentials FIRST so client session is never stuck
    localStorage.removeItem('gari_token');
    localStorage.removeItem('gari_user');
    localStorage.removeItem('gari_host_token');
    sessionStorage.clear();
    this.currentUser = null;
    this.idToken = null;
    this._notifyListeners(null);

    // 3. Notify backend asynchronously with a strict 2s timeout (best-effort)
    try {
        const token = localStorage.getItem('gari_token');
        if (token) {
            await safeFetch('/api/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                credentials: 'include'
            }, 2000);
        }
    } catch (_) {}
}
```

---

### Change 4: `frontend2/register.html` & `frontend2/login.html` (Button State Safety)

Ensure that in `register.html` and `login.html`, any error or timeout unconditionally restores the submit button:
```javascript
finally {
    btnSubmit.disabled = false;
    btnSubmit.textContent = 'Tạo tài khoản nông trại';
}
```

---

## 6. REGRESSION VERIFICATION MATRIX

Before recommending production deployment, all existing test suites were verified:

| Test Suite | Tests Run | Result | Notes |
| :--- | :--- | :--- | :--- |
| **Sprint 6.1 Dual-Gate Pipeline** (`tests/test_sprint6_1_dual_gate.py`) | 10 / 10 | **PASSED** | Optical quality + Leaf botanical gate + ConvNeXt inference verified |
| **Sprint 6.2 Evidence Foundation** (`tests/test_sprint6_2_evidence_foundation.py`) | 13 / 13 | **PASSED** | UUIDv7, reliability, provenance constraints verified |
| **Sprint 6.2 Staging Migration** (`tests/test_sprint6_2_staging_migration.py`) | 13 / 13 | **PASSED** | Schema validation, foreign keys, 3 rollback drills verified |
| **Safe Auth Reproduction Suite** (`tests/test_safe_auth_reproduction.js`) | 5 / 5 | **PASSED** | Stream buffer, fetch timeout, logout cleanup verified |

**Total Verified Tests: 41 / 41 PASSED (100%)**

---

## 7. ROLLBACK PLAN

If an issue arises after applying the proposed remediation:
1. **Frontend Rollback:**
   `git checkout -- frontend2/firebase-client.js frontend2/register.html frontend2/login.html`
2. **Gateway Rollback:**
   `git checkout -- api/[...path].js frontend2/api/[...path].js`
3. **Database Integrity:**
   Database is completely untouched (zero migrations or schema modifications involved).
4. **Vercel Deployment:**
   Re-deploy previous clean production commit via standard Vercel release management.

---

## 8. NEXT STEPS & RECOMMENDATION

1. Request approval to apply the minimal, defensive 4-point remediation to:
   - `api/[...path].js` & `frontend2/api/[...path].js`
   - `frontend2/firebase-client.js`
   - `frontend2/register.html` & `frontend2/login.html`
2. Run end-to-end browser tests verifying registration, login, logout, and simulated timeout recovery.
3. Proceed to Sprint 6.2 Phase 3 (Triage Decision Engine implementation).

