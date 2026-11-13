import os
import datetime
import subprocess

auth_files = [
    "frontend2/register.html",
    "frontend2/login.html",
    "frontend2/forgot-password.html",
    "frontend2/firebase-client.js",
    "frontend2/app.js",
    "frontend2/host-login.html",
    "frontend2/host.html",
    "api/[...path].js",
    "frontend2/api/[...path].js",
    "api/auth/firebase-config.js",
    "frontend2/api/auth/firebase-config.js",
    "gari_auth.py",
    "gari_firebase.py"
]

print("=== TIMESTAMPS FOR AUTH-RELATED FILES ===")
for f in auth_files:
    if os.path.exists(f):
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(f))
        ct = datetime.datetime.fromtimestamp(os.path.getctime(f))
        sz = os.path.getsize(f)
        print(f"{f:38s} | MTIME: {mt.strftime('%Y-%m-%d %H:%M:%S')} | CTIME: {ct.strftime('%Y-%m-%d %H:%M:%S')} | {sz:7d} B")

