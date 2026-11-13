# GARI Auth Server 1.0 — Independent Authentication Service

A dedicated, lightweight, high-security authentication microservice built for the **GARI AgriTech AI Platform**.

Designed to operate 24/7 on a cloud VPS independently of the developer's Windows PC or inference worker.

---

## 1. Key Architectural Invariants

- **Zero Cloud SDK Dependencies:** No Supabase Auth, no Firebase Auth.
- **Argon2id Password Hashing:** OWASP recommended parameters (`m=65536`, `t=3`, `p=4`).
- **Cryptographic Session Tokens:** 256-bit random tokens stored strictly as SHA-256 hashes in SQLite.
- **Secure HttpOnly Cookies:** Credentials are never exposed to browser JavaScript or localStorage.
- **Double-Submit CSRF Protection:** Mutating requests validate `X-CSRF-Token` headers.
- **Hard Registration Capacity Limit:** Strictly capped at **10 accounts** in this evaluation phase, enforced atomically via SQLite transactions (`BEGIN IMMEDIATE`) to prevent concurrent race conditions.
- **Persistent Storage:** Operates on persistent volume with SQLite WAL journal mode and lock-free online backups.

---

## 2. API Endpoints

### Public & Authentication
- `GET  /api/v1/health` — Liveness health probe
- `GET  /api/v1/ready` — Readiness probe (database connectivity)
- `GET  /api/v1/auth/csrf` — Handshake to retrieve anti-CSRF token
- `POST /api/v1/auth/register` — Register new farmer account (strictly capped at 10)
- `POST /api/v1/auth/login` — Authenticate and receive HttpOnly session cookie
- `POST /api/v1/auth/logout` — Revoke active session in DB and clear cookie
- `GET  /api/v1/auth/me` — Retrieve authenticated user profile
- `POST /api/v1/auth/change-password` — Change password and revoke all other sessions
- `POST /api/v1/auth/revoke-sessions` — Revoke all other active sessions

### Administrative (Protected: `account_type == 'admin'`)
- `POST /api/v1/admin/bootstrap` — One-time initial admin setup using secret token
- `GET  /api/v1/admin/stats` — Operational statistics and capacity remaining
- `GET  /api/v1/admin/users` — Paginated user directory
- `GET  /api/v1/admin/users/{user_id}` — Detailed user account and session count
- `POST /api/v1/admin/users/{user_id}/status` — Activate/deactivate account
- `POST /api/v1/admin/users/{user_id}/role` — Change user role (farmer, expert, enterprise, admin)
- `POST /api/v1/admin/users/{user_id}/revoke-sessions` — Force revoke all sessions of a user
- `POST /api/v1/admin/registration/toggle` — Manually open or close public registration
- `GET  /api/v1/admin/security-events` — View sanitized security audit events

---

## 3. Running Locally

```bash
cd auth-server
pip install -r requirements.txt
export AUTH_ENV=development
export AUTH_PORT=8001
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## 4. Production Deployment with Docker & Caddy

```bash
cd auth-server
# Configure environment variables
export BOOTSTRAP_ADMIN_TOKEN="your_secure_random_bootstrap_token_min_16_chars"
docker compose up -d --build
```
