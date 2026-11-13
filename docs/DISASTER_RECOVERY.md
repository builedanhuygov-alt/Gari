# GARI AGRITECH AI LAB — DISASTER RECOVERY & DATA PROTECTION
## Business Continuity, Online WAL Backups & Restoration Runbook

**Document Version:** 1.0  
**Effective Date:** 2026-11-10  
**Database Engine:** SQLite 3 (WAL Mode — `PRAGMA journal_mode=WAL;`)  
**Production Database:** `database/disease_detector.db` (9.46 MB, 83 Tables)  
**Backup Directory:** `database/backups/`  
**Staging Directory:** `database/staging/`  
**Target RTO (Recovery Time Objective):** < 5 Minutes  
**Target RPO (Recovery Point Objective):** < 24 Hours (Nightly Automated) / On-Demand

---

## 1. Technical Context: SQLite WAL Concurrency & Data Safety

SQLite in WAL (Write-Ahead Logging) mode consists of three separate files:
1. `disease_detector.db`: Main database storage file.
2. `disease_detector.db-wal`: Write-Ahead Log journal holding recent uncommitted and committed transactions.
3. `disease_detector.db-shm`: Shared-memory index coordinating reader and writer threads.

> [!WARNING]
> **Danger of Raw File Copying:** Performing a standard operating system file copy (`copy`, `cp`, `Copy-Item`) on `disease_detector.db` while active writers exist produces torn pages, inconsistent schema states, and index corruption. Never use raw OS file copies for SQLite backups.

### The Online Backup API Solution (`sqlite3.backup()`)

GARI utilizes Python's native `sqlite3.backup()` API (`scripts/backup_sqlite.py`). This protocol:
- Locks the source database incrementally in short page bursts without starving active API readers.
- Flushes the WAL log and safely copies pages to the destination file.
- Guarantees complete ACID consistency of the snapshot.
- Emits a standalone, self-contained SQLite file that does not depend on external `-wal` or `-shm` journals.

---

## 2. Automated Backup System

### Architecture & Retention Policy

Backups are executed via `scripts/backup_database.ps1` (or scheduled via Windows Task Scheduler at 02:00 AM daily):

```
[FastAPI / Active DB]
         │
         ▼
[scripts/backup_sqlite.py]
         │
         ├─► Step 1: Pre-flight Disk Check (>= 500 MB free)
         ├─► Step 2: sqlite3.backup() online page-level streaming
         ├─► Step 3: Destination PRAGMA integrity_check
         ├─► Step 4: SHA256 checksum calculation & manifest recording
         └─► Step 5: Grandfather-Father-Son Retention Pruning
                    ├─ 7 Daily Snapshots
                    ├─ 4 Weekly Snapshots
                    └─ 3 Monthly Snapshots
```

### Manifest Format (`database/backups/manifest.json`)

Each backup is registered in a tamper-evident JSON manifest:
```json
{
  "backups": [
    {
      "filename": "gari_db_backup_20261110_150209.db",
      "timestamp_utc": "2026-11-10T15:02:09Z",
      "size_bytes": 9920512,
      "sha256": "0e158b84f9bc78ff0da27c9d46927d2c3df44923e2060010f368bb1d33e5ceca",
      "status": "verified"
    }
  ]
}
```

---

## 3. Disaster Recovery Restore Drill Protocol

To verify that backups are actionable and uncorrupted, GARI includes an automated **Staging Restore Drill** tool (`scripts/run_restore_drill.py`).

### Verification Steps

```
[Production DB] ──(online backup)──► [Backup Snapshot (.db)]
                                              │
                       ┌──────────────────────┘
                       ▼
          [Restore to Staging DB]
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
[PRAGMA integrity_check]   [83-Table Reconciliation]
   (Expect: "ok")              (Prod vs Staging)
                                       │
                                       ▼
                           [Sample Query Validation]
                         (Users, Diagnoses, Orgs, Farms)
```

### Live Drill Results (Verified 2026-11-10)

