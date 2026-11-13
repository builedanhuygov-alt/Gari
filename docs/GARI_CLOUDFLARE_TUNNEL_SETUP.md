# GARI AgriTech AI Platform — Cloudflare Tunnel Architecture & Setup Guide

## 1. Overview

Cloudflare Tunnel provides encrypted, reverse-proxy connectivity between Cloudflare's global edge network and the self-hosted Windows backend (`127.0.0.1:8000`).

### Core Advantages:
1. **Zero Port Forwarding:** Router NAT and Windows Defender Firewall remain 100% closed to all inbound traffic.
2. **DDoS & WAF Protection:** All traffic passes through Cloudflare's edge before touching the Windows machine.
3. **Automated TLS:** End-to-end TLS encryption with certificates managed by Cloudflare.
4. **Header Transparency:** Cloudflare injects verified client headers (`CF-Connecting-IP`, `CF-Ray`) while forwarding to loopback.

---

## 2. Quick Tunnel vs. Named Tunnel Comparison

| Feature | Cloudflare Quick Tunnel (Current Dev/Preview) | Cloudflare Named Tunnel (Production Recommendation) |
| :--- | :--- | :--- |
| **Account Required** | No (Anonymous / Zero-Config) | Yes (Cloudflare Zero Trust free account) |
| **Domain** | Random subdomain `*.trycloudflare.com` | Custom domain (e.g., `api.gari.vn`) |
| **Persistence** | Changes upon each process restart | Static, persistent URL |
| **Configuration** | Command line flags only | `config.yml` or Cloudflare Dashboard |
| **SLA & Uptime** | Best-effort testing tier | High-availability production tier |
| **Best For** | Vercel Preview testing & local debugging | Long-term staging & production deployments |

---

## 3. Quick Tunnel Setup (Current Operational Mode)

The automated script `scripts/start_gari_tunnel.ps1` establishes an active Quick Tunnel:

```powershell
.\cloudflared.exe tunnel --url http://127.0.0.1:8000 --protocol http2 --no-autoupdate
```

### Operational Lifecycle:
1. `cloudflared.exe` initializes an outbound HTTP/2 multiplexed connection to Cloudflare edge edge servers (e.g., Singapore `sin`, Hong Kong `hkg`).
2. Cloudflare allocates an ephemeral URL (e.g., `https://implies-recognition-emails-medicaid.trycloudflare.com`).
3. The script extracts the URL, tests reachability, and saves it to `logs/gari_tunnel_url.txt`.
4. Any requests sent to this URL are routed over the encrypted outbound tunnel directly to `http://127.0.0.1:8000`.

---

## 4. Upgrading to a Persistent Named Tunnel (Production Step)

When transitioning from temporary Preview testing to a permanent domain, set up a Named Tunnel:

### Step 1: Authenticate cloudflared
```powershell
.\cloudflared.exe tunnel login
```
*A browser window will open to authenticate your Cloudflare account and select your domain.*

### Step 2: Create Named Tunnel
```powershell
.\cloudflared.exe tunnel create gari-backend-windows
```
*Outputs a Tunnel ID and creates a credentials file in `%USERPROFILE%\.cloudflared\<TUNNEL-ID>.json`.*

### Step 3: Configure Ingress Rules
Create `config.yml` in `%USERPROFILE%\.cloudflared\config.yml`:
```yaml
tunnel: <TUNNEL-ID>
credentials-file: C:\Users\<Username>\.cloudflared\<TUNNEL-ID>.json

ingress:
  - hostname: api.gari.vn
    service: http://127.0.0.1:8000
    originRequest:
      connectTimeout: 10s
      noTLSVerify: false
  - service: http_status:404
```

### Step 4: Route DNS Record
```powershell
.\cloudflared.exe tunnel route dns gari-backend-windows api.gari.vn
```

### Step 5: Install as Windows Service
To run continuously on Windows startup:
```powershell
.\cloudflared.exe service install
Start-Service cloudflared
```

---

## 5. Security & Isolation Controls

1. **Local Host Protection:** `cloudflared` strictly proxies to `http://127.0.0.1:8000`. Ingress rules reject any request targeting internal LAN IPs or management ports.
2. **No Secret Transmission in URLs:** All authentication uses standard HTTP headers (`Authorization: Bearer <session-token>`).
3. **Log Hygiene:** Request bodies containing credentials or image payloads are not logged to disk by `cloudflared`.

