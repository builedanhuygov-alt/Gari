#!/usr/bin/env python3
"""
GARI AgriTech AI Lab — Lightweight Observability & Health Daemon
Path: deploy/oracle/monitor.py

Monitors:
1. Host Resources: CPU %, RAM %, Swap %, Disk % (via psutil)
2. Backend API: /health status, HTTP latency (ms)
3. Model Lifecycle: Active loaded models, active inferences, process RSS
4. Alerts: Emits warnings if RAM > 85%, Disk > 85%, or API fails
"""

import argparse
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import psutil
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [GARI-MONITOR] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("gari_monitor")

def get_system_metrics() -> Dict[str, Any]:
    """Capture OS-level CPU, RAM, Swap, and Disk utilization."""
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/") if os.name != "nt" else psutil.disk_usage("C:\\")

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram": {
            "total_mb": round(vm.total / (1024 * 1024), 1),
            "used_mb": round(vm.used / (1024 * 1024), 1),
            "available_mb": round(vm.available / (1024 * 1024), 1),
            "percent": vm.percent,
        },
        "swap": {
            "total_mb": round(swap.total / (1024 * 1024), 1),
            "used_mb": round(swap.used / (1024 * 1024), 1),
            "percent": swap.percent,
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": disk.percent,
        }
    }

def probe_api_health(target_url: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Probe /health endpoint and measure latency."""
    health_url = f"{target_url.rstrip('/')}/health"
    start = time.perf_counter()
    status_code = 0
    body = {}
    is_healthy = False

    try:
        req = urllib.request.Request(health_url, headers={"User-Agent": "Gari-Monitor/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            status_code = resp.getcode()
            raw = resp.read().decode("utf-8")
            body = json.loads(raw)
            is_healthy = (status_code == 200 and body.get("status") in ("healthy", "ok"))
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        body = {"error": str(exc)}

    return {
        "endpoint": health_url,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "is_healthy": is_healthy,
        "response": body
    }

def probe_lifecycle_diagnostics(target_url: str, admin_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Query model lifecycle state if admin token is available."""
    if not admin_token:
        return None
    url = f"{target_url.rstrip('/')}/api/admin/models/lifecycle"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Gari-Monitor/1.0",
                "Authorization": f"Bearer {admin_token}"
            }
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

def check_alerts(metrics: Dict[str, Any], health: Dict[str, Any]) -> list:
    """Evaluate metric thresholds against alert rules."""
    alerts = []
    if not health.get("is_healthy"):
        alerts.append(f"CRITICAL: API is unhealthy! HTTP {health.get('status_code')}: {health.get('response')}")

    ram_pct = metrics["ram"]["percent"]
    if ram_pct > 85.0:
        alerts.append(f"WARNING: High RAM utilization: {ram_pct}% (>85%)")

    disk_pct = metrics["disk"]["percent"]
    if disk_pct > 85.0:
        alerts.append(f"WARNING: High Disk utilization: {disk_pct}% (>85%)")

    cpu_pct = metrics["cpu_percent"]
    if cpu_pct > 95.0:
        alerts.append(f"WARNING: High CPU utilization: {cpu_pct}% (>95%)")

    return alerts

def main():
    parser = argparse.ArgumentParser(description="GARI Lightweight Observability Monitor")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL of GARI backend")
    parser.add_argument("--token", default=os.getenv("ADMIN_BEARER_TOKEN", ""), help="Admin bearer token for diagnostics")
    parser.add_argument("--log-file", default="logs/monitoring.jsonl", help="Log output file for time-series aggregation")
    parser.add_argument("--loop", type=int, default=0, help="Interval in seconds for continuous monitoring (0 for single run)")
    args = parser.parse_args()

    log_path = Path(args.log_file).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def run_check():
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        sys_metrics = get_system_metrics()
        api_health = probe_api_health(args.url)
        lifecycle = probe_lifecycle_diagnostics(args.url, args.token)
        alerts = check_alerts(sys_metrics, api_health)

        record = {
            "timestamp": now,
            "system": sys_metrics,
            "api": api_health,
            "lifecycle": lifecycle,
            "alerts": alerts
        }

        # Append to jsonl
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        # Console feedback
        status_sym = "✓" if api_health["is_healthy"] else "✗"
        ram_p = sys_metrics["ram"]["percent"]
        cpu_p = sys_metrics["cpu_percent"]
        lat = api_health["latency_ms"]
        logger.info(f"[{status_sym}] API Latency: {lat}ms | CPU: {cpu_p}% | RAM: {ram_p}% | Disk: {sys_metrics['disk']['percent']}%")

        if alerts:
            for a in alerts:
                logger.warning(f"ALERT TRIGGERED: {a}")

    if args.loop > 0:
        logger.info(f"Starting continuous monitoring daemon (interval: {args.loop}s)...")
        while True:
            try:
                run_check()
                time.sleep(args.loop)
            except KeyboardInterrupt:
                logger.info("Monitoring terminated by user.")
                break
            except Exception as exc:
                logger.error(f"Error in monitor loop: {exc}")
                time.sleep(args.loop)
    else:
        run_check()

if __name__ == "__main__":
    main()

