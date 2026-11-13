# GARI AGRITECH AI LAB — OPERATIONS GUIDE
## Daily Management, Maintenance & Public Access Runbook

**Audience:** System Administrators, DevOps Engineers, Lab Operators  
**Environment:** Windows 11 Enterprise (Self-Hosted Backend) + Vercel (Production Frontend)  
**Cost Target:** **$0.00 / month**

---

## 1. Quick Command Reference

All scripts are located in `scripts/` and run natively in PowerShell (pwsh):

| Action | Command | Purpose |
| :--- | :--- | :--- |
| **Start Backend** | `pwsh .\scripts\start_backend.ps1` | Launches FastAPI on `127.0.0.1:8000` with PID tracking. |
| **Stop Backend** | `pwsh .\scripts\stop_backend.ps1` | Gracefully shuts down FastAPI and frees port 8000. |
| **Restart Backend** | `pwsh .\scripts\restart_backend.ps1` | Performs clean stop -> start with health check. |
| **Health Check** | `pwsh .\scripts\backend_healthcheck.ps1` | Diagnostics for port 8000, `/health`, `/ready`, RAM, WAL. |
| **Run Watchdog** | `pwsh .\scripts\gari_watchdog.ps1 -SingleCheck` | Verifies services, restarts if crashed, checks loop bounds. |
| **Database Backup** | `pwsh .\scripts\backup_database.ps1` | Creates WAL-safe SQLite snapshot with SHA256 checksum. |
| **DR Restore Drill** | `.\.venv\Scripts\python.exe scripts/run_restore_drill.py` | Restores snapshot to staging and tests integrity & queries. |
| **Monitor Metrics** | `pwsh .\scripts\gari_monitor.ps1` | Logs CPU, RAM, Disk, Latency to `logs/local_monitoring.jsonl`. |
| **Install Auto-Start** | `pwsh .\scripts\install_windows_tasks.ps1` | Registers Windows Task Scheduler triggers for user logon. |
| **Uninstall Auto-Start**| `pwsh .\scripts\uninstall_windows_tasks.ps1` | Cleans up registered Task Scheduler entries. |

---

## 2. Managing Public Access (Cloudflare Tunnel)

GARI uses Cloudflare Tunnel to expose the local FastAPI backend (`127.0.0.1:8000`) securely over HTTPS to the Vercel frontend without opening router firewall ports (no NAT/port-forwarding required).

### A. Quick Tunnel (Current Active Mode)

- **Launch Command:**
  ```powershell
  cloudflared.exe tunnel --url http://127.0.0.1:8000
  ```
- **Finding the Active URL:**
  The tunnel URL is printed in standard error output or stored in `logs/cloudflared.log`:
  ```
  INF +--------------------------------------------------------------------------------------------+
  INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
  INF |  https://xxxx-xxxx-xxxx.trycloudflare.com                                                 |
  INF +--------------------------------------------------------------------------------------------+
  ```
