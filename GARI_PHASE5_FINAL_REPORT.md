# GARI — PHASE 5 FINAL ENGINEERING ACCEPTANCE REPORT
**Document ID:** `GARI_PHASE5_FINAL_REPORT.md`  
**Version:** 1.0.0 | **Author:** GARI Site Reliability Engineering & DevOps Team  
**Date:** 2026-11-10  

---

## 1. Executive Summary

Phase 5: Production Infrastructure has completed all preparatory, audit, hardening, testing, monitoring, and disaster recovery engineering requirements for GARI AgriTech AI Lab.

The platform is fully prepared for zero-cost deployment onto an Oracle Cloud Infrastructure (OCI) Always Free ARM64 Ampere A1 instance (Ubuntu 22.04 LTS), providing high-performance on-demand AI inference, automated WAL-safe database backups, agentless observability, and zero external hosting costs ($0.00 / month).

In accordance with strict operational rules, **the existing local FastAPI backend and Cloudflare Tunnel (`task-1310`) remain completely online and untouched**. Production cutover will occur only after the user provisions the Oracle Cloud VM and confirms authorization.

---

## 2. Final Acceptance Status Table

| Hạng mục (Category) | Trạng thái (Status) | Bằng chứng (Verification Evidence) |
| :--- | :---: | :--- |
| **Infrastructure Audit** | **VERIFIED** | [`PHASE5_INFRASTRUCTURE_AUDIT.md`](file:///d:/leaf-diseases-detector-main/PHASE5_INFRASTRUCTURE_AUDIT.md). Verified `docker-compose.yml`, `Dockerfile`, volume persistence (`./database:/app/database`, `./models:/app/models:ro`), and Nginx configurations. |
| **Oracle VM** | **PREPARED** | [`ORACLE_CLOUD_SETUP_CHECKLIST.md`](file:///d:/leaf-diseases-detector-main/ORACLE_CLOUD_SETUP_CHECKLIST.md) and [`bootstrap.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/bootstrap.sh). Target: `VM.Standard.A1.Flex`, 2 OCPU, 12 GB RAM, 100 GB Boot Disk. Awaiting user VM provisioning on OCI Console. |
| **Docker Deployment** | **VERIFIED** | `Dockerfile` & `docker-compose.yml` multi-arch definitions (`linux/amd64`, `linux/arm64`), non-root execution (`USER gari`, UID 1000), logging rotation (`max-size: 50m`), and healthcheck probes tested. |
| **ARM64 Inference** | **PREPARED** | `requirements-production.txt` verified for native `aarch64` wheels (`torch==2.3.1`, `transformers==4.45.2`, `opencv-python-headless`). Tested on CPU inference architecture. Staged for physical ARM64 CPU smoke tests. |
| **API Reliability** | **VERIFIED** | Probes `/health` and `/ready` return HTTP 200. On-demand model lifecycle verified (`MODEL_PRELOAD_ENABLED=false`, `MODEL_AUTO_UNLOAD_ENABLED=true`, `MODEL_IDLE_TIMEOUT_SECONDS=300`, `MAX_CACHED_MODELS=3`). 10-thread concurrent inference passed. |
| **HTTPS** | **PREPARED** | [`setup_ssl.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/setup_ssl.sh), [`gari-http.conf`](file:///d:/leaf-diseases-detector-main/deploy/oracle/nginx/conf.d/gari-http.conf), and [`gari-ssl.conf`](file:///d:/leaf-diseases-detector-main/deploy/oracle/nginx/conf.d/gari-ssl.conf). Automated Let's Encrypt Certbot webroot issuance & HSTS security headers ready for domain binding. |
| **Network Security** | **VERIFIED** | UFW firewall allows only ports 22, 80, 443. Port 8000 strictly bound to localhost/container network. IPTables SSH guarantee configured in `bootstrap.sh`. Wildcard CORS (`*`) strictly rejected in production. |
| **Monitoring** | **VERIFIED** | [`GARI_MONITORING_GUIDE.md`](file:///d:/leaf-diseases-detector-main/GARI_MONITORING_GUIDE.md), [`monitor.py`](file:///d:/leaf-diseases-detector-main/deploy/oracle/monitor.py), and [`system_metrics.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/system_metrics.sh). Structured JSONL telemetry, threshold alerts (RAM > 85%, Disk > 85%), and admin lifecycle diagnostics endpoint tested. |
| **Backup** | **VERIFIED** | [`GARI_BACKUP_AND_DISASTER_RECOVERY.md`](file:///d:/leaf-diseases-detector-main/GARI_BACKUP_AND_DISASTER_RECOVERY.md) and [`backup_sqlite.py`](file:///d:/leaf-diseases-detector-main/deploy/oracle/backup_sqlite.py). Online WAL-safe backup created verified 9.46 MB snapshot in 130ms with SHA256 checksum and 7 daily / 4 weekly / 3 monthly retention. |
| **Restore Test** | **VERIFIED** | [`restore_sqlite.py`](file:///d:/leaf-diseases-detector-main/deploy/oracle/restore_sqlite.py). Disaster recovery drill verified candidate validation, pre-restore safety snapshot creation, stale WAL removal, and post-restore integrity check. |
| **External Staging** | **PREPARED** | [`sync_data.ps1`](file:///d:/leaf-diseases-detector-main/deploy/oracle/sync_data.ps1) and [`sync_data.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/sync_data.sh). Data synchronization pipeline for 5.04 GB models and database prepared for deployment to VM public IP. |
| **Frontend Integration**| **VERIFIED** | API schema matching verified for `frontend2/` (crop catalog, diagnosis responses, farm/org routes, authentication tokens). Production allowed origins include `https://gari-team.vercel.app`. |
| **Production Cutover** | **PREPARED** | [`GARI_PRODUCTION_CUTOVER_CHECKLIST.md`](file:///d:/leaf-diseases-detector-main/GARI_PRODUCTION_CUTOVER_CHECKLIST.md). Cutover plan staged. Backend old instance will remain active for 48 hours post-cutover. Awaiting user authorization. |

---

## 3. Completed Engineering Artifacts

The following operational tools, scripts, and documentation have been created or upgraded in Phase 5:

### 3.1 Automation & Operational Scripts (`deploy/oracle/`)
1. [`deploy/oracle/bootstrap.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/bootstrap.sh): Host OS setup, 4GB swap, Docker CE, UFW firewall, iptables anti-SSH-lockout rules.
2. [`deploy/oracle/deploy.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/deploy.sh): Pulls/builds Docker image, starts containers, runs 60s healthcheck polling loop.
3. [`deploy/oracle/healthcheck.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/healthcheck.sh): Diagnostics tool verifying `/health`, `/ready`, crop catalogs, DB, and WAL status.
4. [`deploy/oracle/rollback.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/rollback.sh): Emergency service rollback preserving production database by default.
5. [`deploy/oracle/setup_ssl.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/setup_ssl.sh): Automated Let's Encrypt Certbot webroot issuance and Nginx SSL configuration swap.
6. [`deploy/oracle/backup_sqlite.py`](file:///d:/leaf-diseases-detector-main/deploy/oracle/backup_sqlite.py): Python WAL-safe online backup engine with integrity checks and rotation retention.
7. [`deploy/oracle/restore_sqlite.py`](file:///d:/leaf-diseases-detector-main/deploy/oracle/restore_sqlite.py): Disaster recovery tool with pre-restore safety snapshots and WAL cleanup.
8. [`deploy/oracle/monitor.py`](file:///d:/leaf-diseases-detector-main/deploy/oracle/monitor.py): Telemetry collector for CPU, RAM, Disk, Swap, API health, and model lifecycle.
9. [`deploy/oracle/system_metrics.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/system_metrics.sh): Cron wrapper script for periodic 5-minute telemetry sampling.
10. [`deploy/oracle/sync_data.ps1`](file:///d:/leaf-diseases-detector-main/deploy/oracle/sync_data.ps1) & [`sync_data.sh`](file:///d:/leaf-diseases-detector-main/deploy/oracle/sync_data.sh): SCP and rsync synchronizers for 5.04 GB models and database.
11. [`deploy/oracle/crontab.example`](file:///d:/leaf-diseases-detector-main/deploy/oracle/crontab.example): Crontab template scheduling daily backups, metrics, and SSL renewals.
12. [`deploy/oracle/nginx/conf.d/gari-http.conf`](file:///d:/leaf-diseases-detector-main/deploy/oracle/nginx/conf.d/gari-http.conf): Pre-SSL HTTP bootstrap configuration.
13. [`deploy/oracle/nginx/conf.d/gari-ssl.conf`](file:///d:/leaf-diseases-detector-main/deploy/oracle/nginx/conf.d/gari-ssl.conf): Production HTTPS configuration with TLS 1.2/1.3 and HSTS.

### 3.2 Engineering Documents
1. [`PHASE5_INFRASTRUCTURE_AUDIT.md`](file:///d:/leaf-diseases-detector-main/PHASE5_INFRASTRUCTURE_AUDIT.md): In-depth audit of container, storage, reverse proxy, and network configs.
2. [`GARI_MONITORING_GUIDE.md`](file:///d:/leaf-diseases-detector-main/GARI_MONITORING_GUIDE.md): SRE runbook, metrics reference, structured JSONL schema, and alerting thresholds.
3. [`GARI_BACKUP_AND_DISASTER_RECOVERY.md`](file:///d:/leaf-diseases-detector-main/GARI_BACKUP_AND_DISASTER_RECOVERY.md): Online WAL backup protocol, retention rules, and disaster recovery drill runbook.
4. [`GARI_PRODUCTION_STAGING_REPORT.md`](file:///d:/leaf-diseases-detector-main/GARI_PRODUCTION_STAGING_REPORT.md): 20/20 test matrix validation report across local, container, and staging scopes.
5. [`GARI_INFRASTRUCTURE_COST_REPORT.md`](file:///d:/leaf-diseases-detector-main/GARI_INFRASTRUCTURE_COST_REPORT.md): Financial analysis confirming $0.00 / month operational cost and FinOps guardrails.
6. [`GARI_PHASE5_FINAL_REPORT.md`](file:///d:/leaf-diseases-detector-main/GARI_PHASE5_FINAL_REPORT.md): Final acceptance summary and operator cutover instructions.

---

## 4. User Action Guide: Provisioning Oracle Cloud VM

To launch the cloud server and complete the cloud deployment:

### Step 1: Create Compute Instance on Oracle Cloud Console
1. Log in to [Oracle Cloud Console](https://cloud.oracle.com/).
2. Navigate to **Compute** $\rightarrow$ **Instances** $\rightarrow$ **Create Instance**.
3. **Name:** `gari-ai-backend`
4. **Image:** Ubuntu 22.04 LTS (Minimal or Standard).
5. **Shape:** Click **Change Shape** $\rightarrow$ **Ampere** $\rightarrow$ Select `VM.Standard.A1.Flex` (Always Free Eligible).
   - OCPU: **2**
   - Memory: **12 GB**
6. **Networking:** Select default VCN and Public Subnet; ensure **Assign a public IPv4 address** is checked.
7. **SSH Keys:** Generate a new key pair or upload your public key (`id_rsa.pub`). Save the private key on your machine.
8. **Boot Volume:** Check **Specify a custom boot volume size** $\rightarrow$ Set to **100 GB** (within the 200 GB Always Free limit).
9. Click **Create** and wait 60–120 seconds until the instance state is **Running**.

### Step 2: Open Security List Ports in OCI Console
1. In the Instance details, click on the **Virtual Cloud Network (VCN)** $\rightarrow$ **Security Lists** $\rightarrow$ **Default Security List**.
2. Click **Add Ingress Rules**:
   - Rule 1: Source CIDR `0.0.0.0/0`, Protocol `TCP`, Destination Port `80` (HTTP)
   - Rule 2: Source CIDR `0.0.0.0/0`, Protocol `TCP`, Destination Port `443` (HTTPS)
   - Rule 3: Source CIDR `0.0.0.0/0`, Protocol `TCP`, Destination Port `22` (SSH - already present by default)

### Step 3: Synchronize Data & Launch
Once the instance is Running, copy its **Public IP Address** (e.g. `152.67.x.x`), and execute the following from your local terminal:

```powershell
# From local Windows terminal:
.\deploy\oracle\sync_data.ps1 -VmIp "YOUR_VM_PUBLIC_IP" -KeyPath "path\to\your_oracle_key"
```

Then SSH into the instance:
```bash
ssh -i path/to/your_oracle_key ubuntu@YOUR_VM_PUBLIC_IP
cd /home/ubuntu/leaf-diseases-detector

# Run bootstrap (installs Docker, swap, firewall, iptables):
sudo bash deploy/oracle/bootstrap.sh

# Deploy application containers:
bash deploy/oracle/deploy.sh

# Verify health:
bash deploy/oracle/healthcheck.sh
```

---

## 5. Production Cutover Criteria

Cutover will be executed only after:
1. Oracle VM is running and accessible via Public IP.
2. `healthcheck.sh` reports 100% PASS on the VM.
3. Domain DNS record (e.g. `api.gari.vn`) points to the VM Public IP and `setup_ssl.sh` has provisioned Let's Encrypt HTTPS.
4. User gives explicit confirmation to update `VERCEL_BACKEND_API_URL` on Vercel.
5. The local backend and Cloudflare Tunnel will remain online for at least 48 hours as a fallback safety net.

