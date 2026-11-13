import urllib.request
import json
import time
import os

BASE = 'https://gari-team.vercel.app'
IMG_PATH = r'D:\leaf-diseases-detector-main\data\organized\Tomato\Tomato_Bacterial_spot\00416648-be6e-4bd4-bc8d-82f43f8a7240___GCREC_Bact.Sp 3110.JPG'

if not os.path.exists(IMG_PATH):
    IMG_PATH = r'D:\leaf-diseases-detector-main\test_leaf.jpg'

# 1. Login to get token
login_data = json.dumps({'email': 'prod_audit_test@gari.vn', 'password': 'SecTest#2026_Prod'}).encode()
try:
    req = urllib.request.Request(f'{BASE}/api/auth/login', data=login_data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req) as r:
        token = json.loads(r.read().decode()).get('token')
except:
    # Register if not yet registered
    reg_data = json.dumps({'email': 'prod_audit_test@gari.vn', 'password': 'SecTest#2026_Prod', 'full_name': 'Tester'}).encode()
    req = urllib.request.Request(f'{BASE}/api/auth/register', data=reg_data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req) as r:
        token = json.loads(r.read().decode()).get('token')

print(f"Obtained Bearer token: {token[:15]}...")

with open(IMG_PATH, 'rb') as f:
    img_bytes = f.read()

boundary = '----WebKitFormBoundaryGariTest' + hex(int(time.time()))[2:]
body = bytearray()
body.extend(f'--{boundary}\r\n'.encode('utf-8'))
body.extend(b'Content-Disposition: form-data; name="crop"\r\n\r\n')
body.extend(b'Tomato\r\n')
body.extend(f'--{boundary}\r\n'.encode('utf-8'))
body.extend(b'Content-Disposition: form-data; name="image"; filename="leaf.jpg"\r\n')
body.extend(b'Content-Type: image/jpeg\r\n\r\n')
body.extend(img_bytes)
body.extend(b'\r\n')
body.extend(f'--{boundary}--\r\n'.encode('utf-8'))

req = urllib.request.Request(
    f'{BASE}/api/predict',
    data=bytes(body),
    headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body)),
        'Authorization': f'Bearer {token}'
    },
    method='POST'
)

with urllib.request.urlopen(req, timeout=40) as r:
    res = json.loads(r.read().decode())
    print('[PASS] Production Inference HTTP', r.status)
    print('  Predicted Disease:', res.get('predicted_disease'))
    print('  Confidence:', res.get('confidence'), '%')
    print('  Inference Time:', res.get('inference_time_ms'), 'ms')
    print('  Model:', res.get('model', {}).get('name'), '| Arch:', res.get('model', {}).get('arch'))
    print('  Top Predictions:', [f"{p.get('label') or p.get('disease')} ({p.get('confidence')}%)" for p in res.get('top_predictions', [])])
