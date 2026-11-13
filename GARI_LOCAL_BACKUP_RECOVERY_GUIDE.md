# GARI — SELF-HOSTED DATABASE BACKUP & RECOVERY GUIDE
**Document ID:** `GARI_LOCAL_BACKUP_RECOVERY_GUIDE.md`  
**Database:** SQLite 3 (WAL Mode, `database/disease_detector.db`)  
**Engine:** Python `sqlite3.Connection.backup()` API  
**Date:** 2026-11-10  

---

## 1. Why Standard File Copies Corrupt Active Databases

When SQLite runs in Write-Ahead Logging (WAL) mode:
- Active transactions and pages reside in `disease_detector.db-wal`.
- Concurrently open connections share page index memory in `disease_detector.db-shm`.
- A naive file copy (`Copy-Item disease_detector.db ...`) copies only the base file at an arbitrary point in time, omitting uncheckpointed WAL pages and producing **corrupted, unreadable database headers**.

### The Online Backup Solution:
GARI utilizes [`deploy/oracle/backup_sqlite.py`](file:///d:/leaf-diseases-detector-main/deploy/oracle/backup_sqlite.py), which invokes Python's native `sqlite3.Connection.backup()` method. This page-by-page streaming protocol guarantees:
1. **Zero Downtime:** Live API writers and read queries are never blocked.
2. **Point-in-Time Consistency:** All active WAL frames are cleanly consolidated into the snapshot.
3. **Automated Verification:** Executes `PRAGMA integrity_check;` before accepting the snapshot.
4. **Cryptographic Checksum:** Calculates a SHA256 hash and writes a companion `.json` manifest.

---

## 2. Taking an On-Demand Backup

To trigger a backup manually from PowerShell:
```powershell
.\scripts\backup_database.ps1
```

**What Happens Automatically:**
1. Verifies that at least 500 MB of free disk space exists on the storage drive.
2. Creates a timestamped backup: `database/backups/gari_db_backup_YYYYMMDD_HHMMSS.db`.
3. Verifies internal page B-Tree integrity (`PRAGMA integrity_check = ok`).
4. Calculates SHA256 checksum and saves metadata: `gari_db_backup_YYYYMMDD_HHMMSS.json`.
5. Applies retention pruning (keeps last 7 daily, 4 weekly, 3 monthly backups).

**Example Output:**
```
[*] Free disk space on drive D: 120945 MB
>> Executing online WAL-safe backup engine...
2026-11-10 21:44:06 [INFO] Initiating online WAL-safe backup...
2026-11-10 21:44:06 [INFO] Verifying integrity of backup snapshot...
2026-11-10 21:44:06 [INFO] Backup verified OK: gari_db_backup_20261110_144406.db (9.46 MB, SHA256: 0e158b84...)
2026-11-10 21:44:06 [INFO] Retention complete. Kept 7 backups, pruned 1.
[+] SUCCESS: Database backup completed and verified intact.
```

---

## 3. Disaster Recovery & Restoration Runbook

If data corruption, accidental deletion, or faulty migration occurs, follow these strict recovery steps:

> [!CAUTION]
> **Safety Rule**: Never overwrite the active database without an emergency pre-restore snapshot. The recovery engine does this automatically.

### Step 1: Gracefully Stop the Backend
Stop the FastAPI service to ensure no active connections hold database file locks:
```powershell
.\scripts\stop_backend.ps1
```

### Step 2: List Available Verified Backups
```powershell
Get-ChildItem -Path database\backups -Filter "*.json" | ForEach-Object { Get-Content $_.FullName | ConvertFrom-Json } | Select-Object backup_file, created_at_utc, size_mb, sha256
```

### Step 3: Run the Disaster Recovery Engine
To restore from the latest verified backup:
```powershell
.\.venv\Scripts\python.exe deploy/oracle/restore_sqlite.py --latest
```

To restore from a specific snapshot:
```powershell
.\.venv\Scripts\python.exe deploy/oracle/restore_sqlite.py --backup-file database/backups/gari_db_backup_20261110_144406.db
```

**The Engine Executes 5 Protection Steps:**
1. Verifies the integrity of the candidate backup file (`PRAGMA integrity_check`).
2. Creates an emergency safety snapshot of the existing database: `database/backups/safety_pre_restore_TIMESTAMP.db`.
3. Deletes stale `disease_detector.db-wal` and `disease_detector.db-shm` journal files.
4. Atomically copies the verified backup over `database/disease_detector.db`.
5. Re-runs `PRAGMA integrity_check` on the active path to confirm clean restoration.

### Step 4: Restart Backend & Verify
```powershell
.\scripts\start_backend.ps1
.\scripts\backend_healthcheck.ps1
```

---

## 4. Setting Up Daily Automated Windows Backups (Task Scheduler)

To automate backups every night at 02:00 AM without manual intervention:

```powershell
$action = New-ScheduledTaskAction -Execute "pwsh.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PWD\scripts\backup_database.ps1`""
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "GARI_Nightly_Database_Backup" -Action $action -Trigger $trigger -Settings $settings -User "$env:USERNAME"
```

