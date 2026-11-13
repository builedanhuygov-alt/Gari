# GARI — CLOUDFLARE TUNNEL OPERATION & RELIABILITY GUIDE
**Document ID:** `GARI_CLOUDFLARE_TUNNEL_GUIDE.md`  
**Architecture:** Zero-Cost Cloudflare Tunnel Integration  
**Date:** 2026-11-10 | **Target:** Windows 11 Localhost Origin  

---

## 1. Current Tunnel Status & Topology

GARI utilizes **Cloudflare Tunnel (`cloudflared.exe`)** to expose the local FastAPI backend to the public internet and Vercel frontend without opening inbound firewall ports, configuring router NAT/Port-Forwarding, or obtaining a static public IP from your ISP.

### Active Runtime Status
- **Tunnel Type:** Cloudflare Quick Tunnel (Ephemeral `trycloudflare.com`)
- **Daemon Process:** `cloudflared.exe` (PID: 20464, Running as background task `task-1310`)
- **Local Origin:** `http://127.0.0.1:8000`
- **Active Public URL:** `https://ist-towards-exclude-said.trycloudflare.com`
- **Protocol:** Encrypted QUIC over UDP / HTTP2 fallback
- **Health Verification:** Verified responding with HTTP 200 `{"status":"healthy"}`.

---

## 2. Quick Tunnel vs. Named Tunnel (Cost & Stability Comparison)

| Attribute | Quick Tunnel (Current) | Cloudflare Named Tunnel (Recommended Permanent) |
| :--- | :--- | :--- |
| **Cost** | **$0.00 / month (0 VND)** | **$0.00 / month (0 VND)** (Cloudflare Zero Trust Free) |
| **Account Requirement** | None (Runs anonymously) | Free Cloudflare Account + Domain DNS |
| **Domain Name** | Random subdomain (`*.trycloudflare.com`) | Fixed custom domain (e.g. `api.gari.vn`) |
| **URL Stability** | **Changes on daemon restart** | **100% Fixed & Permanent** |
| **Windows Service** | Manual script or Task Scheduler | Native `cloudflared service install` |
| **DDoS Protection** | Cloudflare Standard Shield | Cloudflare Enterprise-grade WAF & Rate Limiting |

> [!WARNING]
> **Ephemeral URL Behavior**:
> Whenever `cloudflared.exe` restarts or your computer reboots, Cloudflare Quick Tunnel will assign a **new random URL**.
> You must **never hardcode** the Quick Tunnel URL into frontend source code. Always configure it via Vercel environment variables or dynamic proxy rules.

---

## 3. How to Upgrade to a Permanent Free Named Tunnel

To eliminate URL changes permanently without spending money:

### Step 1: Create a Free Cloudflare Account
1. Register at [dash.cloudflare.com](https://dash.cloudflare.com/).
2. Add a free domain or existing domain to Cloudflare DNS.

### Step 2: Authenticate cloudflared on Local Workstation
In your local terminal:
```powershell
.\cloudflared.exe tunnel login
```
This opens a browser window to authorize your domain.

### Step 3: Create the Named Tunnel
```powershell
.\cloudflared.exe tunnel create gari-local-tunnel
```
This generates a unique tunnel UUID and credentials JSON file at `%USERPROFILE%\.cloudflared\<UUID>.json`.

### Step 4: Create Configuration File (`config.yml`)
Create a file named `config.yml` in `%USERPROFILE%\.cloudflared\config.yml`:
```yaml
tunnel: <YOUR_TUNNEL_UUID>
credentials-file: C:\Users\<Username>\.cloudflared\<YOUR_TUNNEL_UUID>.json

ingress:
  - hostname: api.gari.vn
    service: http://127.0.0.1:8000
    originRequest:
      connectTimeout: 30s
      noTLSVerify: false
  - service: http_status:404
```

### Step 5: Route DNS to Tunnel
```powershell
.\cloudflared.exe tunnel route dns gari-local-tunnel api.gari.vn
```

### Step 6: Install as a Persistent Windows Service
```powershell
.\cloudflared.exe service install
Start-Service cloudflared
```
Once installed as a Windows Service, the tunnel automatically starts at Windows boot, reconnects silently upon Wi-Fi resumption, and maintains a **permanent static URL** (`https://api.gari.vn`) forever for 0 VND.

---

## 4. Connection Resilience & Auto-Reconnect Handling

The Cloudflare daemon includes native resilience mechanisms:
1. **Exponential Backoff:** If the local FastAPI backend is temporarily restarting, `cloudflared` buffers pending TCP streams and retries connection every 1 to 5 seconds.
2. **Multi-PoP Mesh:** Maintains simultaneous connections to at least 4 Cloudflare edge points-of-presence (PoPs, e.g. Singapore, Hong Kong). If an ISP transit route degrades, traffic automatically fails over to the next PoP in milliseconds.
3. **Keep-Alive Heartbeats:** Emits heartbeats every 5 seconds. If the host Wi-Fi drops and reconnects, `cloudflared` automatically restores the tunnel session without restarting.

---

## 5. Troubleshooting & Diagnostics

- **Check Tunnel Process:**
  ```powershell
  Get-Process cloudflared
  ```
- **Inspect Listening Connection on Origin:**
  ```powershell
  Get-NetTCPConnection -LocalPort 8000 -State Listen
  ```
- **Test Public Tunnel Endpoint:**
  ```powershell
  curl.exe -s https://ist-towards-exclude-said.trycloudflare.com/health
  ```
- **Restart Quick Tunnel (Manual fallback):**
  ```powershell
  .\cloudflared.exe tunnel --url http://127.0.0.1:8000
  ```

