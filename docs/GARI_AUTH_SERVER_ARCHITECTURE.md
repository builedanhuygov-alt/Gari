# GARI Auth Server 1.0 — Architecture Specification
**Document:** `docs/GARI_AUTH_SERVER_ARCHITECTURE.md`  
**Date:** November 13, 2026  
**Status:** COMPLETED — READY FOR VPS DEPLOYMENT  
**Service:** `auth-server` (Standalone FastAPI Microservice)  

---

## 1. Executive Summary

GARI Auth Server 1.0 is an independent, lightweight, high-security authentication microservice designed to serve as the dedicated authentication authority for the GARI AgriTech AI Platform.

### Core Architectural Separation
```
+-------------------------------------------------------------+
|                  Vercel Edge & Web App                      |
|            https://gari-team.vercel.app/frontend2           |
+-------------------------------------------------------------+
                                |
             +------------------+------------------+
             | (Auth Requests)                     | (AI Inference)
             v                                     v
+---------------------------+       +-------------------------------+
|      GARI Auth Server     |       |    Windows On-Demand AI Worker |
| (Cloud VPS - Always Online|       |   (FastAPI / PyTorch / GPU)   |
|   SQLite WAL + Caddy)     |       |   (Only active during runs)   |
+---------------------------+       +-------------------------------+
```

The authentication service runs 24/7 on an independent Linux Cloud VPS. When the developer's Windows PC is turned off, sleep mode, or disconnected:
- Users can still register (up to the 10-account evaluation limit).
- Users can log in, log out, update their profiles, and view account statuses.
- Administrative users can manage accounts, revoke sessions, and monitor security events.
- The Windows PC remains strictly an on-demand inference worker, unburdened by session or identity authority.

---

## 2. Directory Structure

```
auth-server/
├── app/
│   ├── __init__.py
│   ├── config.py                 # Configuration via Pydantic Settings
│   ├── database.py               # SQLite WAL engine & foreign key enforcement
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py               # User table with Argon2id hash & role
│   │   ├── session.py            # Session table storing SHA-256 token hashes
│   │   └── security_event.py     # Sanitized audit trail
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py               # Register, Login, Logout, Session endpoints
│   │   ├── profile.py            # Profile retrieval and update
│   │   ├── admin.py              # Bootstrap, user management, stats, toggle
│   │   └── health.py             # Liveness & readiness probes
│   ├── services/
│   │   ├── __init__.py
│   │   ├── password.py           # Argon2id hasher (OWASP recommended parameters)
│   │   ├── session.py            # 256-bit cryptographic token lifecycle
│   │   ├── registration.py       # Transaction-safe 10-account capacity limiter
│   │   └── security_event.py     # Redacted event logger
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── security.py           # Strict HTTP security headers
│   │   ├── rate_limit.py         # Sliding window in-memory rate limiter
│   │   └── csrf.py               # Double-submit anti-CSRF protection
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py               # Pydantic v2 schemas with email normalization
│   │   └── admin.py              # Administrative schemas
│   └── main.py                   # FastAPI application factory
├── frontend-adapter/
│   └── gari-auth-service-client.js # Drop-in modern ES client using secure cookies
├── scripts/
│   ├── backup_db.py              # Online point-in-time SQLite backup with gzip
│   └── restore_db.py             # Atomic verification and restore script
├── tests/                        # 20 automated unit & concurrency tests
├── Dockerfile                    # Non-root container (appuser:10001)
├── docker-compose.yml            # Multi-service setup (Auth Server + Caddy)
├── Caddyfile                     # Automatic Let's Encrypt TLS reverse proxy
├── requirements.txt
└── README.md
```

---

## 3. Database Schema

All tables reside in a dedicated, isolated SQLite database (`gari_auth.db`) with `PRAGMA journal_mode = WAL;` and `PRAGMA foreign_keys = ON;`.

### 3.1. `users` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique user identifier |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | Lowercase normalized email |
| `password_hash` | VARCHAR(255) | NOT NULL | Argon2id password hash |
| `full_name` | VARCHAR(255) | NOT NULL | User display name |
| `account_type` | VARCHAR(50) | NOT NULL, DEFAULT 'farmer' | Role (`farmer`, `expert`, `enterprise`, `admin`) |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | Account state |
| `is_verified` | BOOLEAN | NOT NULL, DEFAULT TRUE | Verification status |
| `created_at` | DATETIME | NOT NULL | Registration timestamp (UTC) |
| `updated_at` | DATETIME | NOT NULL | Last update timestamp (UTC) |

### 3.2. `sessions` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Session record ID |
| `user_id` | INTEGER | FK -> `users.id` (CASCADE) | User reference |
| `token_hash` | VARCHAR(64) | UNIQUE, NOT NULL, INDEX | SHA-256 hash of raw session token |
| `expires_at` | DATETIME | NOT NULL, INDEX | Expiration timestamp |
| `created_at` | DATETIME | NOT NULL | Creation timestamp |
| `last_seen_at` | DATETIME | NOT NULL | Last user activity timestamp |
| `revoked_at` | DATETIME | NULL, INDEX | Revocation timestamp if invalidated |

### 3.3. `security_events` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Event ID |
| `event_type` | VARCHAR(100) | NOT NULL, INDEX | Event code (`LOGIN_SUCCESS`, `REGISTER_CAPACITY_REJECTED`, etc.) |
| `user_id` | INTEGER | FK -> `users.id` (SET NULL) | Target user if applicable |
| `ip_address` | VARCHAR(100) | NULL | Request source IP address |
| `user_agent` | VARCHAR(500) | NULL | Client browser User-Agent |
| `created_at` | DATETIME | NOT NULL, INDEX | Audit timestamp (UTC) |
| `sanitized_metadata` | TEXT | NULL | JSON string with all credentials redacted |

---

## 4. Key Security Controls

1. **Argon2id Hashing:** High-memory (64MB) and compute-bound parameters prevent GPU-accelerated cracking.
2. **Never Storing Raw Session Tokens:** Tokens are 256-bit cryptographically secure strings (`secrets.token_urlsafe(32)`). SQLite stores only `sha256(raw_token)`. Database compromise does not expose active sessions.
3. **HttpOnly & SameSite Cookies:** Session cookies cannot be read by malicious frontend scripts, defending against Cross-Site Scripting (XSS) session theft.
4. **Double-Submit Anti-CSRF Protection:** State-changing requests must include `X-CSRF-Token` header matching the client's `gari_csrf_token` cookie.
5. **Atomic Registration Capacity Limit:** Enforced inside a SQLite `BEGIN IMMEDIATE` transaction to eliminate race conditions. Capped at 10 accounts.
6. **Constant-Time Verification:** Dummy Argon2id hash computed when an unknown email is submitted, eliminating timing-based account enumeration attacks.
