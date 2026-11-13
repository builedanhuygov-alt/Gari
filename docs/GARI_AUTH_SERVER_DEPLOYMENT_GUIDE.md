# GARI Auth Server 1.0 — Cloud VPS Deployment Guide
**Document:** `docs/GARI_AUTH_SERVER_DEPLOYMENT_GUIDE.md`  
**Date:** November 13, 2026  
**Target:** Ubuntu 22.04 / 24.04 LTS or Debian 12 Cloud VPS  

---

## 1. Cloud VPS Prerequisites & Sizing

| Component | Minimum Specification | Recommended Specification |
|---|---|---|
| **CPU** | 1 vCPU (x86_64 or ARM64) | 2 vCPU |
| **RAM** | 1 GB | 2 GB (provides ample room for Argon2id hashing) |
| **Storage** | 20 GB NVMe SSD (Persistent) | 40 GB NVMe SSD |
| **Operating System** | Ubuntu 22.04 LTS / 24.04 LTS | Ubuntu 24.04 LTS |
| **Public Ports** | 80 (HTTP), 443 (HTTPS), 22 (SSH) | All other ports blocked via UFW |

> [!IMPORTANT]
> The database (`gari_auth.db`) must reside on a **persistent block volume**. Never deploy SQLite on an ephemeral or container-local root filesystem that resets upon reboot.

---

## 2. Server Provisioning & OS Hardening

### 2.1. System Update & Docker Installation
```bash
# SSH into your VPS as root or sudoer
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl ufw git fail2ban

# Configure UFW Firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Install Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2.2. Directory & Permissions Setup
```bash
sudo mkdir -p /var/lib/gari-auth/data
sudo mkdir -p /var/lib/gari-auth/backups
sudo chown -R 10001:10001 /var/lib/gari-auth
sudo chmod 700 /var/lib/gari-auth/data
sudo chmod 700 /var/lib/gari-auth/backups
```

---

## 3. Deployment via Docker Compose

### 3.1. Clone Repository & Navigate
```bash
git clone https://github.com/dhuy170509/leaf-diseases-detector.git /opt/gari-app
cd /opt/gari-app/auth-server
```

### 3.2. Environment Configuration (`.env`)
Create `/opt/gari-app/auth-server/.env`:
```ini
AUTH_ENV=production
AUTH_HOST=0.0.0.0
AUTH_PORT=8001
AUTH_DATA_DIR=/var/lib/gari-auth/data
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
MAX_REGISTRATION_ACCOUNTS=10
REGISTRATION_OPEN=true

# Domain for automatic TLS
AUTH_DOMAIN=auth.gari.vn

# Generate a strong 32+ character bootstrap token: openssl rand -hex 32
BOOTSTRAP_ADMIN_TOKEN=your_secure_random_bootstrap_token_here
```

### 3.3. Launch Services
```bash
docker compose up -d --build
```

### 3.4. Verify Health Status
```bash
curl -I https://auth.gari.vn/api/v1/health
# Expected: HTTP/2 200 OK
# {"status":"healthy","service":"GARI Independent Auth Server",...}
```

---

## 4. Initial Administrator Bootstrap

Once the service is active, execute the one-time admin bootstrap using the secret token:

```bash
curl -X POST https://auth.gari.vn/api/v1/admin/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "bootstrap_token": "your_secure_random_bootstrap_token_here",
    "email": "admin@gari.vn",
    "password": "StrongAdminPassword123!",
    "full_name": "Quản Trị Viên Hệ Thống GARI"
  }'
```

**Expected Response (HTTP 201 Created):**
```json
{
  "id": 1,
  "email": "admin@gari.vn",
  "full_name": "Quản Trị Viên Hệ Thống GARI",
  "account_type": "admin",
  "is_active": true,
  "is_verified": true
}
```

> [!CAUTION]
> Once an administrator account is created, any subsequent request to `/api/v1/admin/bootstrap` is permanently locked with HTTP 409 Conflict.

---

## 5. Automated Backup Cron Job

Create a daily automated backup script: `/etc/cron.daily/gari_auth_backup`:
```bash
#!/bin/bash
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/lib/gari-auth/backups"
DB_PATH="/var/lib/gari-auth/data/gari_auth.db"

# Run lock-free backup inside container or via python
docker exec gari-auth-service python scripts/backup_db.py

# Prune backups older than 30 days
find $BACKUP_DIR -name "gari_auth_backup_*.db.gz" -mtime +30 -delete
```
Make executable: `sudo chmod +x /etc/cron.daily/gari_auth_backup`.
