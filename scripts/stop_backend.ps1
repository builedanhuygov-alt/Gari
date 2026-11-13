<#
.SYNOPSIS
    GARI AgriTech AI Lab — Self-Hosted Backend Shutdown Script (Windows PowerShell)
.DESCRIPTION
    Safely terminates the FastAPI backend listening on port 8000 and clears runtime PID files.
.EXAMPLE
    .\scripts\stop_backend.ps1
#>

param (
    [int]$Port = 8000,
    [int]$GraceTimeoutSeconds = 10
)

$ErrorActionPreference = "SilentlyContinue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$PidFile = Join-Path $ProjectRoot "logs\gari_backend.pid"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> [1/3] GARI Backend Termination (Port: $Port)..." -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$pidsToKill = @()

# 1. Read PID from file if exists
if (Test-Path $PidFile) {
    $savedPid = Get-Content $PidFile -ErrorAction SilentlyContinue | Out-String
    if ($savedPid) {
        $savedPidInt = [int]$savedPid.Trim()
        if (Get-Process -Id $savedPidInt -ErrorAction SilentlyContinue) {
            $pidsToKill += $savedPidInt
        }
    }
}

# 2. Check process listening on port
$activePort = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($activePort) {
    $pidsToKill += $activePort.OwningProcess
}

$uniquePids = $pidsToKill | Select-Object -Unique

if ($uniquePids.Count -eq 0) {
    Write-Host "[*] No active GARI backend process found listening on port $Port." -ForegroundColor Yellow
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }
    exit 0
}

Write-Host ">> [2/3] Terminating backend process(es): $($uniquePids -join ', ')..." -ForegroundColor Cyan
foreach ($p in $uniquePids) {
    try {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        Write-Host "[+] Sent termination signal to PID $p." -ForegroundColor Green
    } catch {
        Write-Host "[!] Could not stop PID $p : $_" -ForegroundColor Yellow
    }
}

# 3. Verify port release
Write-Host ">> [3/3] Verifying port $Port release..." -ForegroundColor Cyan
$released = $false
for ($i = 0; $i -lt $GraceTimeoutSeconds; $i++) {
    Start-Sleep -Seconds 1
    $stillActive = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (!$stillActive) {
        $released = $true
        break
    }
}

if (Test-Path $PidFile) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue }

if ($released) {
    Write-Host "[+] SUCCESS: Port $Port successfully released." -ForegroundColor Green
    exit 0
} else {
    Write-Host "[-] WARNING: Port $Port still occupied. Manual inspection required." -ForegroundColor Red
    exit 1
}

