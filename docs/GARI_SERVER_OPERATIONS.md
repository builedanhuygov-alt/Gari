# GARI AgriTech AI Platform — Server Operations & Maintenance Manual

## 1. Daily Operator Runbook

This manual outlines standard operating procedures for managing the self-hosted Windows FastAPI backend, SQLite database, and Cloudflare Tunnel connection.

### Core Automation Scripts:
All operational tasks are managed via scripts located in `D:\leaf-diseases-detector-main\scripts\`:

| Script | Purpose | Command |
| :--- | :--- | :--- |
| **`start_gari_backend.ps1`** | Starts FastAPI server with AI pre-warming on `127.0.0.1:8000` | `pwsh -ExecutionPolicy Bypass -File .\scripts\start_gari_backend.ps1` |
| **`start_gari_tunnel.ps1`** | Launches Cloudflare Tunnel and registers public URL | `pwsh -ExecutionPolicy Bypass -File .\scripts\start_gari_tunnel.ps1` |
| **`check_gari_backend.ps1`** | Performs full health inspection (FastAPI, SQLite, Models, Tunnel) | `pwsh -ExecutionPolicy Bypass -File .\scripts\check_gari_backend.ps1` |

---

## 2. Standard Service Management

### Starting Services
1. Open PowerShell 7 (`pwsh`) in `D:\leaf-diseases-detector-main`.
2. Start the Backend:
   ```powershell
   pwsh -ExecutionPolicy Bypass -File .\scripts\start_gari_backend.ps1
   ```
3. Start the Tunnel:
   ```powershell
   pwsh -ExecutionPolicy Bypass -File .\scripts\start_gari_tunnel.ps1
   ```

### Checking Status & Health
Run the health inspector at any time:
```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\check_gari_backend.ps1
```
*Expected output shows green indicators for Port 8000, `/api/health`, `/api/ready`, SQLite DB, Model Store, and Tunnel Reachability.*

### Stopping Services
To gracefully terminate services:
```powershell
# Stop Cloudflare Tunnel
Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue

# Stop FastAPI Backend (replace PID if different)
$cfPid = Get-Content .\logs\cloudflared.pid -ErrorAction SilentlyContinue
if ($cfPid) { Stop-Process -Id $cfPid -Force -ErrorAction SilentlyContinue }
Get-Process -Name python | Where-Object { $_.CommandLine -match "api_server:app" } | Stop-Process -Force
```

---

## 3. Database Backup & Maintenance

The SQLite database is located at:
`D:\leaf-diseases-detector-main\database\disease_detector.db`

### Online Backup Procedure (Zero-Downtime)
SQLite supports safe online backup without stopping the FastAPI server:
```powershell
# Create automated backup directory
$backupDir = "D:\leaf-diseases-detector-main\backups"
if (!(Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir }

# Generate timestamped backup
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$targetBackup = Join-Path $backupDir "disease_detector_backup_$timestamp.db"

.venv\Scripts\python.exe -c "import sqlite3; src = sqlite3.connect('database/disease_detector.db'); dst = sqlite3.connect('$targetBackup'); src.backup(dst); dst.close(); src.close()"
Write-Host "Backup created: $targetBackup"
```

### Database Integrity Verification
```powershell
.venv\Scripts\python.exe -c "import sqlite3; c = sqlite3.connect('database/disease_detector.db'); print(c.execute('PRAGMA integrity_check;').fetchone()[0])"
```
*Must output `ok`.*

---

## 4. Log Management & Rotation

Log files are stored in `D:\leaf-diseases-detector-main\logs\`:

| Log File | Contents | Typical Size |
| :--- | :--- | :--- |
| `logs\uvicorn_backend.log` | FastAPI HTTP request logs, routing, and exceptions | < 50 MB |
| `logs\cloudflared.log` | Tunnel handshake events, edge connection status | < 10 MB |
| `logs\gari_tunnel_url.txt` | Current active public URL | Plaintext (1 line) |

### Manual Log Truncation (When logs exceed 100 MB)
```powershell
Clear-Content .\logs\uvicorn_backend.log
Clear-Content .\logs\cloudflared.log
```

---

## 5. Troubleshooting Runbook

### Issue A: Port 8000 is already in use
*Symptom:* `start_gari_backend.ps1` reports port 8000 busy or Uvicorn fails to bind.
*Remedy:*
```powershell
$procId = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess
if ($procId) {
    Write-Host "Killing process $procId on port 8000..."
    Stop-Process -Id $procId -Force
}
```

### Issue B: Tunnel shows 530 / 1033 Unreachable
*Symptom:* `check_gari_backend.ps1` reports status 530 or Error 1033.
*Root Cause:* The temporary Quick Tunnel expired, or local ISP DNS has not cached the new subdomain.
*Remedy:*
1. Run `.\scripts\start_gari_tunnel.ps1` to spin up a fresh connection.
2. Verify that `Resolve-DnsName -Server 1.1.1.1` resolves the domain.

### Issue C: AI Inference times out (>15s)
*Symptom:* Diagnosis requests return 504 on Preview.
*Root Cause:* PyTorch cold-start unloaded models from memory.
*Remedy:* Ensure `MODEL_PRELOAD_ENABLED=true` is set in the environment or restart with `.\scripts\start_gari_backend.ps1` which forces warm pre-loading.

