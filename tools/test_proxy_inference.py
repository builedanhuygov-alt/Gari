import urllib.request
import time
import json

SERVER_URL = "http://localhost:5173"
TOMATO_IMG = r"D:\leaf-diseases-detector-main\data\organized\Tomato\Tomato_Bacterial_spot\00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG"

boundary = "----WebKitFormBoundaryGari" + hex(int(time.time()))[2:]
body = bytearray()
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"crop\"\r\n\r\nTomato\r\n".encode("utf-8"))
body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"leaf.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".encode("utf-8"))
with open(TOMATO_IMG, "rb") as f:
    body.extend(f.read())
body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

req = urllib.request.Request(f"{SERVER_URL}/api/predict", data=bytes(body), headers={
    "Content-Type": f"multipart/form-data; boundary={boundary}",
    "Content-Length": str(len(body))
})

with urllib.request.urlopen(req, timeout=30) as resp:
    print("HTTP Status:", resp.status)
    res = json.loads(resp.read().decode("utf-8"))
    print("Prediction:", res.get("predicted_disease"))
    print("Confidence:", res.get("confidence"))
    print("Model:", res.get("model", {}).get("name"))
    print("Arch:", res.get("model", {}).get("arch"))
    print("Latency:", res.get("inference_time_ms"), "ms")
    print("Top 3:", [p.get("label") or p.get("disease") for p in res.get("top_predictions", [])])
