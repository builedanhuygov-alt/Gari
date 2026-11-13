<#
.SYNOPSIS
    GARI AgriTech AI Lab — Self-Hosted Backend Startup Script (Windows PowerShell)
.DESCRIPTION
    Safely starts the FastAPI backend (api_server:app) on port 8000 using the local virtual environment.
    Guarantees single-process execution, health probe verification, and PID file recording.
.EXAMPLE
    .\scripts\start_backend.ps1
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
$StartupLog = Join-Path $LogsDir "backend_startup.log"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> [1/4] GARI Backend Initialization (Port: $Port, Host: $HostAddress)..." -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# Check if port is already in use
$activePort = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($activePort) {
    Write-Host "[*] Port $Port is already in use by PID: $($activePort.OwningProcess)." -ForegroundColor Yellow
    Write-Host "[*] Probing existing service health..." -ForegroundColor Yellow
    try {
        $resp = Invoke-RestMethod -Uri "http://${HostAddress}:${Port}/health" -TimeoutSec 5 -ErrorAction Stop
        if ($resp.status -in @("healthy", "ok")) {
            Write-Host "[+] GARI Backend is ALREADY RUNNING and HEALTHY (PID: $($activePort.OwningProcess))!" -ForegroundColor Green
            # Update PID file
            $activePort.OwningProcess | Out-File -FilePath $PidFile -Encoding ascii
            exit 0
        }
    } catch {
        Write-Host "[!] Port $Port is occupied but service is not responding to /health." -ForegroundColor Red
        Write-Host "    Run .\scripts\stop_backend.ps1 to clear orphaned processes." -ForegroundColor Yellow
        exit 1
    }
}

# Locate Python virtual environment
$PythonBin = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $PythonBin)) {
    $PythonBin = (Get-Command python.exe -ErrorAction SilentlyContinue)?.Source
    if (!$PythonBin) {
        Write-Host "[-] FATAL: Python executable not found in .venv or system PATH." -ForegroundColor Red
        exit 1
    }
}

Write-Host ">> [2/4] Using Python Runtime: $PythonBin" -ForegroundColor Gray
Write-Host ">> [3/4] Launching FastAPI backend in background..." -ForegroundColor Cyan

$processArgs = @(
    "-m", "uvicorn",
    "api_server:app",
    "--host", $HostAddress,
    "--port", "$Port",
    "--timeout-keep-alive", "65"
)

$proc = Start-Process `
    -FilePath $PythonBin `
    -ArgumentList $processArgs `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput (Join-Path $LogsDir "backend_stdout.log") `
    -RedirectStandardError (Join-Path $LogsDir "backend_stderr.log") `
    -WindowStyle Hidden `
    -PassThru

# Record PID
$proc.Id | Out-File -FilePath $PidFile -Encoding ascii
Write-Host "[+] Process started with PID: $($proc.Id)" -ForegroundColor Green

# Health Probe Loop
Write-Host ">> [4/4] Awaiting API readiness probe..." -ForegroundColor Cyan
$elapsed = 0
$healthy = $false

while ($elapsed -lt $MaxWaitSeconds) {
    Start-Sleep -Seconds 2
    $elapsed += 2
    try {
        $resp = Invoke-RestMethod -Uri "http://${HostAddress}:${Port}/health" -TimeoutSec 3 -ErrorAction Stop
        if ($resp.status -in @("healthy", "ok")) {
            $healthy = $true
            break
        }
    } catch {
        Write-Host "    Still initializing ($elapsed/$MaxWaitSeconds s)..." -ForegroundColor Gray
    }
}

if ($healthy) {
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host "[+] SUCCESS: GARI Backend is HEALTHY and listening on http://${HostAddress}:${Port}" -ForegroundColor Green
    Write-Host "==================================================================" -ForegroundColor Green
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [START] PID: $($proc.Id) Port: $Port SUCCESS" | Out-File -FilePath $StartupLog -Append
    exit 0
} else {
    Write-Host "[-] ERROR: Backend failed to become healthy within $MaxWaitSeconds seconds." -ForegroundColor Red
    Write-Host "    Check logs at: $LogsDir\backend_stderr.log" -ForegroundColor Yellow
    exit 1
}

