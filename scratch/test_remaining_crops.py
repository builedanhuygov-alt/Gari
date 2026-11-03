import requests
import sys

sys.stdout.reconfigure(encoding="utf-8")

crops_to_test = ["pepper", "rice", "maize"]

for crop in crops_to_test:
    with open("test_leaf.jpg", "rb") as f:
        r = requests.post(
            "http://127.0.0.1:8000/api/plant/diagnose",
            files={"image": ("leaf.jpg", f, "image/jpeg")},
            data={"mode": "manual", "crop": crop},
            timeout=60
        )
        res = r.json()
        print(f"CROP: {crop:8} | Status: {res.get('status')} | Disease: {res.get('disease_name_vi')} | Conf: {res.get('confidence')} | Model: {res.get('model_name')}")
