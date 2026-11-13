<#
.SYNOPSIS
    GARI AgriTech AI Lab — Self-Hosted Backend Restart Script (Windows PowerShell)
.DESCRIPTION
    Safely recycles the FastAPI backend process and confirms renewed health.
.EXAMPLE
    .\scripts\restart_backend.ps1
#>

param (
    [int]$Port = 8000,
    [string]$HostAddress = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> RESTARTING GARI BACKEND SERVICE..." -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Stop
& (Join-Path $ScriptDir "stop_backend.ps1") -Port $Port
Start-Sleep -Seconds 2

# 2. Start
& (Join-Path $ScriptDir "start_backend.ps1") -Port $Port -HostAddress $HostAddress

Write-Host "==================================================================" -ForegroundColor Green
Write-Host ">> GARI BACKEND RESTART COMPLETED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green

