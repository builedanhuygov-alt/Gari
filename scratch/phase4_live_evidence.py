import urllib.request
import urllib.error
import time
import socket
import json

def test_endpoint(name, url, method="GET", data=None, timeout=5):
    start = time.time()
    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={"User-Agent": "GARI-Diagnostic/1.0", "Content-Type": "application/json"} if data else {"User-Agent": "GARI-Diagnostic/1.0"},
            method=method
        )
        with urllib.request.urlopen(req, timeout=timeout) as res:
            elapsed = round(time.time() - start, 3)
            body = res.read().decode("utf-8", errors="replace")
            return {
                "name": name,
                "url": url,
                "status": res.status,
                "elapsed": elapsed,
                "result": "SUCCESS",
                "snippet": body[:120].strip()
            }
    except urllib.error.HTTPError as he:
        elapsed = round(time.time() - start, 3)
        body = he.read().decode("utf-8", errors="replace")
        return {
            "name": name,
            "url": url,
            "status": he.code,
            "elapsed": elapsed,
            "result": f"HTTPError {he.code}",
            "snippet": body[:120].strip()
        }
    except urllib.error.URLError as ue:
        elapsed = round(time.time() - start, 3)
        return {
            "name": name,
            "url": url,
            "status": "FAIL",
            "elapsed": elapsed,
            "result": f"URLError: {ue.reason}",
            "snippet": ""
        }
    except socket.timeout:
        elapsed = round(time.time() - start, 3)
        return {
            "name": name,
            "url": url,
            "status": "TIMEOUT",
            "elapsed": elapsed,
            "result": "Socket Timeout",
            "snippet": ""
        }
    except Exception as e:
        elapsed = round(time.time() - start, 3)
        return {
            "name": name,
            "url": url,
            "status": "ERROR",
            "elapsed": elapsed,
            "result": f"{type(e).__name__}: {e}",
            "snippet": ""
        }

endpoints = [
    ("Local FastAPI Health", "http://127.0.0.1:8000/health", "GET", None, 3),
    ("Local FastAPI API Health", "http://127.0.0.1:8000/api/health", "GET", None, 3),
    ("Cloudflare Tunnel 1 (logs)", "https://implies-recognition-emails-medicaid.trycloudflare.com/health", "GET", None, 3),
    ("Cloudflare Tunnel 2 (guide)", "https://ist-towards-exclude-said.trycloudflare.com/health", "GET", None, 3),
    ("Cloudflare Tunnel 3 (cloudflared.log)", "https://cats-lang-glory-snow.trycloudflare.com/health", "GET", None, 3),
    ("Vercel Gateway Health", "https://gari-team.vercel.app/api/health", "GET", None, 5),
    ("Vercel Firebase Config", "https://gari-team.vercel.app/api/auth/firebase-config", "GET", None, 5),
    ("Vercel Upstream Proxy (GET ready)", "https://gari-team.vercel.app/api/ready", "GET", None, 5),
    ("Vercel Frontend Predict HTML", "https://gari-team.vercel.app/frontend2/predict", "GET", None, 5),
    ("Vercel Frontend Firebase Client JS", "https://gari-team.vercel.app/frontend2/firebase-client.js", "GET", None, 5),
    ("Vercel Login POST (Safe Dummy Probe)", "https://gari-team.vercel.app/api/auth/login", "POST", json.dumps({"email":"probe_only@test.invalid","password":"dummy"}).encode("utf-8"), 8)
]

print("=== GARI PHASE 4 LIVE EVIDENCE AUDIT ===")
for name, url, method, data, timeout in endpoints:
    r = test_endpoint(name, url, method, data, timeout)
    snippet = r['snippet'].encode('ascii', 'backslashreplace').decode('ascii')
    print(f"[{r['status']}] {r['name']} ({r['elapsed']}s) -> {r['result']} | {snippet}")
