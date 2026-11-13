#!/usr/bin/env bash
# ==============================================================================
# GARI AgriTech AI Lab — Oracle Cloud VM Rollback Script
# Execute from repository root: bash deploy/oracle/rollback.sh [BACKUP_FILE]
# ==============================================================================

set -euo pipefail

echo "=================================================================="
echo ">> [1/4] KÍCH HOẠT QUY TRÌNH HOÀN NGUYÊN KHẨN CẤP (ROLLBACK)..."
echo "=================================================================="

# Check Docker Compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "[-] Lỗi: Không tìm thấy Docker Compose."
    exit 1
fi

# Stop current running containers
echo ">> [2/4] Dừng các container đang hoạt động..."
$DOCKER_COMPOSE down || true

# [3/4] Quản lý Cơ sở dữ liệu (Bảo vệ dữ liệu sản xuất tuyệt đối)
# QUY TẮC AN TOÀN: Mặc định rollback CHỈ hoàn nguyên mã nguồn / container, KHÔNG BAO GIỜ tự ý ghi đè database.
RESTORE_FLAG="${1:-}"
SPECIFIC_BACKUP="${2:-}"

if [ "$RESTORE_FLAG" == "--restore-db" ] && [ -n "$SPECIFIC_BACKUP" ] && [ -f "$SPECIFIC_BACKUP" ]; then
    echo ">> [3/4] CẢNH BÁO: Yêu cầu khôi phục Database từ: $SPECIFIC_BACKUP"
    # Luôn tạo bản sao lưu an toàn của database hiện tại trước khi khôi phục
    mkdir -p database/backups
    SAFETY_BACKUP="database/backups/safety_backup_before_restore_$(date +%s).db"
    if [ -f database/disease_detector.db ]; then
        echo "[*] Đang tạo bản sao lưu khẩn cấp của database hiện tại vào: $SAFETY_BACKUP"
        cp database/disease_detector.db "$SAFETY_BACKUP"
    fi
    cp "$SPECIFIC_BACKUP" database/disease_detector.db
    # Xóa WAL files cũ để tránh xung đột trạng thái
    rm -f database/disease_detector.db-wal database/disease_detector.db-shm
    # Đảm bảo phân quyền UID 1000 cho container
    chown -R 1000:1000 database logs 2>/dev/null || true
    chmod -R 775 database logs 2>/dev/null || true
    echo "[+] Đã khôi phục cơ sở dữ liệu thành công từ $SPECIFIC_BACKUP."
else
    echo ">> [3/4] BẢO VỆ DỮ LIỆU: Giữ nguyên 100% cơ sở dữ liệu hiện tại (database/disease_detector.db)."
    echo "    Không ghi đè dữ liệu sản xuất bằng bản sao lưu cũ."
    echo "    (Nếu thực sự muốn khôi phục database, chạy: bash deploy/oracle/rollback.sh --restore-db <tệp_backup.db>)"
fi

# Restart containers
echo ">> [4/4] Khởi động lại các dịch vụ ổn định..."
$DOCKER_COMPOSE up -d

# Verify healthcheck
sleep 5
bash deploy/oracle/healthcheck.sh

echo "=================================================================="
echo ">> [HOÀN TẤT] Quy trình hoàn nguyên đã hoàn thành."
echo "=================================================================="

