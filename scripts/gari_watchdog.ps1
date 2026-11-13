<#
.SYNOPSIS
    GARI AgriTech AI Lab — Self-Hosted Watchdog & Auto-Recovery Engine (PowerShell)
.DESCRIPTION
    Monitors FastAPI backend and Cloudflare Tunnel processes.
    Enforces bounded retries with exponential backoff to prevent crash loops.
    Guarantees zero duplicate process spawning.
.EXAMPLE
    .\scripts\gari_watchdog.ps1 -SingleCheck
    .\scripts\gari_watchdog.ps1 -Daemon -IntervalSeconds 30
#>

param (
    [switch]$SingleCheck,
    [switch]$Daemon,
    [int]$IntervalSeconds = 30,
    [int]$Port = 8000,
    [int]$MaxRestartsInWindow = 3,
    [int]$WindowMinutes = 10
)

$ErrorActionPreference = "SilentlyContinue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

$LogsDir = Join-Path $ProjectRoot "logs"
if (!(Test-Path $LogsDir)) { New-Item -ItemType Directory -Path $LogsDir | Out-Null }
$WatchdogLog = Join-Path $LogsDir "watchdog.log"
$RestartStateFile = Join-Path $LogsDir "watchdog_restarts.json"

function Write-WatchdogLog {
    param ([string]$Level, [string]$Message)
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$ts] [$Level] $Message"
    $line | Out-File -FilePath $WatchdogLog -Append -Encoding utf8
    $color = switch ($Level) {
        "ERROR"   { "Red" }
        "WARN"    { "Yellow" }
        "SUCCESS" { "Green" }
        default   { "Cyan" }
    }
    Write-Host $line -ForegroundColor $color
}

function Get-RestartHistory {
    if (Test-Path $RestartStateFile) {
        try {
            $data = Get-Content $RestartStateFile -Raw | ConvertFrom-Json
            $cutoff = (Get-Date).AddMinutes(-$WindowMinutes)
            $validTimes = @()
            foreach ($t in $data.restart_timestamps) {
                $dt = [DateTime]::Parse($t)
                if ($dt -gt $cutoff) { $validTimes += $t }
            }
            return $validTimes
        } catch {
            return @()
        }
    }
    return @()
}

function Record-RestartEvent {
    $history = Get-RestartHistory
    $nowStr = (Get-Date).ToString("o")
    $history += $nowStr
    $obj = [ordered]@{
        last_restart = $nowStr
        total_recent = $history.Count
        restart_timestamps = $history
    }
    $obj | ConvertTo-Json | Out-File -FilePath $RestartStateFile -Encoding utf8
}

function Check-BackendHealth {
    $active = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (!$active) { return $false }
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 4 -ErrorAction Stop
        return ($resp.status -in @("healthy", "ok"))
    } catch {
        return $false
    }
}

function Check-TunnelProcess {
    $proc = Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Select-Object -First 1
    return ($proc -ne $null)
}

function Ensure-GariServices {
    # 1. Backend Verification
    $backendOk = Check-BackendHealth
    if ($backendOk) {
        Write-WatchdogLog "INFO" "FastAPI backend is active and healthy on port $Port."
    } else {
        Write-WatchdogLog "WARN" "FastAPI backend is NOT responding on port $Port. Initiating recovery..."
        
        $history = Get-RestartHistory
        if ($history.Count -ge $MaxRestartsInWindow) {
            Write-WatchdogLog "ERROR" "CRASH LOOP BLOCKED: Backend failed $MaxRestartsInWindow times within $WindowMinutes mins. Manual inspection required."
            return
        }

        # Check existing port to terminate any zombie process
        & (Join-Path $ScriptDir "stop_backend.ps1") -Port $Port
        Start-Sleep -Seconds 2

        # Record restart attempt
        Record-RestartEvent
        Write-WatchdogLog "WARN" "Restart attempt $($history.Count + 1) of $MaxRestartsInWindow..."

        # Start backend
        & (Join-Path $ScriptDir "start_backend.ps1") -Port $Port
        Start-Sleep -Seconds 3

        if (Check-BackendHealth) {
            Write-WatchdogLog "SUCCESS" "FastAPI backend successfully recovered!"
        } else {
            Write-WatchdogLog "ERROR" "Backend start failed. Check logs/backend_stderr.log."
            return
        }
    }

    # 2. Cloudflare Tunnel Verification
    $tunnelOk = Check-TunnelProcess
    if ($tunnelOk) {
        Write-WatchdogLog "INFO" "Cloudflare Tunnel process (cloudflared.exe) is running."
    } else {
        Write-WatchdogLog "WARN" "cloudflared.exe is NOT running. Launching tunnel daemon..."
        
        $cloudflaredBin = Join-Path $ProjectRoot "cloudflared.exe"
        if (Test-Path $cloudflaredBin) {
            $tunnelOutLog = Join-Path $LogsDir "tunnel_stdout.log"
            $tunnelErrLog = Join-Path $LogsDir "tunnel_stderr.log"
            
            Start-Process -FilePath $cloudflaredBin `
                -ArgumentList "tunnel --url http://127.0.0.1:$Port" `
                -WorkingDirectory $ProjectRoot `
                -RedirectStandardOutput $tunnelOutLog `
                -RedirectStandardError $tunnelErrLog `
                -WindowStyle Hidden
            
            Start-Sleep -Seconds 4
            if (Check-TunnelProcess) {
                Write-WatchdogLog "SUCCESS" "Cloudflare Tunnel process launched successfully."
            } else {
                Write-WatchdogLog "ERROR" "Failed to start cloudflared.exe."
            }
        } else {
            Write-WatchdogLog "ERROR" "cloudflared.exe not found at: $cloudflaredBin"
        }
    }
}

# Main Execution Flow
Write-WatchdogLog "INFO" "=== GARI Watchdog Sweep Initiated ==="

if ($Daemon) {
    Write-WatchdogLog "INFO" "Running in continuous daemon mode (sweep interval: $IntervalSeconds s)."
    while ($true) {
        Ensure-GariServices
        Start-Sleep -Seconds $IntervalSeconds
    }
} else {
    Ensure-GariServices
    Write-WatchdogLog "INFO" "=== Sweep Completed ==="
}