From `logs/restore_drill_report.json`:
- **Snapshot Size:** 9.46 MB (9,920,512 bytes).
- **Snapshot Creation Time:** **90.28 ms**.
- **Restore to Staging Time:** **105.0 ms**.
- **Total Recovery Time (RTO Demonstrated):** **< 1 Second**.
- **`PRAGMA integrity_check`:** **`ok`** (Zero errors).
- **Table Reconciliation:** **83 of 83 tables matched identically**:
  - `users`: 3,608 rows
  - `crops`: 3 rows
  - `diagnoses`: 599 rows
  - `farms`: 644 rows
  - `user_sessions`: 4,073 rows
  - `organizations`: 399 rows
  - `user_consents`: 6,867 rows
  - `plot_timeline_events`: 605 rows
- **Sample Business Queries:** Verified intact records for users, farms, diagnoses, and organizations.

---

## 4. Emergency Production Restoration Procedure

Follow this runbook step-by-step in the event of database corruption, accidental table deletion, or hardware recovery:

### Step 1: Halt Application Traffic
Stop the FastAPI backend immediately to prevent ongoing writes:
```powershell
pwsh .\scripts\stop_backend.ps1
```
Verify port 8000 is released:
```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

### Step 2: Take Forensic Safety Snapshot
Before making any modifications, preserve the damaged production database and its WAL files for post-mortem analysis:
```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$damagedDir = "database\forensics_$timestamp"
New-Item -ItemType Directory -Path $damagedDir -Force
Copy-Item "database\disease_detector.db*" -Destination $damagedDir
```

### Step 3: Select and Verify Backup Candidate
Identify the latest verified backup from `database\backups\manifest.json` or list directory:
```powershell
Get-ChildItem database\backups\*.db | Sort-Object CreationTime -Descending | Select-Object -First 3
```
Verify the candidate file integrity using Python:
```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c = sqlite3.connect('database/backups/gari_db_backup_YYYYMMDD_HHMMSS.db'); print(c.execute('PRAGMA integrity_check;').fetchall())"
```
*(Ensure the output prints `[('ok',)]`)*.

### Step 4: Clear Corrupted Database and Stale Journals
Purge the damaged database and any associated `-wal` and `-shm` files:
```powershell
Remove-Item "database\disease_detector.db" -Force -ErrorAction SilentlyContinue
Remove-Item "database\disease_detector.db-wal" -Force -ErrorAction SilentlyContinue
Remove-Item "database\disease_detector.db-shm" -Force -ErrorAction SilentlyContinue
```

### Step 5: Restore Clean Backup
Copy the verified backup to the active production location:
```powershell
Copy-Item "database\backups\gari_db_backup_YYYYMMDD_HHMMSS.db" -Destination "database\disease_detector.db"
```

### Step 6: Verify Production Integrity
Check that the newly placed production database is readable:
```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c = sqlite3.connect('database/disease_detector.db'); print('Integrity:', c.execute('PRAGMA integrity_check;').fetchall()[0][0]); print('Users count:', c.execute('SELECT COUNT(*) FROM users;').fetchone()[0])"
```

### Step 7: Restart Backend & Public Tunnel
Restart the FastAPI backend service:
```powershell
pwsh .\scripts\start_backend.ps1
```
Run comprehensive diagnostics:
```powershell
pwsh .\scripts\backend_healthcheck.ps1
```

### Step 8: Confirm Public Connectivity
Test the public health endpoint through the Cloudflare tunnel:
```powershell
pwsh .\scripts\gari_watchdog.ps1 -SingleCheck
```

---

## 5. Summary of Disaster Recovery Safeguards

| Safeguard | Implementation | Benefit |
| :--- | :--- | :--- |
| **No-Lock Online Backups** | `sqlite3.backup()` API in `backup_sqlite.py` | Eliminates torn-page corruption during WAL writes. |
| **Pre-Flight Disk Verification** | Disk free check (>= 500 MB) before backup | Prevents half-written backups due to full disk. |
| **Isolated Staging Drills** | `scripts/run_restore_drill.py` -> `staging/` | Proves backups work without endangering live database. |
| **Row-Level Reconciliation** | Automated counting across all 83 tables | Ensures zero data loss between backup and restore. |
| **Bounded Watchdog Retries** | Max 3 restarts per 10 minutes | Halts infinite crash loops if database fails to mount. |
| **Zero Cloud Egress** | Backups stored strictly locally in `database/backups/` | Complies with zero-cost and privacy regulations. |

