# GARI AgriTech AI Platform — Windows Self-Hosted Backend Server Setup

## 1. Overview & System Topology

The GARI AgriTech AI Platform utilizes a hybrid architecture:
- **Frontend / Edge Delivery:** Vercel Global Edge Network (`https://gari-team.vercel.app` / Preview environments).
- **Backend Application Core:** Self-hosted FastAPI runtime running locally on the Windows host machine (`D:\leaf-diseases-detector-main`).
- **Database Engine:** Local SQLite storage (`database\disease_detector.db`).
- **AI Inference Engine:** Local PyTorch neural models (`models\` directory) running with in-memory pre-warming.
- **Edge Connectivity:** Cloudflare Tunnel outbound daemon (`cloudflared.exe`) bridging public HTTPS requests to `http://127.0.0.1:8000` without inbound port forwarding or router exposure.

```
+-------------------------------------------------------------+
|                     Client Browser                          |
+-------------------------------------------------------------+
                              |
                              v HTTPS
+-------------------------------------------------------------+
|                 Vercel Gateway Serverless                   |
|       (Buffered Proxy, Fail-Closed 503 on Backend Outage)    |
+-------------------------------------------------------------+
                              |
                              v HTTPS (Encrypted Outbound Tunnel)
+-------------------------------------------------------------+
|                  Cloudflare Edge Network                    |
+-------------------------------------------------------------+
                              |
                              v Encrypted Tunnel (HTTP/2 / QUIC)
+-------------------------------------------------------------+
|                 cloudflared.exe (Windows Host)              |
+-------------------------------------------------------------+
                              |
                              v HTTP (Loopback Only)
+-------------------------------------------------------------+
|                 127.0.0.1:8000 (FastAPI Backend)            |
|                 - gari_auth.py (Sessions & RBAC)            |
|                 - disease_detector.db (SQLite)              |
|                 - PyTorch AI Model Store (Preloaded)        |
+-------------------------------------------------------------+
```

---

## 2. Host Prerequisites & Environment

1. **Operating System:** Windows 10/11 64-bit.
2. **Python Environment:** Python 3.11+ located in `.venv\Scripts\python.exe`.
3. **Core Dependencies:**
   - FastAPI, Uvicorn, Pydantic
   - PyTorch (`torch`, `torchvision`, `torchaudio`)
   - OpenCV, Pillow, NumPy
   - SQLite3
4. **Cloudflare Tunnel Binary:**
   - `cloudflared.exe` located at `D:\leaf-diseases-detector-main\cloudflared.exe` (Version 2026.10.7+).

---

## 3. Network & Security Isolation

- **Loopback Binding Strict Enforcement:**
  FastAPI is configured to listen strictly on `127.0.0.1:8000`. It is never bound to `0.0.0.0` or public network adapters.
- **Firewall Policy:**
  No inbound ports (e.g. 8000, 80, 443) are opened on Windows Defender Firewall or router NAT. The host initiates all communication as an outbound TCP/UDP tunnel to Cloudflare Edge.
- **Zero-PHP Policy:**
  Strictly zero PHP files, runtimes, fixtures, or extensions are installed or executed.
- **Windows Defender Compatibility:**
  No security exclusions or bypasses are applied. All binaries and scripts operate within standard non-elevated user permissions.

---

## 4. Directory Layout

```
D:\leaf-diseases-detector-main\
├── api_server.py                 # Primary FastAPI application entry point
├── gari_auth.py                  # Sole authentication and session authority
├── cloudflared.exe               # Cloudflare Tunnel outbound agent
├── database\
│   └── disease_detector.db       # Primary SQLite production database
├── models\                       # 53 AI vision model packages
├── scripts\
│   ├── start_gari_backend.ps1    # Automated FastAPI launcher with pre-warming
│   ├── start_gari_tunnel.ps1     # Cloudflare Tunnel launcher & URL extractor
│   └── check_gari_backend.ps1    # End-to-end health and connectivity inspector
├── logs\
│   ├── uvicorn_backend.log       # Local FastAPI stdout/stderr log
│   ├── cloudflared.log           # Cloudflare Tunnel connection events
│   ├── cloudflared.pid           # Active Tunnel PID
│   └── gari_tunnel_url.txt       # Active public tunnel endpoint
└── tests\
    └── test_windows_self_hosted_setup.py # 10-point end-to-end verification suite
```

---

## 5. Startup Procedure

Follow the two-step startup sequence:

### Step 1: Start FastAPI Backend
Open PowerShell 7 (`pwsh`) and run:
```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\start_gari_backend.ps1
```
*Verification:*
- Inspects port 8000.
- Activates model pre-warming (`MODEL_PRELOAD_ENABLED=true`).
- Confirms `http://127.0.0.1:8000/api/health` returns `status: healthy`.

### Step 2: Establish Cloudflare Tunnel
In a new or background shell, run:
```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\start_gari_tunnel.ps1
```
*Verification:*
- Connects securely to Cloudflare Edge over HTTP/2.
- Exports the active HTTPS endpoint to `logs\gari_tunnel_url.txt`.
- Tests reachability from the public Internet.

### Step 3: Run Full Health Inspector
Verify the entire chain with:
```powershell
pwsh -ExecutionPolicy Bypass -File .\scripts\check_gari_backend.ps1
```

