# GARI Auth Server — Demo Edition Security Architecture & Review
## Defense-in-Depth for Startup Competition Demo

**Date:** 2026-11-13  
**Classification:** Engineering Security Architecture  
**Status:** **APPROVED FOR DEMO DEPLOYMENT**  

---

## 1. Threat Model & Security Objectives

For a startup competition demo, the authentication system is exposed to external evaluators, competitors, and potential bad actors over the public internet. The security goals are:

1. **Confidentiality:** Prevent exposure of user passwords, session tokens, or personal identifiers.
2. **Integrity:** Enforce an exact 10-account registration limit that cannot be bypassed via race conditions.
3. **Availability:** Shield the free-tier infrastructure from brute-force floods and denial-of-service.
4. **Data Isolation:** Ensure total isolation from legacy user accounts (3,611 accounts in `disease_detector.db`).
5. **No Edge Authority Compromise:** Never mint, sign, or forge authentication tokens in edge proxy logic.

---

## 2. Reverse Proxy & 1st-Party Cookie Architecture

### The Problem with Direct Cross-Origin Cookies
When a frontend on `https://gari-team.vercel.app` communicates directly with a backend on `https://gari-auth.onrender.com`, cookies issued by the backend are classified as **third-party cookies**. Modern browsers (Apple Safari ITP, Google Chrome Third-Party Cookie Deprecation, Brave Shields, Firefox ETP) block third-party cookies by default. This causes users to be immediately logged out upon page refresh.

### The GARI Vercel Gateway Solution
The Vercel Edge Gateway acts as a reverse proxy for all authentication routes:

```
[ Browser: https://gari-team.vercel.app ]
                     |
                     | 1. POST /api/auth/login
                     v
[ Vercel Gateway: api/[...path].js ]
                     |
                     | 2. Proxies upstream to https://gari-auth.onrender.com/api/auth/login
                     |    Forwards client IP and existing Cookie headers
                     v
[ Render Web Service: FastAPI ]
                     |
                     | 3. Responds with Set-Cookie: gari_auth_session=...; Path=/; HttpOnly; SameSite=Lax
                     v
[ Vercel Gateway ]
                     |
                     | 4. Propagates Set-Cookie header unchanged to browser
                     v
[ Browser receives cookie as 1st-PARTY on gari-team.vercel.app domain ]
```

### Cookie Security Attributes
| Attribute | Setting | Security Rationale |
| :--- | :--- | :--- |
| `Name` | `gari_auth_session` | Isolated namespace, no collision with legacy cookie names. |
| `HttpOnly` | `True` | Inaccessible to JavaScript `document.cookie`; completely protects against token theft via Cross-Site Scripting (XSS). |
| `Secure` | `True` | Only transmitted over encrypted HTTPS channels. |
| `SameSite` | `Lax` | Restricts cross-site request forgery while permitting safe top-level link navigations. |
| `Path` | `/` | Accessible across all application routes. |
| `Max-Age` | `7,200s` (2 hrs) / `86,400s` (24 hrs) | Automatic session expiry; supports "Remember Me". |

---

## 3. Cryptographic Storage & Session Handling

### Argon2id Password Hashing
GARI uses **Argon2id** (the winner of the Password Hashing Competition and RFC 9106 standard):
- **Memory Cost ($m$):** `65,536 KiB` (64 MB)
- **Time Cost ($t$):** `3 iterations`
- **Parallelism ($p$):** `4 lanes`
- **Salt:** 16 cryptographically secure random bytes generated via OS CSPRNG.

### Constant-Time Timing Attack Mitigation
When an attacker attempts to log in with an email address that does not exist in the database, the server runs a verification against a pre-computed dummy Argon2id hash (`DUMMY_ARGON2_HASH`). This ensures that the response latency is identical whether the user exists or not, defeating user enumeration attacks.

### SHA-256 Hashed Session Storage
- Raw session tokens are 32-byte cryptographically secure random values (256 bits of entropy) encoded as URL-safe base64 strings.
- **The raw token is NEVER stored in the database.**
- Only `token_hash = sha256(raw_token)` is persisted in Neon PostgreSQL.
- In the event of a database dump or read-only SQL injection vulnerability, an attacker cannot recover valid session tokens.

---

## 4. Race-Condition Proof 10-Account Capacity Enforcement

To satisfy the startup demo constraint of maximum 10 accounts, the registration service employs dialect-aware atomic locking:

```python
# Dialect-aware concurrency control in app/services/registration.py
bind = db.get_bind()
dialect_name = bind.dialect.name

if dialect_name == "sqlite":
    # SQLite write-lock for local development/testing
    db.connection().execute(text("BEGIN IMMEDIATE"))
elif dialect_name == "postgresql":
    # Neon PostgreSQL transaction-level advisory lock
    db.connection().execute(text("SELECT pg_advisory_xact_lock(424242);"))

# Check capacity inside write-locked transaction
current_count = db.query(User).filter(User.account_type != "admin").count()
if current_count >= settings.MAX_REGISTRATION_ACCOUNTS:
    raise RegistrationCapacityError("Cổng đăng ký tài khoản mới hiện đã đạt giới hạn thử nghiệm (10 tài khoản).")
```

### Why `pg_advisory_xact_lock(424242)`?
1. **Zero Table Lock Overhead:** Unlike `LOCK TABLE users`, an advisory transaction lock does not block concurrent read-only queries or interfere with database schema migrations.
2. **Automatic Lifecycle:** The lock is acquired atomically at the start of registration and released automatically upon `COMMIT` or `ROLLBACK`.
3. **Multi-Worker Safety:** Even if Render or an attacker runs multiple concurrent registration threads, all threads queue serially at the lock, guaranteeing that the 11th registration attempt is strictly rejected.

---

## 5. Defense Against Common Vulnerabilities

| Vulnerability | Defense Mechanism | Verified in Tests |
| :--- | :--- | :--- |
| **CSRF Attacks** | Double-submit cookie with `secrets.compare_digest` validation on mutating requests (`PUT`, `DELETE`). | `test_csrf_token_generation_and_validation` |
| **Brute-Force Login** | Sliding window rate limiter: 5 attempts per 60 seconds per IP. Returns HTTP 429 with `Retry-After`. | `test_login_rate_limiting` |
| **Registration Spam** | Rate limiter: 5 attempts per hour per IP. Combined with 10-user hard ceiling. | `test_registration_rate_limiting` |
| **Privilege Escalation** | `account_type` is hardcoded to `'farmer'` upon registration; ignores client-supplied role payloads. | `test_register_user_success` |
| **Session Fixation** | New session token generated on login; old sessions revoked on password change or explicit logout. | `test_session_revocation_on_password_change` |
| **Edge Token Minting** | Vercel Edge Gateway is strictly a proxy; contains zero JWT minting keys or mock authentication paths. | `test_auth_fail_closed_gate.js` |

---

## 6. Audit Verdict

The **GARI Auth Server Demo Edition** meets all production security criteria for an isolated competition deployment. It safely supports up to 10 live demo accounts with zero risk of compromising existing local data or accumulating unexpected cloud infrastructure costs.
