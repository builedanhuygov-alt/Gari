<#
.SYNOPSIS
    GARI AgriTech AI Lab — Cloudflare Quick Tunnel Launch Script
.DESCRIPTION
    Establishes an encrypted, zero-port-forwarding Cloudflare Tunnel from public internet
    to local FastAPI origin (http://127.0.0.1:8000).
#>

param (
    [string]$LocalOrigin = "http://127.0.0.1:8000",
    [int]$MaxWaitSeconds = 25
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$LogsDir = Join-Path $ProjectRoot "logs"
if (!(Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }
$TunnelPidFile = Join-Path $LogsDir "cloudflared.pid"
$TunnelLogFile = Join-Path $LogsDir "cloudflared.log"
$TunnelUrlFile = Join-Path $LogsDir "gari_tunnel_url.txt"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> [GARI TUNNEL] Initializing Cloudflare Zero-Trust Quick Tunnel..." -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Verify local backend is alive before starting tunnel
Write-Host "[*] Probing local FastAPI backend health ($LocalOrigin/api/health)..." -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "$LocalOrigin/api/health" -TimeoutSec 3 -ErrorAction Stop
    if ($health.status -notin @("healthy", "ok")) {
        throw "Backend responded with non-healthy status: $($health.status)"
    }
    Write-Host "[+] Local backend is verified ONLINE and HEALTHY." -ForegroundColor Green
} catch {
    Write-Host "[-] FATAL: Local FastAPI backend is not accessible at $LocalOrigin." -ForegroundColor Red
    Write-Host "    Please run .\scripts\start_gari_backend.ps1 first." -ForegroundColor Yellow
    exit 1
}

# 2. Check if cloudflared is already running
$runningCf = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
if ($runningCf) {
    Write-Host "[*] cloudflared is ALREADY RUNNING (PID: $($runningCf[0].Id))." -ForegroundColor Yellow
    if (Test-Path $TunnelUrlFile) {
        $existingUrl = (Get-Content $TunnelUrlFile -Raw).Trim()
        Write-Host "[+] Active Tunnel URL: $existingUrl" -ForegroundColor Green
        Write-Host "[*] Testing tunnel endpoint..." -ForegroundColor Cyan
        try {
            $testHealth = Invoke-RestMethod -Uri "$existingUrl/api/health" -TimeoutSec 5 -ErrorAction Stop
            if ($testHealth.status -in @("healthy", "ok")) {
                Write-Host "[+] Tunnel is verified REACHABLE from the public internet!" -ForegroundColor Green
                exit 0
            }
        } catch {
            Write-Host "[!] Existing tunnel PID $($runningCf[0].Id) is not responding. Terminating stale process..." -ForegroundColor Yellow
            Stop-Process -Id $runningCf[0].Id -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "[!] Terminating unmapped cloudflared process..." -ForegroundColor Yellow
        Stop-Process -Id $runningCf[0].Id -Force -ErrorAction SilentlyContinue
    }
}

# 3. Locate cloudflared.exe
$CloudflaredBin = Join-Path $ProjectRoot "cloudflared.exe"
if (!(Test-Path $CloudflaredBin)) {
    $CloudflaredBin = (Get-Command cloudflared.exe -ErrorAction SilentlyContinue)?.Source
    if (!$CloudflaredBin) {
        Write-Host "[-] FATAL: cloudflared.exe not found in $ProjectRoot or system PATH." -ForegroundColor Red
        Write-Host "    Download from: https://github.com/cloudflare/cloudflared/releases" -ForegroundColor Yellow
        exit 1
    }
}

# Clear previous log
if (Test-Path $TunnelLogFile) { Remove-Item $TunnelLogFile -Force }

Write-Host "[*] Starting Cloudflare Quick Tunnel forwarding to $LocalOrigin..." -ForegroundColor Cyan
$proc = Start-Process -FilePath $CloudflaredBin -ArgumentList "tunnel --url $LocalOrigin --protocol http2 --no-autoupdate" -PassThru -NoNewWindow -RedirectStandardError $TunnelLogFile

$proc.Id | Out-File -FilePath $TunnelPidFile -Encoding ascii

# 4. Wait and extract public tunnel URL from log file
$startTime = Get-Date
$tunnelUrl = $null

while (((Get-Date) - $startTime).TotalSeconds -lt $MaxWaitSeconds) {
    Start-Sleep -Milliseconds 750
    if (Test-Path $TunnelLogFile) {
        $content = Get-Content $TunnelLogFile -Raw -ErrorAction SilentlyContinue
        if ($content -match '(https://[a-zA-Z0-9-]+\.trycloudflare\.com)') {
            $tunnelUrl = $matches[1]
            break
        }
    }
    if ($proc.HasExited) {
        Write-Host "[-] cloudflared process terminated prematurely." -ForegroundColor Red
        if (Test-Path $TunnelLogFile) { Get-Content $TunnelLogFile -Tail 15 }
        exit 1
    }
}

if ($tunnelUrl) {
    $tunnelUrl | Out-File -FilePath $TunnelUrlFile -Encoding ascii
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host "[+] CLOUDFLARE QUICK TUNNEL ESTABLISHED SUCCESSFULLY!" -ForegroundColor Green
    Write-Host "    - Public URL:  $tunnelUrl" -ForegroundColor Yellow
    Write-Host "    - Local Proxy: $LocalOrigin" -ForegroundColor Gray
    Write-Host "    - PID:         $($proc.Id)" -ForegroundColor Gray
    Write-Host "==================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "[!] IMPORTANT NOTICE REGARDING QUICK TUNNELS:" -ForegroundColor Yellow
    Write-Host "    1. This is a temporary testing URL generated anonymously by Cloudflare." -ForegroundColor Gray
    Write-Host "    2. If this process is stopped or your PC restarts, a NEW URL will be assigned." -ForegroundColor Gray
    Write-Host "    3. To link with Vercel Preview, update VERCEL_BACKEND_API_URL in Vercel Project Settings:" -ForegroundColor Cyan
    Write-Host "       Variable: VERCEL_BACKEND_API_URL" -ForegroundColor Cyan
    Write-Host "       Value:    $tunnelUrl" -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[-] Failed to detect public tunnel URL within ${MaxWaitSeconds}s." -ForegroundColor Red
    if (Test-Path $TunnelLogFile) { Get-Content $TunnelLogFile -Tail 15 }
    exit 1
}
