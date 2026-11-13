<#
.SYNOPSIS
    GARI AgriTech AI Lab — Self-Hosted SQLite Automated Backup Script (Windows PowerShell)
.DESCRIPTION
    Executes the WAL-safe online backup engine (deploy/oracle/backup_sqlite.py) using the local Python runtime.
    Validates free disk space, verifies SQLite integrity, computes SHA256 hashes, and applies retention rules.
.EXAMPLE
    .\scripts\backup_database.ps1
#>

param (
    [string]$DbPath = "database\disease_detector.db",
    [string]$BackupDir = "database\backups",
    [int]$MinFreeDiskMb = 500
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$LogsDir = Join-Path $ProjectRoot "logs"
if (!(Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }
$BackupLog = Join-Path $LogsDir "database_backup.log"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> GARI DATABASE AUTOMATED BACKUP ($DbPath)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Check disk capacity
$drive = (Get-Item $ProjectRoot).PSDrive
$freeMb = [math]::Round($drive.Free / (1024 * 1024), 0)
Write-Host "[*] Free disk space on drive $($drive.Name): $freeMb MB" -ForegroundColor Gray

if ($freeMb -lt $MinFreeDiskMb) {
    Write-Host "[-] ERROR: Insufficient disk space for backup ($freeMb MB available, $MinFreeDiskMb MB required)." -ForegroundColor Red
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [BACKUP_ERROR] Insufficient disk space ($freeMb MB free)" | Out-File -FilePath $BackupLog -Append
    exit 1
}

# 2. Locate Python binary
$PythonBin = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $PythonBin)) {
    $PythonBin = (Get-Command python.exe -ErrorAction SilentlyContinue)?.Source
}

if (!(Test-Path $PythonBin)) {
    Write-Host "[-] ERROR: Python binary not found." -ForegroundColor Red
    exit 1
}

# 3. Execute WAL-safe backup engine
$backupEngine = Join-Path $ProjectRoot "deploy\oracle\backup_sqlite.py"
Write-Host ">> Executing online WAL-safe backup engine..." -ForegroundColor Cyan

$process = Start-Process `
    -FilePath $PythonBin `
    -ArgumentList @($backupEngine, "--db-path", $DbPath, "--backup-dir", $BackupDir) `
    -NoNewWindow `
    -Wait `
    -PassThru

if ($process.ExitCode -eq 0) {
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host "[+] SUCCESS: Database backup completed and verified intact." -ForegroundColor Green
    Write-Host "==================================================================" -ForegroundColor Green
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [BACKUP_SUCCESS] Completed with exit code 0" | Out-File -FilePath $BackupLog -Append
    exit 0
} else {
    Write-Host "[-] ERROR: Backup engine failed with exit code $($process.ExitCode)." -ForegroundColor Red
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [BACKUP_FAIL] Engine exited with $($process.ExitCode)" | Out-File -FilePath $BackupLog -Append
    exit 1
}

