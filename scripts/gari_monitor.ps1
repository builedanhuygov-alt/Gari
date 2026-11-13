<#
.SYNOPSIS
    GARI AgriTech AI Lab — Self-Hosted Resource & Service Telemetry Monitor (Windows PowerShell)
.DESCRIPTION
    Lightweight observability daemon monitoring backend health, cloudflared tunnel, host CPU/RAM/Disk,
    and SQLite WAL state. Emits structured JSONL telemetry without heavy SaaS dependencies.
.EXAMPLE
    .\scripts\gari_monitor.ps1 -LoopIntervalSeconds 30
#>

param (
    [string]$TargetUrl = "http://127.0.0.1:8000",
    [string]$TunnelUrl = "https://ist-towards-exclude-said.trycloudflare.com",
    [int]$LoopIntervalSeconds = 0,
    [string]$LogFile = "logs\local_monitoring.jsonl"
)

$ErrorActionPreference = "SilentlyContinue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$LogsDir = Join-Path $ProjectRoot "logs"
if (!(Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }
$LogFullPath = Join-Path $ProjectRoot $LogFile

function Get-GariSnapshot {
    $now = (Get-Date).ToUniversalTime().ToString("o")

    # 1. Host Resources
    $os = Get-CimInstance Win32_OperatingSystem
    $totalRamMb = [math]::Round($os.TotalVisibleMemorySize / 1024, 1)
    $freeRamMb = [math]::Round($os.FreePhysicalMemory / 1024, 1)
    $usedRamMb = [math]::Round($totalRamMb - $freeRamMb, 1)
    $ramPct = [math]::Round(($usedRamMb / $totalRamMb) * 100, 1)

    $cpuLoad = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    if ($null -eq $cpuLoad) { $cpuLoad = 0 }

    $drive = (Get-Item $ProjectRoot).PSDrive
    $diskTotalGb = [math]::Round(($drive.Used + $drive.Free) / (1024 * 1024 * 1024), 2)
    $diskFreeGb = [math]::Round($drive.Free / (1024 * 1024 * 1024), 2)
    $diskPct = [math]::Round((($diskTotalGb - $diskFreeGb) / $diskTotalGb) * 100, 1)

    # 2. Backend Process
    $backendProc = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
        (Get-NetTCPConnection -OwningProcess $_.Id -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
    } | Select-Object -First 1

    $backendRunning = ($backendProc -ne $null)
    $backendPid = if ($backendProc) { $backendProc.Id } else { $null }
    $backendRssMb = if ($backendProc) { [math]::Round($backendProc.WorkingSet64 / (1024 * 1024), 1) } else { 0 }

    # 3. Cloudflare Tunnel Process & Probe
    $tunnelProc = Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Select-Object -First 1
    $tunnelRunning = ($tunnelProc -ne $null)

    # Probe Local API
    $swLocal = [System.Diagnostics.Stopwatch]::StartNew()
    $localHealthy = $false
    try {
        $lResp = Invoke-RestMethod -Uri "$TargetUrl/health" -TimeoutSec 3 -ErrorAction Stop
        $swLocal.Stop()
        $localHealthy = ($lResp.status -in @("healthy", "ok"))
    } catch {
        $swLocal.Stop()
    }

    # Probe Public Tunnel API
    $swTunnel = [System.Diagnostics.Stopwatch]::StartNew()
    $tunnelHealthy = $false
    try {
        $tResp = Invoke-RestMethod -Uri "$TunnelUrl/health" -TimeoutSec 5 -ErrorAction Stop
        $swTunnel.Stop()
        $tunnelHealthy = ($tResp.status -in @("healthy", "ok"))
    } catch {
        $swTunnel.Stop()
    }

    # 4. SQLite State
    $dbFile = Join-Path $ProjectRoot "database\disease_detector.db"
    $walFile = Join-Path $ProjectRoot "database\disease_detector.db-wal"
    $dbSizeMb = if (Test-Path $dbFile) { [math]::Round((Get-Item $dbFile).Length / (1024 * 1024), 2) } else { 0 }
    $walSizeKb = if (Test-Path $walFile) { [math]::Round((Get-Item $walFile).Length / 1024, 1) } else { 0 }

    # Compose telemetry record
    $telemetry = [ordered]@{
        timestamp = $now
        system = [ordered]@{
            cpu_percent = $cpuLoad
            ram = [ordered]@{
                total_mb = $totalRamMb
                used_mb = $usedRamMb
                free_mb = $freeRamMb
                percent = $ramPct
            }
            disk = [ordered]@{
                total_gb = $diskTotalGb
                free_gb = $diskFreeGb
                percent = $diskPct
            }
        }
        backend = [ordered]@{
            running = $backendRunning
            pid = $backendPid
            working_set_mb = $backendRssMb
            local_healthy = $localHealthy
            latency_ms = $swLocal.ElapsedMilliseconds
        }
        tunnel = [ordered]@{
            running = $tunnelRunning
            public_healthy = $tunnelHealthy
            tunnel_url = $TunnelUrl
            latency_ms = $swTunnel.ElapsedMilliseconds
        }
        database = [ordered]@{
            db_size_mb = $dbSizeMb
            wal_size_kb = $walSizeKb
            wal_active = ($walSizeKb -ge 0)
        }
    }

    $jsonLine = $telemetry | ConvertTo-Json -Compress
    $jsonLine | Out-File -FilePath $LogFullPath -Append -Encoding utf8

    # Console output
    $bSym = if ($localHealthy) { "✓" } else { "✗" }
    $tSym = if ($tunnelHealthy) { "✓" } else { "✗" }
    $color = if ($localHealthy -and $tunnelHealthy) { "Green" } else { "Yellow" }

    Write-Host "[$bSym Local: $($swLocal.ElapsedMilliseconds)ms] [$tSym Tunnel: $($swTunnel.ElapsedMilliseconds)ms] | CPU: $cpuLoad% | RAM: $ramPct% ($usedRamMb/$totalRamMb MB) | Backend RSS: $backendRssMb MB" -ForegroundColor $color
}

if ($LoopIntervalSeconds -gt 0) {
    Write-Host ">> GARI Telemetry Monitor started (Polling interval: $LoopIntervalSeconds s). Press Ctrl+C to exit." -ForegroundColor Cyan
    while ($true) {
        Get-GariSnapshot
        Start-Sleep -Seconds $LoopIntervalSeconds
    }
} else {
    Get-GariSnapshot
}

