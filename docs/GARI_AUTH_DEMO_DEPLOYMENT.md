# GARI Auth Server — Demo Edition Deployment Guide
## Architecture: Vercel Frontend + Render FastAPI + Neon Serverless PostgreSQL

**Date:** 2026-11-13  
**Target:** Startup Competition Demo (10 Registered Accounts Max)  
**Monthly Infrastructure Cost:** **$0.00** (Free Tier Only)  
**Requirements:** Zero VPS, Zero Custom Domain, Zero Paid Cloud Services  

---

## 1. Executive Summary & Architecture Overview

The **GARI Auth Server Demo Edition** decouples user authentication and profile management from the developer's physical Windows PC. It allows judges, evaluators, and early farmers to register, log in, browse dashboard features, and maintain persistent authenticated sessions 24/7 without requiring the local machine or Cloudflare Tunnel to be running.

```
+-------------------------------------------------------------------------------+
|                                USER BROWSER                                   |
|                          (Desktop / Tablet / Mobile)                          |
+-------------------------------------------------------------------------------+
          |                                                   |
          | 1. HTTP Requests                                  | 2. AI Inference
          |    (All /api/* calls)                             |    (Plant Diagnosis)
          v                                                   v
+-------------------------------+                   +---------------------------+
|        VERCEL GATEWAY         |                   |     WINDOWS AI WORKER     |
|   https://gari-team.vercel.app|                   |    (FastAPI Port 8000)    |
+-------------------------------+                   |     (On-Demand / Local)   |
  |                           |                     +---------------------------+
  | Proxies /api/auth/*       | Standby or Proxies                ^
  | and /api/v1/auth/*        | /api/predict to                   |
  v                           | AI Worker when online             |
+-------------------------+   +-----------------------------------+
|    RENDER WEB SERVICE   |
| (FastAPI Port 10000)    |
| Free Tier: Scale-to-Zero|
+-------------------------+
          |
          | TLS Encrypted (pool_pre_ping=True)
          v
+----------------------------------+
|    NEON SERVERLESS POSTGRESQL    |
| (Database: neondb, Free Tier)    |
| 10-Account Transaction Lock      |
+----------------------------------+
```

### Key Advantages for Demo & Competition
1. **$0.00 Total Cost:** Runs within 100% free-tier allowances on Vercel, Render, and Neon.
2. **1st-Party Cookie Architecture:** Vercel reverse-proxies `/api/auth/*` directly to Render, setting cookies on `gari-team.vercel.app`. This completely eliminates 3rd-party cookie blocking in Chrome Incognito, Safari, and Brave.
3. **No Domain Purchasing:** Uses free default platform subdomains (`*.onrender.com` and `*.vercel.app`).
4. **Data Isolation:** Uses an independent Neon database; the 3,611 legacy SQLite accounts in `database/disease_detector.db` remain 100% untouched and safe.

---

## 2. Component Provisioning Guide

