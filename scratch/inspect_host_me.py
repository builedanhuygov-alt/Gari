import sys
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gari_auth
import gari_database

# Check user 1 admin status
with gari_database.get_connection() as conn:
    c = conn.cursor()
    c.execute("SELECT id, email, is_admin, account_type FROM users WHERE id = 1")
    print("User 1 in DB:", c.fetchone())

token = gari_auth.create_session(user_id=1)
session = requests.Session()
session.headers.update({"Authorization": f"Bearer {token}"})
session.cookies.set("auth_token", token)

resp = session.get("http://127.0.0.1:8000/api/host/me")
print("Response /api/host/me status:", resp.status_code)
print("Response body:", resp.json())
