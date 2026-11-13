import sys
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gari_auth

token = gari_auth.create_session(user_id=1)
session = requests.Session()
session.headers.update({"Authorization": f"Bearer {token}"})
session.cookies.set("auth_token", token)

resp = session.get("http://127.0.0.1:8000/api/host/overview")
print("Status:", resp.status_code)
print("Keys in /api/host/overview:", list(resp.json().keys()))
print("Overview sample:", {k: resp.json()[k] for k in list(resp.json().keys())[:6]})