### Step 1: Provision Free Neon PostgreSQL Database
1. Go to [https://neon.tech](https://neon.tech) and sign up for a free account.
2. Click **Create Project**:
   - **Project Name:** `gari-auth-demo`
   - **Postgres Version:** `16` (Default)
   - **Region:** `Singapore (ap-southeast-1)` or `US East (Ohio)`
3. Once created, copy your connection string from the Neon dashboard. It looks like:
   ```text
   postgresql://neondb_owner:npg_AbCd1234EfGh@ep-lively-star-123456-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```
   *(Note: The connection string automatically includes `sslmode=require`. GARI's configuration handles both `postgres://` and `postgresql://` URIs seamlessly).*

---

### Step 2: Deploy GARI Auth Server on Render
Render hosts the FastAPI service on its free tier.

#### Method A: Using Render Blueprint (`render.yaml`)
1. Log in to [https://render.com](https://render.com).
2. Click **New +** -> **Blueprint**.
3. Connect your GitHub repository: `dhuy170509/leaf-diseases-detector` (branch: `gari-2.0-redesign`).
4. Render automatically detects `render.yaml` with root directory `auth-server`.
5. Enter the `DATABASE_URL` environment variable with the Neon connection string from Step 1.
6. Click **Apply**.

#### Method B: Manual Web Service Setup
1. On Render, click **New +** -> **Web Service**.
2. Connect repository `dhuy170509/leaf-diseases-detector`.
3. Configure the service settings:
   - **Name:** `gari-auth-server`
   - **Region:** `Singapore` (or closest to Neon)
   - **Branch:** `gari-2.0-redesign`
   - **Root Directory:** `auth-server`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free`
4. Set **Health Check Path** to `/api/v1/health`.
5. Add Environment Variables:

| Key | Recommended Value | Purpose |
| :--- | :--- | :--- |
| `AUTH_ENV` | `production` | Enables production security and disables Swagger docs |
| `DATABASE_URL` | `postgresql://...neon.tech/neondb?sslmode=require` | Connection to Neon Postgres |
| `COOKIE_SECURE` | `true` | Enforces HTTPS on session cookies |
| `COOKIE_SAMESITE` | `lax` | Enables 1st-party cookie transfer via Vercel proxy |
| `CORS_ALLOWED_ORIGINS` | `https://gari-team.vercel.app,https://gari-team-fwwp1442f-bui11.vercel.app` | Allowed frontend origins |
| `MAX_REGISTRATION_ACCOUNTS` | `10` | Hard cap for competition demo accounts |
| `REGISTRATION_OPEN` | `true` | Opens public registration for competition |
| `BOOTSTRAP_ADMIN_TOKEN` | `<GENERATE_RANDOM_SECRET_64_CHARS>` | Secret key for bootstrapping host admin |

6. Click **Deploy Web Service**.
7. Note down your service URL once deployed (e.g., `https://gari-auth-server.onrender.com`).

---

### Step 3: Configure Vercel Edge Gateway
To connect your Vercel frontend to the Render Auth Server:

1. Open your Vercel Dashboard for `gari-team` (or Preview deployment).
2. Go to **Settings** -> **Environment Variables**.
3. Add the variable:
   - **Key:** `AUTH_SERVER_URL`
   - **Value:** `https://gari-auth-server.onrender.com` (Your Render service URL, without trailing slash)
   - **Environment:** `Preview` (and `Production` when authorized)
4. Redeploy the Vercel Preview or trigger a redeploy from Git.

---

## 3. Operational Characteristics on Free Tier

| Characteristic | Behavior | Mitigation Built Into GARI |
| :--- | :--- | :--- |
| **Render Cold Start** | Free Web Services spin down after 15 min of inactivity. Initial request takes ~25–40s to wake up. | Gateway has fail-safe error handling; frontend displays user-friendly retry message instead of crashing. |
| **Neon Auto-Suspend** | Compute scales to zero after 5 min idle; wakes in ~500ms–1s on new query. | SQLAlchemy configured with `pool_pre_ping=True` and `pool_recycle=300` to automatically reconnect severed sockets. |
| **10-Account Cap** | 11th registration attempt receives HTTP 403. | `SELECT pg_advisory_xact_lock(424242)` ensures concurrency safety across simultaneous requests. |
| **Windows PC Offline** | Physical PC can be turned off. | Authentication, registration, logout, and profile queries succeed 100% in cloud. AI inference returns structured 503 standby. |

---

## 4. Verification Checklist

1. **Render Health Check:**
   ```bash
   curl -i https://gari-auth-server.onrender.com/api/v1/health
   # Expected: HTTP 200 {"status":"healthy","service":"GARI Independent Auth Server","version":"1.0.0"}
   ```
2. **Neon DB Connectivity Check:**
   ```bash
   curl -i https://gari-auth-server.onrender.com/api/v1/ready
   # Expected: HTTP 200 {"status":"ready","database":"connected","registration_capacity_max":10}
   ```
3. **Vercel Proxied CSRF Handshake:**
   ```bash
   curl -i https://gari-team-preview.vercel.app/api/v1/auth/csrf
   # Expected: HTTP 200 with Set-Cookie: gari_csrf_token=...
   ```
4. **Browser E2E Test:**
   - Navigate to `https://gari-team-preview.vercel.app/frontend2/register.html`.
   - Create account `judge1@demo.gari.vn`.
   - Verify redirection to dashboard, refresh page, and observe active session.
