import io
import sys
sys.path.insert(0, ".")
from PIL import Image
from fastapi.testclient import TestClient
from api_server import app
from tests.test_module_02_leaf_intelligence import create_auth_headers, get_test_leaf_bytes

test_leaf_bytes = get_test_leaf_bytes()

with TestClient(app) as client:
    headers = create_auth_headers(client, "debug_test")
    
    # Test 6 debug
    files = {"file": ("test_leaf.jpg", test_leaf_bytes, "image/jpeg")}
    data = {"crop": "durian", "include_attention": "false", "include_overlay": "false"}
    res6 = client.post("/api/predict", headers=headers, files=files, data=data)
    print("Test 6 status:", res6.status_code)
    print("Test 6 response:", res6.json())
    
    # Test 8 debug
    files = {"file": ("test_leaf.jpg", test_leaf_bytes, "image/jpeg")}
    data = {"crop": "tomato", "include_attention": "false"}
    res8 = client.post("/api/predict", headers=headers, files=files, data=data)
    print("Test 8 status:", res8.status_code)
    print("Test 8 response is_verified:", res8.json().get("is_verified"))
    print("Test 8 response diagnosis_type:", res8.json().get("diagnosis_type"))
    print("Test 8 response disclaimer_vi:", res8.json().get("disclaimer_vi"))
