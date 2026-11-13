import urllib.request
import urllib.error
import json
import ssl

ctx = ssl.create_default_context()

BASE = "https://gari-team.vercel.app"
endpoints = [
    ("GET", "/api/health", None),
    ("GET", "/api/auth/firebase-config", None),
    ("GET", "/api/user/profile", None),
    ("GET", "/api/monitoring", None),
    ("GET", "/api/notifications", None),
    ("GET", "/api/supported-crops", None),
    ("POST", "/api/auth/provider-lookup", json.dumps({"email": "test@gari.vn"}).encode()),
    ("POST", "/api/auth/login", json.dumps({"email": "test@gari.vn", "password": "test"}).encode()),
]

print("Probing https://gari-team.vercel.app...")
for method, path, body in endpoints:
    req = urllib.request.Request(BASE + path, data=body, method=method)
    req.add_header("User-Agent", "Mozilla/5.0")
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as res:
            hdrs = dict(res.headers)
            content = res.read().decode("utf-8", errors="replace")
            vid = hdrs.get("x-vercel-id", "none")
            print(f"[{res.status}] {method} {path} -> {content[:120]} | vercel-id: {vid}")
    except urllib.error.HTTPError as e:
        hdrs = dict(e.headers)
        content = e.read().decode("utf-8", errors="replace")
        vid = hdrs.get("x-vercel-id", "none")
        print(f"[{e.code}] {method} {path} -> {content[:120]} | vercel-id: {vid}")
    except Exception as exc:
        print(f"[ERR] {method} {path} -> {exc}")

