import sys
import io
import time
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import requests
import gari_auth
import gari_database

BASE_URL = "http://127.0.0.1:8000"

def get_auth_token():
    # User 1 is existing registered user
    token = gari_auth.create_session(1)
    return token

def test_upload(image_path: Path, mode: str = "auto_standard", crop: str = None, token: str = None):
    url = f"{BASE_URL}/api/plant/diagnose"
    with open(image_path, "rb") as f:
        img_bytes = f.read()
    files = {"image": (image_path.name, img_bytes, "image/jpeg")}
    data = {"mode": mode}
    if crop:
        data["crop"] = crop
    
    headers = {"Authorization": f"Bearer {token}"}
    
    t0 = time.perf_counter()
    resp = requests.post(url, files=files, data=data, headers=headers, timeout=30)
    dur = (time.perf_counter() - t0) * 1000.0
    
    return resp.status_code, resp.json() if resp.status_code == 200 or resp.headers.get("content-type") == "application/json" else resp.text, dur

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    token = get_auth_token()
    
    print("=" * 70)
    print("TESTING LIVE HTTP API: POST /api/plant/diagnose")
    print("=" * 70)
    
    # 1. Diseased Leaf: Tomato Leaf Mold
    pv_mold = list(Path("data/organized/PlantVillage/Tomato_Leaf_Mold").glob("*.JPG"))[0]
    status, res, dur = test_upload(pv_mold, token=token)
    print(f"\n1. Diseased Leaf [Tomato Leaf Mold] ({pv_mold.name}):")
    print(f"   HTTP Status: {status} | Latency: {dur:.1f}ms")
    print(f"   Success: {res.get('success')} | Status: {res.get('status')}")
    print(f"   Validation: {res.get('validation')}")
    print(f"   Crop: {res.get('crop_name_vi')} | Disease: {res.get('disease_name_vi')} | Conf: {res.get('confidence')}")
    assert res.get("success") is True, f"Failed on valid diseased leaf: {res}"
    assert res.get("validation", {}).get("status") == "LEAF_VALID", f"Expected LEAF_VALID: {res}"
    assert res.get("crop_id") == "tomato"

    time.sleep(3.2) # debounce protection

    # 2. Diseased Leaf: Tomato Early Blight
    pv_eb = list(Path("data/organized/PlantVillage/Tomato_Early_blight").glob("*.JPG"))[0]
    status, res, dur = test_upload(pv_eb, token=token)
    print(f"\n2. Diseased Leaf [Tomato Early Blight] ({pv_eb.name}):")
    print(f"   HTTP Status: {status} | Latency: {dur:.1f}ms")
    print(f"   Success: {res.get('success')} | Status: {res.get('status')}")
    print(f"   Validation: {res.get('validation')}")
    print(f"   Crop: {res.get('crop_name_vi')} | Disease: {res.get('disease_name_vi')} | Conf: {res.get('confidence')}")
    assert res.get("success") is True, f"Failed on valid diseased leaf: {res}"
    assert res.get("disease_id") == "Early_blight"

    time.sleep(3.2)

    # 3. Healthy Leaf: Tomato Healthy
    pv_h = list(Path("data/organized/PlantVillage/Tomato_healthy").glob("*.JPG"))[0]
    status, res, dur = test_upload(pv_h, token=token)
    print(f"\n3. Healthy Leaf [Tomato Healthy] ({pv_h.name}):")
    print(f"   HTTP Status: {status} | Latency: {dur:.1f}ms")
    print(f"   Success: {res.get('success')} | Status: {res.get('status')}")
    print(f"   Validation: {res.get('validation')}")
    print(f"   Crop: {res.get('crop_name_vi')} | Disease: {res.get('disease_name_vi')} | Conf: {res.get('confidence')}")
    assert res.get("success") is True
    assert res.get("is_healthy") is True

    time.sleep(3.2)

    # 4. Non-Leaf: Blue object
    p_non = Path("data/test_samples_17/5_non_leaf.jpg")
    status, res, dur = test_upload(p_non, token=token)
    print(f"\n4. Non-Leaf [Blue object] (5_non_leaf.jpg):")
    print(f"   HTTP Status: {status} | Latency: {dur:.1f}ms")
    print(f"   Success: {res.get('success')} | Status: {res.get('status')}")
    print(f"   Validation: {res.get('validation')}")
    assert res.get("success") is False
    assert res.get("validation", {}).get("status") == "NOT_A_LEAF"

    time.sleep(3.2)

    # 5. Non-Leaf: Human Face
    p_face = Path("data/test_samples_17/6_human_face.jpg")
    status, res, dur = test_upload(p_face, token=token)
    print(f"\n5. Non-Leaf [Human face] (6_human_face.jpg):")
    print(f"   HTTP Status: {status} | Latency: {dur:.1f}ms")
    print(f"   Success: {res.get('success')} | Status: {res.get('status')}")
    print(f"   Validation: {res.get('validation')}")
    assert res.get("success") is False
    assert res.get("validation", {}).get("status") == "NOT_A_LEAF"

    time.sleep(3.2)

    # 6. Non-Leaf: Animal
    p_animal = Path("data/test_samples_17/7_animal.jpg")
    status, res, dur = test_upload(p_animal, token=token)
    print(f"\n6. Non-Leaf [Animal] (7_animal.jpg):")
    print(f"   HTTP Status: {status} | Latency: {dur:.1f}ms")
    print(f"   Success: {res.get('success')} | Status: {res.get('status')}")
    print(f"   Validation: {res.get('validation')}")
    assert res.get("success") is False
    assert res.get("validation", {}).get("status") == "NOT_A_LEAF"

    time.sleep(3.2)

    # 7. Non-Leaf: General Object
    p_obj = Path("data/test_samples_17/8_general_object.jpg")
    status, res, dur = test_upload(p_obj, token=token)
    print(f"\n7. Non-Leaf [General Object] (8_general_object.jpg):")
    print(f"   HTTP Status: {status} | Latency: {dur:.1f}ms")
    print(f"   Success: {res.get('success')} | Status: {res.get('status')}")
    print(f"   Validation: {res.get('validation')}")
    assert res.get("success") is False
    assert res.get("validation", {}).get("status") == "NOT_A_LEAF"

    time.sleep(3.2)

    # 8. Blurry leaf
    p_blur = Path("data/test_samples_17/9_blurry_leaf.jpg")
    status, res, dur = test_upload(p_blur, token=token)
    print(f"\n8. Low Quality [Blurry Leaf] (9_blurry_leaf.jpg):")
    print(f"   HTTP Status: {status} | Latency: {dur:.1f}ms")
    print(f"   Success: {res.get('success')} | Status: {res.get('status')}")
    print(f"   Validation: {res.get('validation')}")
    assert res.get("success") is False
    assert res.get("validation", {}).get("status") == "IMAGE_QUALITY_LOW"

    time.sleep(3.2)

    # 9. Low Light leaf
    p_dark = Path("data/test_samples_17/10_low_light_leaf.jpg")
    status, res, dur = test_upload(p_dark, token=token)
    print(f"\n9. Low Quality [Low Light Leaf] (10_low_light_leaf.jpg):")
    print(f"   HTTP Status: {status} | Latency: {dur:.1f}ms")
    print(f"   Success: {res.get('success')} | Status: {res.get('status')}")
    print(f"   Validation: {res.get('validation')}")
    assert res.get("success") is False
    assert res.get("validation", {}).get("status") == "IMAGE_QUALITY_LOW"

    print("\n" + "=" * 70)
    print("ALL 9 HTTP API INTEGRATION TESTS PASSED PERFECTLY!")
    print("=" * 70)
