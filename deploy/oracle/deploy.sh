#!/usr/bin/env bash
# ==============================================================================
# GARI AgriTech AI Lab — Oracle Cloud VM Deployment Script
# Execute from repository root: bash deploy/oracle/deploy.sh
# ==============================================================================

set -euo pipefail

echo "=================================================================="
echo ">> [1/5] Kiểm tra điều kiện tiên quyết trước khi Deploy..."
echo "=================================================================="

# Check Docker Compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "[-] Lỗi: Không tìm thấy Docker Compose. Vui lòng chạy bootstrap.sh trước."
    exit 1
fi

# Check .env file
if [ ! -f .env ]; then
    echo "[!] Cảnh báo: Tệp .env chưa tồn tại. Đang tạo từ .env.example..."
    cp .env.example .env
    # Generate random JWT Secret Key if unset
    RANDOM_JWT=$(openssl rand -hex 32)
    sed -i "s/replace_with_a_secure_random_string_at_least_32_chars_long/$RANDOM_JWT/" .env
    echo "[+] Đã tạo .env mới với JWT_SECRET_KEY ngẫu nhiên."
fi

# Check models directory
if [ ! -d models ] || [ ! -d "models/Model tong" ]; then
    echo "[-] Lỗi: Không tìm thấy thư mục models/ hoặc models/Model tong."
    echo "    Vui lòng đảm bảo các tệp trọng số AI đã được sao chép vào models/."
    exit 1
fi

MODEL_COUNT=$(find models -name "*.safetensors" | wc -l)
echo "[+] Phát hiện thư mục models với $MODEL_COUNT mô hình .safetensors hợp lệ."

# Check database directory & permissions
mkdir -p database/uploads database/backups logs/nginx
chmod 775 database database/uploads database/backups logs
# Allow UID 1000 (non-root container user) write access to database
if [ "$EUID" -eq 0 ]; then
    chown -R 1000:1000 database logs || true
fi

echo "=================================================================="
echo ">> [2/5] Tiến hành Build Docker Image cho GARI Backend..."
echo "=================================================================="

$DOCKER_COMPOSE build --pull gari-backend

echo "=================================================================="
echo ">> [3/5] Khởi động các container (FastAPI + Nginx)..."
echo "=================================================================="

$DOCKER_COMPOSE up -d

echo "=================================================================="
echo ">> [4/5] Đang chờ dịch vụ sẵn sàng (Healthcheck Probe)..."
echo "=================================================================="

MAX_RETRIES=15
COUNT=0
HEALTHY=false

while [ $COUNT -lt $MAX_RETRIES ]; do
    COUNT=$((COUNT + 1))
    echo "[*] Kiểm tra trạng thái container lần $COUNT/$MAX_RETRIES..."
    
    # Check internal container health
    CONTAINER_HEALTH=$(docker inspect --format='{{json .State.Health.Status}}' gari-backend 2>/dev/null || echo '"unknown"')
    
    if [ "$CONTAINER_HEALTH" == '"healthy"' ]; then
        HEALTHY=true
        break
    fi
    
    # Also test via direct curl to port 8000
    if curl -s -f http://127.0.0.1:8000/health > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    
    sleep 4
done

if [ "$HEALTHY" = true ]; then
    echo "[+] Dịch vụ GARI Backend đã KHỎE MẠNH (HEALTHY) và sẵn sàng!"
else
    echo "[-] Cảnh báo: Container chưa chuyển sang trạng thái Healthy sau 60s."
    echo "    Xem nhật ký chi tiết:"
    $DOCKER_COMPOSE logs --tail=50 gari-backend
fi

echo "=================================================================="
echo ">> [5/5] Trạng thái các dịch vụ đang chạy:"
echo "=================================================================="

$DOCKER_COMPOSE ps

echo ""
echo ">> GARI API nội bộ: http://127.0.0.1:8000"
echo ">> GARI Nginx công khai: http://$(curl -s ifconfig.me || echo 'YOUR_VM_IP')"
echo ">> Chạy lệnh kiểm tra toàn diện: bash deploy/oracle/healthcheck.sh"
echo "=================================================================="

