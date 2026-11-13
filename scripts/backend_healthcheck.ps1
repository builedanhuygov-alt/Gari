<#
.SYNOPSIS
    GARI AgriTech AI Lab — Self-Hosted Backend Healthcheck Diagnostic Tool (Windows PowerShell)
.DESCRIPTION
    Comprehensive health inspection covering HTTP endpoints, latency, memory RSS, and SQLite WAL status.
.EXAMPLE
    .\scripts\backend_healthcheck.ps1
#>

param (
    [string]$TargetUrl = "http://127.0.0.1:8000",
    [int]$Port = 8000
)

$ErrorActionPreference = "SilentlyContinue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> GARI BACKEND HEALTHCHECK & DIAGNOSTICS ($TargetUrl)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$allPass = $true

# 1. TCP Port Listener
$activeConn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($activeConn) {
    $procId = $activeConn.OwningProcess
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    $memMb = [math]::Round($proc.WorkingSet64 / (1024 * 1024), 1)
    Write-Host "[+] TCP Port $Port : LISTENING (PID: $procId, Memory: $memMb MB)" -ForegroundColor Green
} else {
    Write-Host "[-] TCP Port $Port : NOT LISTENING" -ForegroundColor Red
    $allPass = $false
}

# 2. HTTP /health Probe
$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $healthResp = Invoke-RestMethod -Uri "$TargetUrl/health" -TimeoutSec 5 -ErrorAction Stop
    $sw.Stop()
    $latencyMs = $sw.ElapsedMilliseconds
    if ($healthResp.status -in @("healthy", "ok")) {
        Write-Host "[+] API /health : PASS ($latencyMs ms, Status: $($healthResp.status))" -ForegroundColor Green
        Write-Host "    Services: DB=$($healthResp.services.database) | AI=$($healthResp.services.ai_inference) | Runtime=$($healthResp.services.backend_runtime)" -ForegroundColor Gray
    } else {
        Write-Host "[!] API /health : DEGRADED (Status: $($healthResp.status))" -ForegroundColor Yellow
        $allPass = $false
    }
} catch {
    $sw.Stop()
    Write-Host "[-] API /health : FAILED ($($sw.ElapsedMilliseconds) ms) - $_" -ForegroundColor Red
    $allPass = $false
}

# 3. HTTP /ready Probe
try {
    $readyResp = Invoke-RestMethod -Uri "$TargetUrl/ready" -TimeoutSec 5 -ErrorAction Stop
    if ($readyResp.ready -eq $true) {
        Write-Host "[+] API /ready  : PASS (Database: $($readyResp.database), Storage: $($readyResp.models_storage))" -ForegroundColor Green
    } else {
        Write-Host "[!] API /ready  : NOT READY" -ForegroundColor Yellow
        $allPass = $false
    }
} catch {
    Write-Host "[-] API /ready  : FAILED - $_" -ForegroundColor Red
    $allPass = $false
}

# 4. SQLite Database & WAL Status
$dbFile = Join-Path $ProjectRoot "database\disease_detector.db"
$walFile = Join-Path $ProjectRoot "database\disease_detector.db-wal"
if (Test-Path $dbFile) {
    $dbSizeMb = [math]::Round((Get-Item $dbFile).Length / (1024 * 1024), 2)
    Write-Host "[+] SQLite DB   : EXISTS ($dbSizeMb MB at $dbFile)" -ForegroundColor Green
    if (Test-Path $walFile) {
        $walSizeKb = [math]::Round((Get-Item $walFile).Length / 1024, 1)
        Write-Host "[+] SQLite WAL  : ACTIVE ($walSizeKb KB journal at $walFile)" -ForegroundColor Green
    }
} else {
    Write-Host "[-] SQLite DB   : FILE NOT FOUND ($dbFile)" -ForegroundColor Red
    $allPass = $false
}

Write-Host "==================================================================" -ForegroundColor Cyan
if ($allPass) {
    Write-Host ">> OVERALL VERDICT: ALL HEALTH CHECKS PASSED (HEALTHY)" -ForegroundColor Green
    exit 0
} else {
    Write-Host ">> OVERALL VERDICT: ONE OR MORE CHECKS FAILED (DEGRADED)" -ForegroundColor Red
    exit 1
}

