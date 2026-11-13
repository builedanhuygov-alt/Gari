import sys
from pathlib import Path
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import gari_auth
token = gari_auth.create_session(user_id=1)
headers = {"Authorization": f"Bearer {token}"}

def test_it(p, mode="manual", crop="coffee"):
    files = {"image": open(p, "rb")}
    r = requests.post("http://localhost:8000/api/plant/diagnose", headers=headers, files=files, data={"mode": mode, "crop": crop})
    data = r.json()
    st = data.get("status")
    pred = data.get("prediction")
    val = data.get("validation", {}).get("status")
    msg = data.get("message")
    print(f"{p.name} [{mode}, {crop}]: HTTP {r.status_code} | status={st} | val={val} | pred={pred} | msg={msg}")

p_coffee = ROOT_DIR / "data" / "field_dataset" / "images" / "field_1793374087037_1a78f2_coffee.jpg"
if p_coffee.exists():
    test_it(p_coffee, "manual", "coffee")

p_tomato = next((ROOT_DIR / "data" / "organized" / "PlantVillage" / "Tomato_Bacterial_spot").glob("*.JPG"))
test_it(p_tomato, "manual", "tomato")
test_it(p_tomato, "auto_standard", None)
