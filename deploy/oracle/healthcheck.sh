#!/usr/bin/env bash
# ==============================================================================
# GARI AgriTech AI Lab — Oracle Cloud VM Healthcheck & Diagnostic Tool
# Execute from repository root: bash deploy/oracle/healthcheck.sh [TARGET_URL]
# ==============================================================================

set -euo pipefail

TARGET_URL="${1:-http://127.0.0.1:8000}"

echo "=================================================================="
echo ">> Kiểm tra sức khỏe hệ thống GARI tại: $TARGET_URL"
echo "=================================================================="

# Colors for terminal output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0

test_endpoint() {
    local name="$1"
    local endpoint="$2"
    local expected_code="$3"
    
    echo -n "[*] Kiểm tra $name ($endpoint)... "
    local http_code
    http_code=$(curl -s -o /tmp/gari_hc_response.txt -w "%{http_code}" "$TARGET_URL$endpoint" || echo "000")
    
    if [ "$http_code" -eq "$expected_code" ]; then
        echo -e "${GREEN}PASS${NC} (HTTP $http_code)"
        pass_count=$((pass_count + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC} (Kỳ vọng $expected_code, nhận được $http_code)"
        if [ -s /tmp/gari_hc_response.txt ]; then
            head -n 2 /tmp/gari_hc_response.txt
        fi
        fail_count=$((fail_count + 1))
        return 1
    fi
}

# 1. Health endpoint
test_endpoint "API Health" "/health" 200

# 2. Ready probe
test_endpoint "API Ready Probe" "/ready" 200

# 3. Crop Knowledge Catalog
test_endpoint "Thư viện Cây trồng" "/api/knowledge/crops" 200

# 4. Model Registry for Tomato
test_endpoint "Danh mục Model Cà chua" "/api/models/Tomato" 200

# 5. Check response JSON structure
echo -n "[*] Kiểm tra thông tin chi tiết từ /health... "
HEALTH_JSON=$(curl -s "$TARGET_URL/health" || echo "{}")
if echo "$HEALTH_JSON" | grep -qE '"status":"(healthy|ok)"'; then
    echo -e "${GREEN}OK (healthy)${NC}"
    echo "    $HEALTH_JSON"
else
    echo -e "${YELLOW}WARNING (Phản hồi không chứa status=healthy hoặc status=ok)${NC}"
fi

# 6. Check Docker Container resource consumption
if command -v docker &> /dev/null && docker ps | grep -q gari-backend; then
    echo ""
    echo "=================================================================="
    echo ">> Thống kê tài nguyên Container đang chạy:"
    echo "=================================================================="
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}" gari-backend gari-nginx 2>/dev/null || true
fi

# 7. Check SQLite WAL Database File
echo ""
echo "=================================================================="
echo ">> Kiểm tra trạng thái Cơ sở dữ liệu SQLite:"
echo "=================================================================="
if [ -f database/disease_detector.db ]; then
    DB_SIZE=$(du -h database/disease_detector.db | cut -f1)
    echo -e "[+] Tệp database chính: ${GREEN}TỒN TẠI${NC} (Dung lượng: $DB_SIZE)"
    if [ -f database/disease_detector.db-wal ]; then
        WAL_SIZE=$(du -h database/disease_detector.db-wal | cut -f1)
        echo -e "[+] WAL Journal file: ${GREEN}HOẠT ĐỘNG${NC} (Dung lượng: $WAL_SIZE)"
    fi
else
    echo -e "[-] Tệp database chính: ${RED}CHƯA TỒN TẠI${NC}"
fi

echo ""
echo "=================================================================="
if [ $fail_count -eq 0 ]; then
    echo -e ">> KẾT QUẢ: ${GREEN}TẤT CẢ $pass_count KIỂM TRA ĐỀU THÀNH CÔNG!${NC}"
else
    echo -e ">> KẾT QUẢ: ${RED}$fail_count KIỂM TRA THẤT BẠI${NC}, $pass_count thành công."
fi
echo "=================================================================="

