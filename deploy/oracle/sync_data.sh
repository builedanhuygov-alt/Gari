#!/usr/bin/env bash
# ==============================================================================
# GARI AgriTech AI Lab — Data & Models Synchronization Script (Linux/macOS)
# Path: deploy/oracle/sync_data.sh
# Usage: bash deploy/oracle/sync_data.sh <VM_PUBLIC_IP> [SSH_KEY_PATH]
# Example: bash deploy/oracle/sync_data.sh 152.67.123.45 ~/.ssh/id_rsa
# ==============================================================================

set -euo pipefail

VM_IP="${1:-}"
SSH_KEY="${2:-}"

if [ -z "$VM_IP" ]; then
    echo "[-] Lỗi: Vui lòng cung cấp Public IP của máy chủ Oracle Cloud."
    echo "    Cách dùng: bash deploy/oracle/sync_data.sh <VM_PUBLIC_IP> [SSH_KEY_PATH]"
    exit 1
fi

SSH_OPTS="-o StrictHostKeyChecking=no"
if [ -n "$SSH_KEY" ]; then
    SSH_OPTS="$SSH_OPTS -i $SSH_KEY"
fi

REMOTE_USER="ubuntu"
REMOTE_DIR="/home/ubuntu/leaf-diseases-detector"

echo "=================================================================="
echo ">> [1/3] Kiểm tra kết nối SSH tới $REMOTE_USER@$VM_IP..."
echo "=================================================================="
ssh $SSH_OPTS "$REMOTE_USER@$VM_IP" "mkdir -p $REMOTE_DIR"

echo "=================================================================="
echo ">> [2/3] Đồng bộ mã nguồn và cấu hình (loại bỏ artifacts tạm)..."
echo "=================================================================="
rsync -avz --progress \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'models/' \
    -e "ssh $SSH_OPTS" \
    ./ "$REMOTE_USER@$VM_IP:$REMOTE_DIR/"

echo "=================================================================="
echo ">> [3/3] Đồng bộ thư mục Models (5.04 GB) & Database..."
echo "=================================================================="
rsync -avz --progress \
    -e "ssh $SSH_OPTS" \
    ./models/ "$REMOTE_USER@$VM_IP:$REMOTE_DIR/models/"

rsync -avz --progress \
    -e "ssh $SSH_OPTS" \
    ./database/disease_detector.db "$REMOTE_USER@$VM_IP:$REMOTE_DIR/database/disease_detector.db"

echo "=================================================================="
echo ">> [HOÀN TẤT] Dữ liệu đã đồng bộ lên Oracle Cloud VM!"
echo ">> Đăng nhập vào VM để triển khai:"
echo "   ssh $SSH_OPTS $REMOTE_USER@$VM_IP"
echo "   cd $REMOTE_DIR && sudo bash deploy/oracle/bootstrap.sh"
echo "=================================================================="

