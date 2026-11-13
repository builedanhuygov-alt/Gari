#!/usr/bin/env bash
# ==============================================================================
# GARI AgriTech AI Lab — Oracle Cloud VM Bootstrap Script
# Target OS: Ubuntu 22.04 / 24.04 LTS (ARM64 Ampere A1 or x86_64)
# Run as root or with sudo: sudo bash deploy/oracle/bootstrap.sh
# ==============================================================================

set -euo pipefail

echo "=================================================================="
echo ">> [1/7] Bắt đầu khởi tạo hệ thống máy chủ Oracle Cloud..."
echo "=================================================================="

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo "[-] Lỗi: Vui lòng chạy script này với quyền root: sudo bash deploy/oracle/bootstrap.sh"
  exit 1
fi

ARCH=$(uname -m)
echo "[*] Kiến trúc CPU phát hiện: $ARCH"

# Update package repositories
echo ">> [2/7] Cập nhật các gói hệ thống..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    ufw \
    fail2ban \
    certbot \
    git \
    rsync \
    htop \
    iptables-persistent \
    netfilter-persistent

# Setup 4GB Swapfile for memory safety
echo ">> [3/7] Cấu hình 4GB Swapfile an toàn..."
if [ ! -f /swapfile ]; then
    fallocate -l 4G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=4096
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
    sysctl vm.swappiness=10
    echo 'vm.swappiness=10' >> /etc/sysctl.d/99-gari-swap.conf
    echo "[+] Tạo 4GB swapfile thành công."
else
    echo "[*] Swapfile đã tồn tại. Bỏ qua."
fi

# Install Docker CE & Docker Compose Plugin
echo ">> [4/7] Cài đặt Docker CE và Docker Compose..."
if ! command -v docker &> /dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    echo "[+] Docker đã được cài đặt và kích hoạt."
else
    echo "[*] Docker đã được cài đặt. Kiểm tra phiên bản:"
    docker --version
fi

# Add current user to docker group if ubuntu or opc user exists
CURRENT_USER="${SUDO_USER:-$(whoami)}"
if [ "$CURRENT_USER" != "root" ]; then
    usermod -aG docker "$CURRENT_USER" || true
    echo "[+] Đã thêm người dùng $CURRENT_USER vào nhóm docker."
fi

# Fix Oracle Cloud default IPTables blocking incoming HTTP/HTTPS and guarantee SSH persistence
echo ">> [5/7] Cấu hình iptables an toàn (chống khóa SSH)..."
# Đảm bảo port 22 luôn ở vị trí đầu tiên để không bao giờ bị mất kết nối SSH
iptables -C INPUT -p tcp --dport 22 -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport 22 -j ACCEPT
iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || iptables -I INPUT 2 -p tcp --dport 80 -j ACCEPT
iptables -C INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || iptables -I INPUT 3 -p tcp --dport 443 -j ACCEPT
netfilter-persistent save || true

# Configure UFW Host Firewall
echo ">> [6/7] Cấu hình tường lửa UFW..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP Nginx'
ufw allow 443/tcp comment 'HTTPS Nginx'
ufw --force enable
echo "[+] UFW firewall đã kích hoạt (chỉ mở port 22, 80, 443)."

# Create necessary application runtime directories
echo ">> [7/7] Khởi tạo các thư mục runtime..."
mkdir -p /var/www/certbot
mkdir -p database/uploads database/backups logs/nginx
chmod 755 /var/www/certbot

echo "=================================================================="
echo ">> [HOÀN TẤT] Bootstrap máy chủ Oracle Cloud thành công!"
echo ">> Bạn có thể tiếp tục với script: bash deploy/oracle/deploy.sh"
echo "=================================================================="

