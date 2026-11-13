import sys
from pathlib import Path
import urllib.request
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gari_auth

BASE_URL = "http://127.0.0.1:8000"

# Create valid session for user 1 (buidanhuy555@gmail.com)
token = gari_auth.create_session(user_id=1)
print(f"Created session token: {token[:12]}...")

headers = {
    "Authorization": f"Bearer {token}",
    "Cookie": f"auth_token={token}"
}

print("1. Testing GET /api/plots (with auth)...")
req1 = urllib.request.Request(f"{BASE_URL}/api/plots", headers=headers)
with urllib.request.urlopen(req1) as resp:
    res = json.loads(resp.read().decode())
    print(" -> Plots count:", res.get("total"), [p["plot_name"] for p in res.get("plots", [])[:3]])

# Get plot 13 which has timeline events
target_plot_id = 13

print(f"\n2. Testing GET /api/plots/{target_plot_id}/timeline (with auth)...")
req2 = urllib.request.Request(f"{BASE_URL}/api/plots/{target_plot_id}/timeline", headers=headers)
with urllib.request.urlopen(req2) as resp:
    res = json.loads(resp.read().decode())
    events = res.get("timeline", {}).get("events", [])
    print(f" -> Timeline events for Plot {target_plot_id}:", len(events))
    for e in events:
        print(f"    * [{e['monitoring_status']}] {e['notes'][:50]}...")

print("\nPlots and Timeline API verified with full authorization!")
