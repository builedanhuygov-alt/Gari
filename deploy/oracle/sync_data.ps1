<#
.SYNOPSIS
    GARI AgriTech AI Lab — Data & Models Synchronization Script (Windows PowerShell)
.DESCRIPTION
    Syncs source code, AI models (5.04 GB), and SQLite database to Oracle Cloud VM via SCP.
.EXAMPLE
    .\deploy\oracle\sync_data.ps1 -VmIp "152.67.123.45" -KeyPath "C:\Users\username\.ssh\oracle_key"
#>

param (
    [Parameter(Mandatory=$true)]
    [string]$VmIp,

    [Parameter(Mandatory=$false)]
    [string]$KeyPath = "",

    [Parameter(Mandatory=$false)]
    [string]$User = "ubuntu",

    [Parameter(Mandatory=$false)]
    [string]$RemoteDir = "/home/ubuntu/leaf-diseases-detector"
)

$ErrorActionPreference = "Stop"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> [1/4] Kiểm tra tham số và kết nối SSH tới $User@$VmIp..." -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$sshKeyArg = ""
if ($KeyPath -and (Test-Path $KeyPath)) {
    $sshKeyArg = "-i `"$KeyPath`""
}

# Create remote directory
$cmd = "ssh $sshKeyArg -o StrictHostKeyChecking=no $User@$VmIp `"mkdir -p $RemoteDir/models $RemoteDir/database $RemoteDir/logs`""
Invoke-Expression $cmd

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> [2/4] Đồng bộ Cơ sở dữ liệu SQLite..." -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$scpDb = "scp $sshKeyArg -o StrictHostKeyChecking=no .\database\disease_detector.db ${User}@${VmIp}:${RemoteDir}/database/"
Invoke-Expression $scpDb

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> [3/4] Đồng bộ Thư mục AI Models (5.04 GB, 51 entries)..." -ForegroundColor Cyan
Write-Host ">> Lưu ý: Quá trình này có thể mất từ 3-8 phút tùy tốc độ mạng." -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Cyan

$scpModels = "scp $sshKeyArg -o StrictHostKeyChecking=no -r .\models\* ${User}@${VmIp}:${RemoteDir}/models/"
Invoke-Expression $scpModels

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ">> [4/4] Đồng bộ Mã nguồn Backend & Cấu hình Docker..." -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# Copy key files
$filesToCopy = @(
    "Dockerfile", "docker-compose.yml", "requirements-production.txt",
    "requirements.txt", ".env.example", "api_server.py", "gari_config.py",
    "gari_database.py", "gari_auth.py", "gari_inference_engine.py",
    "gari_model_lifecycle.py", "gari_knowledge.py", "gari_plans.py",
    "gari_privacy.py", "gari_quota.py", "gari_revenue.py", "gari_vouchers.py",
    "gari_b2b.py", "gari_visual_localization.py", "model_inventory.json"
)

foreach ($f in $filesToCopy) {
    if (Test-Path $f) {
        $cmdFile = "scp $sshKeyArg -o StrictHostKeyChecking=no `"$f`" ${User}@${VmIp}:${RemoteDir}/"
        Invoke-Expression $cmdFile
    }
}

# Copy directories: deploy and localization
$cmdDeploy = "scp $sshKeyArg -o StrictHostKeyChecking=no -r .\deploy ${User}@${VmIp}:${RemoteDir}/"
Invoke-Expression $cmdDeploy

$cmdLoc = "scp $sshKeyArg -o StrictHostKeyChecking=no -r .\localization ${User}@${VmIp}:${RemoteDir}/"
Invoke-Expression $cmdLoc

Write-Host "==================================================================" -ForegroundColor Green
Write-Host ">> [HOÀN TẤT] Dữ liệu đã đồng bộ thành công lên máy chủ Oracle!" -ForegroundColor Green
Write-Host ">> Đăng nhập vào VM để khởi chạy:" -ForegroundColor White
Write-Host "   ssh $sshKeyArg $User@$VmIp" -ForegroundColor Yellow
Write-Host "   cd $RemoteDir && sudo bash deploy/oracle/bootstrap.sh" -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Green

