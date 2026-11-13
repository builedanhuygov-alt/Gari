# GARI AgriTech AI Lab — Supabase Auth Migration & Implementation Plan

**Document ID:** GARI-PLAN-SUPABASE-MIGRATION-2026-01  
**Project:** GARI AgriTech AI Lab  
**Scope:** Frontend Auth, FastAPI JWT Verification, Hybrid Identity Provisioning  
**Target Environment:** Preview Channel Only (Vercel Preview + Isolated Supabase Instance)  
**Strategy:** Hybrid Database Architecture + Identity Reset  
**Date:** 2026-11-11  
**Status:** DRAFT / PENDING CREDENTIAL STAGING  

---

## 1. Executive Summary & Migration Objectives

The purpose of this migration is to replace fragmented authentication mechanisms (Firebase Auth SDK v10 + native PBKDF2 session tables) with a unified, enterprise-grade authentication system powered by **Supabase Auth**.

### 1.1 Key Invariants
1. **Zero Downtime for Business Data:** SQLite database `database/disease_detector.db` (with its 59 user-linked tables) remains completely intact.
2. **Identity Reset Strategy (Preview):** In accordance with Phase 6, we do **not** attempt to convert old PBKDF2 password hashes into Supabase Auth. Preview users register cleanly into a fresh Supabase Auth pool. Legacy business records in SQLite are preserved, and automatic unverified linking by email alone is explicitly prohibited.
3. **Strict Fail-Closed Architecture:** FastAPI validates Supabase asymmetric JWTs via public JWKS. No fallback token minting or synthetic identity creation is permitted.
4. **Vercel Preview Isolation:** Deployment is targeted solely at Vercel Preview. `vercel --prod` is strictly forbidden.

---

## 2. Phase-by-Phase Execution Roadmap

```
[ Phase 0: Discovery ] (Completed)
        │
        ▼
[ Phase 1: Project Readiness & Credential Staging ]
        │  - Obtain SUPABASE_URL & SUPABASE_PUBLISHABLE_KEY
        │  - Configure backend SUPABASE_JWKS_URL
        │
        ▼
[ Phase 2: PostgreSQL Schema Deployment ]
        │  - Apply docs/GARI_SUPABASE_HYBRID_SCHEMA.md in Supabase SQL Editor
        │  - Verify RLS policies and signup trigger
        │
        ▼
[ Phase 3: Frontend Client Integration ]
        │  - Introduce frontend2/supabase-client.js (pinned @supabase/supabase-js v2.48.0 ESM)
        │  - Update login.html, register.html, forgot-password.html
        │  - Implement session auto-refresh and guaranteed error/timeout unlocking
        │
        ▼
[ Phase 4: FastAPI JWKS Verification Layer ]
        │  - Implement PyJWT / cryptography JWKS client in gari_auth.py
        │  - Verify signature, issuer, audience='authenticated', exp, and sub
        │  - Inject resolved SQLite user into request context
        │
        ▼
[ Phase 5: Hybrid Identity Provisioning State Machine ]
        │  - Implement idempotent /api/auth/supabase-sync endpoint
        │  - Map supabase_uid (UUID) to sqlite_user_id (INTEGER)
        │  - Handle network retries, pending verification, and partial failures
        │
        ▼
[ Phase 6: Legacy Account Reset & Isolation ]
        │  - Isolate SQLite legacy sessions from active Supabase sessions
        │  - Implement explicit account linking specification
        │
        ▼
[ Phase 7: Excising Legacy & Duplicate Authorities ]
        │  - Decommission Firebase client/server auth components
        │  - Remove PBKDF2 registration/login routes from active path
        │  - Verify pure Fail-Closed edge proxy behavior
        │
        ▼
[ Phase 8: Comprehensive Automated Security Suite ]
        │  - 20 security test scenarios (JWT tampering, expired tokens, RLS, cross-tenant)
        │
        ▼
[ Phase 9 & 10: Vercel Preview Deployment & Browser Acceptance ]
        │  - Deploy to isolated Preview URL
        │  - Live browser smoke testing (Register -> Verify -> Login -> Profile -> Logout)
```

---

## 3. Frontend Implementation Specification (Phase 3)

