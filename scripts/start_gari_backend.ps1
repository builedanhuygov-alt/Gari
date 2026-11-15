<#
.SYNOPSIS
    GARI AgriTech AI Lab — Self-Hosted Windows Backend Startup Script
.DESCRIPTION
    Safely launches the FastAPI backend on 127.0.0.1:8000 with pre-warming enabled.
    Guarantees single-process execution, port collision checks, and health probe verification.
#>

param (
    [int]$Port = 8000,
    [string]$HostAddress = "127.0.0.1",
    [int]$MaxWaitSeconds = 30
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$LogsDir = Join-Path $ProjectRoot "logs"
if (!(Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }
$PidFile = Join-Path $LogsDir "gari_backend.pid"
$LogFile = Join-Path $LogsDir "gari_backend.log"
$ErrFile = Join-Path $LogsDir "gari_backend_err.log"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> [GARI BACKEND] Initializing Self-Hosted Server (${HostAddress}:${Port})..." -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Check if port 8000 is already in use
$activeConn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($activeConn) {
    $existingPid = $activeConn.OwningProcess
    Write-Host "[*] Port $Port is currently occupied by PID: $existingPid" -ForegroundColor Yellow
    Write-Host "[*] Probing existing service health..." -ForegroundColor Yellow
    try {
        $resp = Invoke-RestMethod -Uri "http://${HostAddress}:${Port}/api/health" -TimeoutSec 4 -ErrorAction Stop
        if ($resp.status -in @("healthy", "ok")) {
            Write-Host "[+] GARI Backend is ALREADY RUNNING and HEALTHY (PID: $existingPid)!" -ForegroundColor Green
            $existingPid | Out-File -FilePath $PidFile -Encoding ascii
            exit 0
        }
    } catch {
        Write-Host "[!] Port $Port is occupied but not responding to /api/health." -ForegroundColor Red
        Write-Host "    Terminate orphaned PID $existingPid or investigate before restarting." -ForegroundColor Yellow
        exit 1
    }
}

# 2. Locate Python executable in .venv
$PythonBin = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $PythonBin)) {
    $PythonBin = (Get-Command python.exe -ErrorAction SilentlyContinue)?.Source
    if (!$PythonBin) {
        Write-Host "[-] FATAL: Python binary not found in .venv or system PATH." -ForegroundColor Red
        exit 1
    }
}

# 3. Environment configuration for hardened Windows self-hosting
$env:APP_ENV = "production"
$env:HOST = $HostAddress
$env:PORT = "$Port"
$env:MODEL_PRELOAD_ENABLED = "true"
$env:MODEL_IDLE_TIMEOUT_SECONDS = "86400"
$env:INFERENCE_TIMEOUT_SECONDS = "60"
if (!$env:SESSION_SECRET -or $env:SESSION_SECRET.Length -lt 32) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $env:SESSION_SECRET = [System.BitConverter]::ToString($bytes) -replace '-'
}
if (!$env:JWT_SECRET -or $env:JWT_SECRET.Length -lt 32) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $env:JWT_SECRET = [System.BitConverter]::ToString($bytes) -replace '-'
}

Write-Host "[*] Launching Uvicorn server on ${HostAddress}:${Port} (Preload: Enabled)..." -ForegroundColor Cyan
$processArgs = "-m uvicorn api_server:app --host $HostAddress --port $Port --no-access-log"
$proc = Start-Process -FilePath $PythonBin -ArgumentList $processArgs -PassThru -NoNewWindow -RedirectStandardOutput $LogFile -RedirectStandardError $ErrFile

$proc.Id | Out-File -FilePath $PidFile -Encoding ascii
Write-Host "[*] Process launched with PID: $($proc.Id). Awaiting health readiness..." -ForegroundColor Cyan

# 4. Bounded polling health check
$startTime = Get-Date
$isHealthy = $false

while (((Get-Date) - $startTime).TotalSeconds -lt $MaxWaitSeconds) {
    Start-Sleep -Milliseconds 750
    try {
        $health = Invoke-RestMethod -Uri "http://${HostAddress}:${Port}/api/health" -TimeoutSec 2 -ErrorAction Stop
        if ($health.status -in @("healthy", "ok")) {
            $isHealthy = $true
            break
        }
    } catch {
        # Check if process unexpectedly died
        if ($proc.HasExited) {
            Write-Host "[-] Process $($proc.Id) terminated prematurely with code $($proc.ExitCode)." -ForegroundColor Red
            if (Test-Path $LogFile) { Get-Content $LogFile -Tail 20 }
            exit 1
        }
    }
}

if ($isHealthy) {
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host "[+] GARI BACKEND IS ONLINE AND READY (PID: $($proc.Id))!" -ForegroundColor Green
    Write-Host "    - Bind Address: http://${HostAddress}:${Port}" -ForegroundColor Gray
    Write-Host "    - Health Probe: http://${HostAddress}:${Port}/api/health" -ForegroundColor Gray
    Write-Host "    - PID File:     $PidFile" -ForegroundColor Gray
    Write-Host "==================================================================" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[-] Timeout waiting for backend readiness (${MaxWaitSeconds}s)." -ForegroundColor Red
    exit 1
}
