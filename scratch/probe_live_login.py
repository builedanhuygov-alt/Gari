import urllib.request
import urllib.error
import time
import json

url = "https://gari-team.vercel.app/api/auth/login"
payload = json.dumps({"email": "probe_user@test.invalid", "password": "dummy_password"}).encode("utf-8")
headers = {
    "Content-Type": "application/json",
    "User-Agent": "GARI-Diagnostic/1.0"
}

req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
start = time.time()
print(f"[*] Sending POST request to {url}...")
try:
    with urllib.request.urlopen(req, timeout=15) as res:
        elapsed = round(time.time() - start, 3)
        body = res.read().decode("utf-8", errors="replace")
        print(f"[+] Status: {res.status} | Elapsed: {elapsed}s | Body: {body[:300]}")
except urllib.error.HTTPError as he:
    elapsed = round(time.time() - start, 3)
    body = he.read().decode("utf-8", errors="replace")
    print(f"[-] HTTPError: {he.code} | Elapsed: {elapsed}s | Body: {body[:300]}")
except Exception as e:
    elapsed = round(time.time() - start, 3)
    print(f"[!] Error: {type(e).__name__}: {e} | Elapsed: {elapsed}s")