### 3.1 Pinned Supabase Client Library
* **Library:** `@supabase/supabase-js@2.48.0` (ESM via CDN `https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.48.0/+esm`).
* **Implementation File:** [`frontend2/supabase-client.js`](file:///d:/leaf-diseases-detector-main/frontend2/supabase-client.js).

### 3.2 Registration Flow (`frontend2/register.html`)
```javascript
// 1. Supabase Auth Signup
const { data, error } = await supabase.auth.signUp({
  email: email,
  password: password,
  options: {
    data: {
      full_name: name,
      phone: phone,
      province: province,
      account_type: accountType
    }
  }
});

// 2. Handle Email Confirmation Case
if (data?.user && !data?.session) {
  // Email confirmation is enabled in Supabase project
  showSuccessMessage('Đăng ký thành công! Vui lòng kiểm tra hộp thư email để xác nhận tài khoản trước khi đăng nhập.');
  return;
}

// 3. Post-Signup Provisioning Sync with Backend
if (data?.session?.access_token) {
  const syncRes = await safeFetch('/api/auth/supabase-sync', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${data.session.access_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      full_name: name,
      phone: phone,
      province: province,
      account_type: accountType
    })
  }, 10000);
}
```

### 3.3 Guaranteed State Recovery
* Every async call is race-bounded by `withTimeout(promise, 10000)`.
* Every form submission is wrapped in `try ... finally`, ensuring `submitBtn.disabled = false` and `isSubmitting = false` always execute.

---

## 4. Backend JWT Verification Specification (Phase 4)

### 4.1 JWKS In-Memory Cache with TTL
In [`gari_auth.py`](file:///d:/leaf-diseases-detector-main/gari_auth.py):
```python
import jwt
from jwt import PyJWKClient

# Configured from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")  # e.g. https://xyzcompany.supabase.co
SUPABASE_JWKS_URL = os.getenv("SUPABASE_JWKS_URL") or f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
EXPECTED_ISSUER = f"{SUPABASE_URL}/auth/v1"
EXPECTED_AUDIENCE = "authenticated"

# Cached JWK Client with bounded lifetime (cache_keys=True, max_cached_keys=16)
_jwks_client: Optional[PyJWKClient] = None

def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(SUPABASE_JWKS_URL, cache_keys=True, lifespan=3600)
    return _jwks_client

def verify_supabase_jwt(token: str) -> Dict[str, Any]:
    try:
        signing_key = get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            issuer=EXPECTED_ISSUER,
            audience=EXPECTED_AUDIENCE,
            options={"require": ["exp", "sub", "aud", "iss"]}
        )
        return payload
    except jwt.PyJWTError as exc:
        logger.warning("Supabase JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã xác thực không hợp lệ hoặc đã hết hạn."
        )
```

---

## 5. Hybrid Identity Provisioning State Machine (Phase 5)

When a valid Supabase JWT arrives at FastAPI, the system transitions through the following state machine:

```
        +-------------------------+
        |  Incoming Verified JWT  |
        +-------------------------+
                     │
                     ▼
        +-------------------------+
        | Query Identity Bridge   |
        | (gari_identity_links)   |
        +-------------------------+
          │                     │
   (Found)│                     │(Not Found)
          ▼                     ▼
+-------------------+   +------------------------------------+
| Return SQLite User|   | State: PENDING                     |
| Context           |   | - Create SQLite user record        |
+-------------------+   | - Insert gari_identity_links       |
                        | - Insert account_provisioning      |
                        +------------------------------------+
                                    │
                       (Success)    │    (Error)
                       ┌────────────┴────────────┐
                       ▼                         ▼
            +--------------------+    +--------------------+
            | State: ACTIVE      |    | State: FAILED      |
            | - Return Context   |    | - Log error_code   |
            +--------------------+    | - HTTP 500 / Retry |
                                      +--------------------+
```

### 5.1 Concurrency & Idempotency Safeguards
1. **Unique Constraints:** `supabase_uid` and `sqlite_user_id` are both `UNIQUE` in `gari_identity_links`.
2. **Upsert Semantics:** SQLite user insertion uses `ON CONFLICT(email) DO UPDATE` or email validation to prevent duplicate primary users.
3. **Failure Isolation:** If provisioning fails midway, `account_provisioning.status` remains `FAILED` with diagnostic `error_code`, allowing safe client retry without duplicate record creation.

---

## 6. Legacy Account Reset & Future Relinking Design (Phase 6)

### 6.1 Preview Policy
* Fresh user registration into the Supabase Auth pool.
* Old PBKDF2 password hashes remain stored in SQLite for existing data continuity, but cannot be used to log in via the new Supabase preview interface.
* **No Unverified Linking:** A user who registers `huy@example.com` in Supabase will NOT automatically inherit an old SQLite user with email `huy@example.com` unless verified.

### 6.2 Future Production Relinking Protocol (Specification)
When transitioning to production, verified accounts may be linked via:
1. User logs in with Supabase Auth (proving current email ownership via verification email).
2. User provides previous legacy password in an authenticated `/api/user/relink-legacy` endpoint.
3. Backend verifies old PBKDF2 hash on SQLite `users` record.
4. On match, updates `gari_identity_links (supabase_uid, sqlite_user_id)`.
5. Nullifies old `password_hash` in SQLite, permanently delegating authentication to Supabase.

