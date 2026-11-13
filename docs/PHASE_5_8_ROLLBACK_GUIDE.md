# GARI AGRITECH AI LAB — PHASE 5.8 ROLLBACK GUIDE
**Date:** 2026-11-11  
**Scope:** Reverting Phase 5.8 code and/or restoring database state  
**Target Environment:** Localhost Windows 11 / Self-Hosted Backend

---

## 1. Pre-Flight Checkpoint Reference

Before applying Phase 5.8 remediations, a dedicated pre-flight snapshot was created:
- **Database Backup Path:** `database/backups/gari_db_backup_20261111_063050.db`
- **File Size:** 9.46 MB
- **SHA-256 Digest:** `34c86bacaa6265971a8e945c79e612e5c8e3aa7da954a242c23bc4fc69ad66fd`
- **Integrity Status:** Verified intact via `PRAGMA integrity_check;`

---

## 2. Code-Only Rollback (Git Working Tree)

If code changes in Phase 5.8 cause unforeseen client issues and need to be rolled back while preserving all production database records created in the interim:

### Step 1: Discard Code Edits
Run PowerShell:
```powershell
# Restore specific modified backend files to pre-remediation state
git checkout HEAD -- api_server.py gari_database.py gari_farm_management.py
```

### Step 2: Remove Remediation Test Suite (Optional)
```powershell
Remove-Item -Force .\tests\test_phase5_8_remediation.py
```

### Step 3: Restart Backend Service
Restart the background FastAPI process:
```powershell
# In PowerShell:
Stop-Process -Name python -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000
```

### Step 4: Run Health Check
```powershell
pwsh .\scripts\backend_healthcheck.ps1
```

---

## 3. Database Restoration (Emergency Recovery)

> [!CAUTION]
> Restoring a database snapshot will overwrite new diagnoses or records created after `2026-11-11 06:30:50 UTC`. Only perform this step if data corruption occurred.

### Step 1: Stop FastAPI Backend
Ensure no active connections hold write locks on `database/disease_detector.db`.
```powershell
Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force
```

### Step 2: Run the Automated Restore Script
GARI provides an automated, WAL-safe restore utility in `scripts/restore_db.py`:
```powershell
.\.venv\Scripts\python.exe .\scripts\restore_db.py database\backups\gari_db_backup_20261111_063050.db
```

The script will:
1. Verify the candidate backup's SHA-256 and SQLite integrity.
2. Create an emergency pre-restore safety snapshot of the live database.
3. Clean up stale `-wal` and `-shm` files.
4. Atomically copy the backup into place.
5. Execute `PRAGMA integrity_check` on the restored database.

### Step 3: Restart FastAPI & Cloudflare Tunnel
```powershell
# Restart backend
pwsh -File .\scripts\start_backend.ps1

# Verify tunnel connectivity
curl.exe -s https://gloves-specific-equation-amended.trycloudflare.com/health
```

