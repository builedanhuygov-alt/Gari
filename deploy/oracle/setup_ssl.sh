#!/usr/bin/env bash
# ==============================================================================
# GARI AgriTech AI Lab — Let's Encrypt Automated SSL Setup Script
# Path: deploy/oracle/setup_ssl.sh
# Usage: sudo bash deploy/oracle/setup_ssl.sh <DOMAIN_NAME> <CONTACT_EMAIL>
# Example: sudo bash deploy/oracle/setup_ssl.sh api.gari.vn admin@gari.vn
# ==============================================================================

set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "[-] Lỗi cú pháp: Vui lòng cung cấp Domain và Email quản trị."
    echo "    Cách dùng: sudo bash deploy/oracle/setup_ssl.sh <DOMAIN_NAME> <CONTACT_EMAIL>"
    echo "    Ví dụ:     sudo bash deploy/oracle/setup_ssl.sh api.gari.vn admin@gari.vn"
    exit 1
fi

echo "=================================================================="
echo ">> [1/4] Chuẩn bị cấp phát chứng chỉ SSL Let's Encrypt cho: $DOMAIN"
echo "=================================================================="

# Check root privileges
if [ "$EUID" -ne 0 ]; then
  echo "[-] Lỗi: Vui lòng chạy với quyền root hoặc sudo."
  exit 1
fi

# 1. Ensure Certbot webroot directory exists
mkdir -p /var/www/certbot
chmod 755 /var/www/certbot

# 2. Use HTTP-only configuration to avoid SSL file missing crash
echo ">> [2/4] Kích hoạt cấu hình HTTP xác thực ACME..."
cp deploy/oracle/nginx/conf.d/gari-http.conf deploy/oracle/nginx/conf.d/gari.conf

# Reload or start Nginx container
if docker ps | grep -q gari-nginx; then
    docker exec gari-nginx nginx -s reload || true
else
    docker compose up -d nginx
fi

# 3. Request certificate via Certbot webroot mode
echo ">> [3/4] Gửi yêu cầu cấp chứng chỉ tới Let's Encrypt..."
certbot certonly --webroot \
    -w /var/www/certbot \
    -d "$DOMAIN" \
    --cert-name gari \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive

# 4. Switch to full SSL configuration and reload Nginx
echo ">> [4/4] Cập nhật Nginx sang cấu hình HTTPS bảo mật..."
cp deploy/oracle/nginx/conf.d/gari-ssl.conf deploy/oracle/nginx/conf.d/gari.conf
# Replace server_name with actual domain
sed -i "s/server_name _;/server_name $DOMAIN;/g" deploy/oracle/nginx/conf.d/gari.conf

docker exec gari-nginx nginx -t
docker exec gari-nginx nginx -s reload

echo "=================================================================="
echo ">> [HOÀN TẤT] HTTPS đã kích hoạt thành công cho $DOMAIN!"
echo ">> Kiểm tra endpoint: https://$DOMAIN/health"
echo "=================================================================="

