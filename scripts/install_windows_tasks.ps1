<#
.SYNOPSIS
    GARI AgriTech AI Lab — Windows Scheduled Task Installer (PowerShell)
.DESCRIPTION
    Configures non-administrative, user-level Windows Scheduled Tasks to automatically start
    the GARI Watchdog (FastAPI backend + Cloudflare Tunnel) on User Logon and run nightly database backups.
    Requires ZERO password storage and operates entirely within user permissions.
.EXAMPLE
    .\scripts\install_windows_tasks.ps1
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> INSTALLING GARI WINDOWS SCHEDULED TASKS (USER LOGON)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "[*] Registering tasks for user: $CurrentUser" -ForegroundColor Gray

# 1. Watchdog Daemon Task (Runs at Logon)
$watchdogTaskName = "GARI_Watchdog_Daemon"
$watchdogScript = Join-Path $ProjectRoot "scripts\gari_watchdog.ps1"

# Unregister if already exists
Unregister-ScheduledTask -TaskName $watchdogTaskName -Confirm:$false -ErrorAction SilentlyContinue

$watchdogAction = New-ScheduledTaskAction `
    -Execute "pwsh.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watchdogScript`" -Daemon -IntervalSeconds 30" `
    -WorkingDirectory $ProjectRoot

$watchdogTrigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser

$watchdogSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $watchdogTaskName `
    -Action $watchdogAction `
    -Trigger $watchdogTrigger `
    -Settings $watchdogSettings `
    -Description "GARI AgriTech AI Lab Background Watchdog (FastAPI + Cloudflare Tunnel)" `
    -User $CurrentUser | Out-Null

Write-Host "[+] Task 1 Installed: $watchdogTaskName (Triggers on User Logon)" -ForegroundColor Green

# 2. Nightly Database Backup Task (Daily at 02:00 AM)
$backupTaskName = "GARI_Nightly_Database_Backup"
$backupScript = Join-Path $ProjectRoot "scripts\backup_database.ps1"

Unregister-ScheduledTask -TaskName $backupTaskName -Confirm:$false -ErrorAction SilentlyContinue

$backupAction = New-ScheduledTaskAction `
    -Execute "pwsh.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$backupScript`"" `
    -WorkingDirectory $ProjectRoot

$backupTrigger = New-ScheduledTaskTrigger -Daily -At 2am

$backupSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $backupTaskName `
    -Action $backupAction `
    -Trigger $backupTrigger `
    -Settings $backupSettings `
    -Description "GARI AgriTech AI Lab Nightly WAL-Safe Database Backup" `
    -User $CurrentUser | Out-Null

Write-Host "[+] Task 2 Installed: $backupTaskName (Runs daily at 02:00 AM)" -ForegroundColor Green

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> VERIFYING REGISTERED TASKS:" -ForegroundColor Cyan
Get-ScheduledTask -TaskName "GARI_*" | Select-Object TaskName, State, @{N='User';E={$_.Principal.UserId}} | Format-Table -AutoSize

Write-Host "[+] To uninstall these tasks at any time, run: .\scripts\uninstall_windows_tasks.ps1" -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Green

