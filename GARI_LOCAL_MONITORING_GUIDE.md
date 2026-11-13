# GARI — SELF-HOSTED MONITORING & OBSERVABILITY GUIDE
**Document ID:** `GARI_LOCAL_MONITORING_GUIDE.md`  
**Tooling:** Native PowerShell + Python + Structured JSONL (Zero External Dependencies)  
**Date:** 2026-11-10  

---

## 1. Zero-Cost Observability Architecture

To prevent unnecessary resource overhead and avoid third-party SaaS subscription costs, GARI implements a lightweight, native Windows observability pipeline:

1. **Native OS Instrumentation:** Measures host CPU, physical RAM, disk utilization, and process working set via PowerShell CIM (`Win32_OperatingSystem`, `Win32_Processor`).
2. **Dual-Endpoint Probe:** Probes both the local loopback origin (`http://127.0.0.1:8000/health`) and the public Cloudflare Tunnel gateway (`https://ist-towards-exclude-said.trycloudflare.com/health`) to distinguish between local backend crashes and internet/tunnel outages.
3. **Structured JSONL Telemetry:** Telemetry snapshots are appended as compressed JSON lines into `logs/local_monitoring.jsonl` for easy parsing.
4. **Zero Heavy Daemons:** Eliminates resource-heavy telemetry suites like Prometheus, Grafana, Datadog, or ElasticSearch.

---

## 2. Using the Local Monitoring Tool (`scripts/gari_monitor.ps1`)

### 2.1 Single Health Snapshot
To perform a single instant diagnostic check from your terminal:
```powershell
.\scripts\gari_monitor.ps1
```

**Example Console Output:**
```
[✓ Local: 146ms] [✓ Tunnel: 1429ms] | CPU: 33% | RAM: 86.5% (13909.2/16087.9 MB) | Backend RSS: 197.3 MB
```

### 2.2 Continuous Monitoring Loop
To keep an active telemetry dashboard running in a dedicated PowerShell window:
```powershell
.\scripts\gari_monitor.ps1 -LoopIntervalSeconds 30
```
This polls the local origin and public tunnel every 30 seconds, outputting color-coded green/yellow status lines and recording history to disk.

---

## 3. JSONL Telemetry Schema Specification

Every snapshot appended to `logs/local_monitoring.jsonl` adheres to this standard schema:

```json
{
  "timestamp": "2026-11-10T14:44:34.5886072Z",
  "system": {
    "cpu_percent": 33.0,
    "ram": {
      "total_mb": 16087.9,
      "used_mb": 13909.2,
      "free_mb": 2178.7,
      "percent": 86.5
    },
    "disk": {
      "total_gb": 195.31,
      "free_gb": 118.1,
      "percent": 39.5
    }
  },
  "backend": {
    "running": true,
    "pid": 3488,
    "working_set_mb": 197.3,
    "local_healthy": true,
    "latency_ms": 146
  },
  "tunnel": {
    "running": true,
    "public_healthy": true,
    "tunnel_url": "https://ist-towards-exclude-said.trycloudflare.com",
    "latency_ms": 1429
  },
  "database": {
    "db_size_mb": 9.46,
    "wal_size_kb": 0.0,
    "wal_active": true
  }
}
```

---

## 4. Querying AI Model Lifecycle Diagnostics

To inspect in-memory model slots, idle durations, and loaded weights directly from the FastAPI backend:

```powershell
# Using the administrative endpoint:
$token = "YOUR_ADMIN_SESSION_TOKEN"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/admin/models/lifecycle" -Headers @{ Authorization = "Bearer $token" } | ConvertTo-Json -Depth 4
```

**Returned Diagnostic Fields:**
- `active_models_count`: Number of model weights currently resident in RAM.
- `models.<crop>.state`: `UNLOADED`, `LOADING`, `READY`, `INFERENCE_ACTIVE`, or `UNLOADING`.
- `models.<crop>.active_requests`: Active forward pass reference counter.
- `models.<crop>.seconds_since_last_used`: Time elapsed since last request (compared against `300s` idle limit).

---

## 5. Setting Up as a Windows Background Task (Optional)

If you wish to collect continuous telemetry in the background without keeping a terminal open:

```powershell
$action = New-ScheduledTaskAction -Execute "pwsh.exe" -Argument "-NoProfile -WindowStyle Hidden -File `"$PWD\scripts\gari_monitor.ps1`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "GARI_Telemetry_Monitor" -Action $action -Trigger $trigger -Settings $settings -User "$env:USERNAME"
```

