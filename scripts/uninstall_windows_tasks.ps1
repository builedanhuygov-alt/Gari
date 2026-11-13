<#
.SYNOPSIS
    GARI AgriTech AI Lab — Windows Scheduled Task Uninstaller (PowerShell)
.DESCRIPTION
    Safely unregisters GARI background tasks from Windows Task Scheduler.
.EXAMPLE
    .\scripts\uninstall_windows_tasks.ps1
#>

$ErrorActionPreference = "SilentlyContinue"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> UNINSTALLING GARI WINDOWS SCHEDULED TASKS" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$tasks = @("GARI_Watchdog_Daemon", "GARI_Nightly_Database_Backup")

foreach ($t in $tasks) {
    $existing = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "[+] Removed Task: $t" -ForegroundColor Green
    } else {
        Write-Host "[*] Task not found (already uninstalled): $t" -ForegroundColor Gray
    }
}

Write-Host "==================================================================" -ForegroundColor Green
Write-Host "[+] All GARI Windows Scheduled Tasks have been uninstalled." -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green

