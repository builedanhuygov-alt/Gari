<#
.SYNOPSIS
    GARI AgriTech AI Lab — Self-Hosted Backend Health & Monitoring Inspector
.DESCRIPTION
    Probes local FastAPI, database integrity, AI models, and Cloudflare tunnel reachability.
#>

param (
    [string]$LocalUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$LogsDir = Join-Path $ProjectRoot "logs"
$TunnelUrlFile = Join-Path $LogsDir "gari_tunnel_url.txt"
$BackendPidFile = Join-Path $LogsDir "gari_backend.pid"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> GARI SELF-HOSTED BACKEND HEALTH INSPECTOR" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Local Process & Port Inspection
$portConn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portConn) {
    $procId = $portConn.OwningProcess
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    $memMb = if ($proc) { [math]::Round($proc.WorkingSet64 / 1MB, 1) } else { "N/A" }
    Write-Host "[+] Local Port 8000: LISTENING (PID: $procId, Memory: ${memMb} MB)" -ForegroundColor Green
} else {
    Write-Host "[-] Local Port 8000: NOT LISTENING (Backend is stopped)" -ForegroundColor Red
}

# 2. Local Endpoint Health Probe
try {
    $health = Invoke-RestMethod -Uri "$LocalUrl/api/health" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "[+] /api/health:     $($health.status.ToUpper())" -ForegroundColor Green
    Write-Host "    - Database:      $($health.services.database)" -ForegroundColor Gray
    Write-Host "    - Auth Service:  $($health.services.authentication)" -ForegroundColor Gray
    Write-Host "    - AI Inference:  $($health.services.ai_inference)" -ForegroundColor Gray
} catch {
    Write-Host "[-] /api/health:     UNREACHABLE ($($_.Exception.Message))" -ForegroundColor Red
}

try {
    $ready = Invoke-RestMethod -Uri "$LocalUrl/api/ready" -TimeoutSec 3 -ErrorAction Stop
    $readyStr = if ($ready.ready) { "READY" } else { "NOT READY" }
    Write-Host "[+] /api/ready:      $readyStr" -ForegroundColor Green
} catch {
    Write-Host "[-] /api/ready:      UNREACHABLE" -ForegroundColor Red
}

# 3. Database & Model Storage Verification
$dbPath = Join-Path $ProjectRoot "database\disease_detector.db"
if (Test-Path $dbPath) {
    $dbSizeMb = [math]::Round((Get-Item $dbPath).Length / 1MB, 2)
    Write-Host "[+] SQLite Database: PRESENT (${dbSizeMb} MB, $dbPath)" -ForegroundColor Green
} else {
    Write-Host "[-] SQLite Database: MISSING at $dbPath" -ForegroundColor Red
}

$modelsDir = Join-Path $ProjectRoot "models"
if (Test-Path $modelsDir) {
    $modelDirs = Get-ChildItem -Path $modelsDir -Directory -ErrorAction SilentlyContinue
    Write-Host "[+] AI Model Store:  PRESENT ($($modelDirs.Count) model directories)" -ForegroundColor Green
} else {
    Write-Host "[-] AI Model Store:  MISSING at $modelsDir" -ForegroundColor Red
}

# 4. Cloudflare Public Tunnel Probe
if (Test-Path $TunnelUrlFile) {
    $tunnelUrl = (Get-Content $TunnelUrlFile -Raw).Trim()
    Write-Host "`n------------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host ">> CLOUDFLARE PUBLIC TUNNEL INSPECTION" -ForegroundColor Cyan
    Write-Host "------------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "[*] Registered URL:  $tunnelUrl" -ForegroundColor Yellow

    try {
        $t0 = Get-Date
        $remoteHealth = Invoke-RestMethod -Uri "$tunnelUrl/api/health" -TimeoutSec 7 -ErrorAction Stop
        $latencyMs = [math]::Round(((Get-Date) - $t0).TotalMilliseconds, 1)
        Write-Host "[+] Tunnel Health:   REACHABLE via Public Internet ($($remoteHealth.status), Latency: ${latencyMs}ms)" -ForegroundColor Green
    } catch {
        # Check if failure is local DNS resolution latency
        $dnsRecord = Resolve-DnsName -Name ($tunnelUrl -replace '^https?://', '') -Server 1.1.1.1 -ErrorAction SilentlyContinue | Where-Object { $_.IP4Address } | Select-Object -First 1
        if ($dnsRecord) {
            $ip = $dnsRecord.IP4Address
            $hostHeader = ($tunnelUrl -replace '^https?://', '')
            $curlOut = curl.exe -s -i --resolve "${hostHeader}:443:${ip}" "$tunnelUrl/api/health"
            if ($curlOut -match "200 OK") {
                Write-Host "[+] Tunnel Health:   REACHABLE via Cloudflare Edge (${ip}:443, Public DNS 1.1.1.1 Verified)" -ForegroundColor Green
            } else {
                Write-Host "[-] Tunnel Health:   UNREACHABLE via Public Internet ($($_.Exception.Message))" -ForegroundColor Red
            }
        } else {
            Write-Host "[-] Tunnel Health:   UNREACHABLE via Public Internet ($($_.Exception.Message))" -ForegroundColor Red
            Write-Host "    The tunnel process may be down, or the URL has expired." -ForegroundColor Yellow
            Write-Host "    Run .\scripts\start_gari_tunnel.ps1 to generate an active URL." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "`n[*] Cloudflare Tunnel: No active tunnel URL recorded in logs\gari_tunnel_url.txt." -ForegroundColor Yellow
}

Write-Host "==================================================================" -ForegroundColor Cyan
