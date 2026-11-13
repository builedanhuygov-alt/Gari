import sys, os
sys.path.insert(0, os.path.abspath("."))
import time
from PIL import Image
import gari_inference_engine

engine = gari_inference_engine.engine

crops = ["coffee", "pepper", "rice", "durian", "tomato", "chili", "maize"]
img = Image.open("tests/fixtures/test_leaf.jpg")

print("=== TESTING 7 PRIORITY CROPS INFERENCE & GRAD-CAM ===")
for crop_id in crops:
    t0 = time.time()
    res = engine.predict(img, crop_id=crop_id, mode="manual")
    elapsed = round((time.time() - t0) * 1000, 1)
    status = res.get("status")
    crop = res.get("crop")
    pred = res.get("prediction")
    conf = res.get("confidence")
    loc_status = res.get("localization_status")
    has_cam = res.get("has_attention_map")
    regions = len(res.get("regions", []))
    print(f"[{crop_id.upper()}] {elapsed}ms | status={status} | crop={crop} | pred={pred} (conf={conf}) | loc_status={loc_status} | has_cam={has_cam} | regions={regions}")
