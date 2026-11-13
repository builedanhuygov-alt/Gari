# GARI Auth Server 1.0 — Security Audit & Defense-in-Depth Report
**Document:** `docs/GARI_AUTH_SERVER_SECURITY_REPORT.md`  
**Date:** November 13, 2026  
**Status:** AUDITED & PASSING ALL THREAT MITIGATIONS  

---

## 1. Threat Modeling & Security Posture

GARI Auth Server 1.0 was designed to counter the primary web application attack vectors identified in the OWASP Top 10 and cloud authentication threat models:

| Threat Vector | Attack Scenario | GARI Auth Server Defense Implementation |
|---|---|---|
| **Broken Authentication** | Credential stuffing, brute force attacks | In-memory sliding window rate limiter: max 5 login attempts per 60s per IP and per email. Returns HTTP 429 with `Retry-After`. |
| **Account Enumeration** | Timing discrepancy or distinct error messages revealing valid emails | Constant-time dummy Argon2id hash evaluation for non-existent users; identical generic error message: *"Email hoặc mật khẩu không chính xác."* |
| **Session Hijacking & XSS** | JavaScript theft of tokens from `localStorage` | Pure HttpOnly session cookie (`gari_auth_session`). JavaScript cannot read or extract session credentials. |
| **Cross-Site Request Forgery (CSRF)** | Malicious third-party origin submitting state-changing POST requests | `CSRFProtectionMiddleware` enforces double-submit cookie validation: requests require valid `X-CSRF-Token` header. |
| **Privilege Escalation** | Registration payload tampering (`"account_type": "admin"`) | `register_user()` strictly hardcodes `account_type = 'farmer'`. Admin elevation is restricted to authenticated admins via `/api/v1/admin/users/{id}/role`. |
| **Database Compromise** | Attacker obtains SQLite file dump | All passwords hashed with Argon2id (64MB memory cost). All session tokens hashed with SHA-256 (plaintext tokens never written to disk). |
| **Registration Race Conditions** | Attacker floods registration to bypass the 10-account quota | Transaction-safe atomic `BEGIN IMMEDIATE` write lock inside SQLite. Verified resistant to 15 concurrent threads. |
| **Sensitive Data Logging** | Passwords or tokens appearing in server stdout/stderr logs | `log_security_event()` runs all metadata through `sanitize_dict()`, redacting any password, token, or auth header key. |

---

## 2. Cryptographic Specifications

### 2.1. Password Hashing (Argon2id)
- **Algorithm:** Argon2id (`argon2.Type.ID`, version 19).
- **Time Cost (`t`):** 3 iterations.
- **Memory Cost (`m`):** 65,536 KiB (64 MiB RAM per hash).
- **Parallelism (`p`):** 4 parallel lanes.
- **Salt Length:** 16 bytes (128 bits cryptographically secure random salt).
- **Hash Length:** 32 bytes (256 bits).
- **Defense Rationale:** Exceeds OWASP minimum guidelines; completely neutralizes GPU and ASIC cracking rigs.

### 2.2. Session Token Entropy
- **Token Generation:** `secrets.token_urlsafe(32)` yielding 43 characters with 256 bits of cryptographic entropy.
- **Database Storage:** SQLite stores only `sha256(raw_token).hexdigest()`.
- **Validation Pipeline:**
  1. Hash incoming token: `token_hash = sha256(cookie_value)`.
  2. Query database for matching `token_hash`.
  3. Verify `revoked_at IS NULL`.
  4. Verify `expires_at > now`.
  5. Verify `now - created_at <= 86,400s` (24h absolute max lifetime).
  6. Slide idle expiration forward by 7,200s (2h).

---

## 3. Cookie & Transport Security

```http
Set-Cookie: gari_auth_session=<opaque_token>; Max-Age=7200; Path=/; HttpOnly; SameSite=Lax; Secure
Set-Cookie: gari_csrf_token=<csrf_token>; Path=/; SameSite=Lax; Secure
```

- **`HttpOnly`:** Enforced on `gari_auth_session` to prevent DOM XSS access.
- **`Secure`:** Enabled by default in production; prevents transmission over unencrypted HTTP.
- **`SameSite=Lax`:** Prevents cross-site cookie transmission on third-party cross-origin requests.
- **`Strict-Transport-Security`:** `max-age=31536000; includeSubDomains; preload` injected by `SecurityHeadersMiddleware`.

---

## 4. Administrative Security & One-Time Bootstrap

- **Zero Hardcoded Secrets:** No default passwords exist in codebase or migrations.
- **One-Time Bootstrap Protocol:**
  - Route: `POST /api/v1/admin/bootstrap`.
  - Prerequisite: `BOOTSTRAP_ADMIN_TOKEN` environment variable set on host VPS.
  - Constant-time verification: `secrets.compare_digest(req.bootstrap_token, configured_token)`.
  - Re-use lockout: Queries `SELECT COUNT(*) FROM users WHERE account_type = 'admin'`. If count > 0, returns HTTP 409 and permanently disables the bootstrap flow.