- **Updating the URL on Vercel:**
  Because the Vercel frontend uses the serverless Edge Proxy (`api/[...path].js`), **zero code changes are required** when the tunnel URL changes.
  
  **Method 1: Via Vercel Web Dashboard (Recommended)**
  1. Open [https://vercel.com/dashboard](https://vercel.com/dashboard).
  2. Select the `gari-team` project -> **Settings** -> **Environment Variables**.
  3. Locate `VERCEL_BACKEND_API_URL` -> Click **Edit**.
  4. Paste the new URL (e.g. `https://xxxx-xxxx-xxxx.trycloudflare.com`) for **Production, Preview, Development**.
  5. Click **Save**. The proxy will automatically use the new target for incoming requests.

  **Method 2: Via Vercel CLI**
  ```powershell
  vercel env rm VERCEL_BACKEND_API_URL production -y
  vercel env add VERCEL_BACKEND_API_URL production
  # When prompted, paste the new URL
  ```

### B. Named Tunnel (Future Permanent Mode)

If a custom domain (e.g. `gari-ai.org`) is later registered with Cloudflare DNS:
1. Log in to Cloudflare CLI:
   ```powershell
   cloudflared tunnel login
   ```
2. Create named tunnel:
   ```powershell
   cloudflared tunnel create gari-prod
   ```
3. Route DNS to the tunnel:
   ```powershell
   cloudflared tunnel route dns gari-prod api.gari-ai.org
   ```
4. Run the tunnel:
   ```powershell
   cloudflared tunnel run gari-prod
   ```
5. Set `VERCEL_BACKEND_API_URL` to `https://api.gari-ai.org` once. It will **never need to be changed again**.

---

## 3. Windows Task Scheduler Automation

The system can automatically start and supervise GARI upon user login without requiring administrative service passwords.

### Installation

Run in an interactive PowerShell window:
```powershell
pwsh .\scripts\install_windows_tasks.ps1
```

This creates two user-level scheduled tasks:
1. **`GARI_AutoStart_Watchdog`**:
   - Trigger: `AtLogon` of the current user.
   - Action: Executes `scripts/gari_watchdog.ps1` in the background.
   - Supervisor logic:
     - Detects if FastAPI is already listening on port 8000; avoids duplicate launches.
     - Detects if `cloudflared.exe` is already running.
     - Recovers failed services automatically with bounded retry limits (max 3 restarts per 10 minutes to prevent crash loops).
2. **`GARI_Nightly_Database_Backup`**:
   - Trigger: Daily at `02:00 AM`.
   - Action: Executes `scripts/backup_database.ps1`.
   - Performs WAL-safe online snapshot with SHA256 checksum, verifying disk space (>= 500 MB) and enforcing a 7-day retention policy.

### Uninstallation

To remove the scheduled tasks cleanly:
```powershell
pwsh .\scripts\uninstall_windows_tasks.ps1
```

---

## 4. Model Lifecycle & Memory Management

GARI features an on-demand AI inference model lifecycle to operate smoothly on desktop workstations with limited RAM:

- **Lazy Loading:** PyTorch weights are only loaded into RAM when a prediction request arrives.
- **LRU Cache Limit:** Maximum **3 models** cached concurrently in RAM.
- **Idle Eviction:** Models inactive for more than **300 seconds (5 minutes)** are automatically unloaded from memory, triggering Python garbage collection (`gc.collect()`).
- **RAM Protection:** If host physical memory exceeds 90% utilization, idle models are proactively purged before loading new ones. If physical memory exceeds 98.5% or available RAM is below 200 MB, incoming load requests are gracefully rejected with HTTP 503 to prevent OS freezing.

---

## 5. Routine Troubleshooting Runbook

### Issue 1: Port 8000 Conflict (`Address already in use`)
- **Symptom:** `uvicorn` fails to start; error log shows `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`.
- **Resolution:**
  ```powershell
  # Find PID occupying port 8000
  Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess, State
  # Stop backend cleanly using helper
  pwsh .\scripts\stop_backend.ps1
  ```

### Issue 2: Frontend Shows "May chu GARI AI tam thoi gian doan" (502 / 503)
- **Symptom:** Web UI displays red warning banner stating the backend is offline.
- **Diagnostics:**
  1. Check if backend is alive locally:
     ```powershell
     pwsh .\scripts\backend_healthcheck.ps1
     ```
  2. If local backend is healthy, check if Cloudflare tunnel is running:
     ```powershell
     Get-Process cloudflared -ErrorAction SilentlyContinue
     ```
  3. If tunnel restarted, check if the tunnel URL changed:
     - Compare active tunnel URL with `VERCEL_BACKEND_API_URL` on Vercel.
     - Update Vercel environment variable as shown in Section 2.

### Issue 3: Watchdog Paused (Too Many Restarts)
- **Symptom:** Log file `logs/watchdog_restarts.json` indicates `restart_limit_exceeded = true`.
- **Cause:** Backend crashed more than 3 times within 10 minutes (safety threshold to prevent infinite CPU/disk loop).
- **Resolution:**
  1. Inspect `logs/gari_backend.log` for the root exception (e.g. corrupt model file, DB lock, port conflict).
  2. Fix the underlying root cause.
  3. Clear restart history:
     ```powershell
     Remove-Item logs/watchdog_restarts.json -ErrorAction SilentlyContinue
     ```
  4. Restart manually:
     ```powershell
     pwsh .\scripts\restart_backend.ps1
     ```

### Issue 4: Disk Space Warning During Backup
- **Symptom:** `backup_database.ps1` warns that available disk space is under 500 MB.
- **Resolution:**
  1. Check backup directory `database/backups/`.
  2. Prune old `.db` files:
     ```powershell
     Get-ChildItem database/backups/*.db | Sort-Object CreationTime -Descending | Select-Object -Skip 7 | Remove-Item
     ```

---

## 6. Security & Operational Rules

1. **Never commit `.env` or credentials:** Cloudflare tunnel credentials, Vercel tokens, and database passwords must remain in local environment variables.
2. **Never restore directly over active production database:** Always perform restore drills into `database/staging/` first to verify `PRAGMA integrity_check` before copying over live databases.
3. **Always use online backup API:** Never use raw file copy on `database/disease_detector.db` while FastAPI is writing; use `scripts/backup_sqlite.py` which executes the WAL-safe SQLite backup protocol.

