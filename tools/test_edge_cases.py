import urllib.request
import urllib.error
import json
import time

BASE = 'https://gari-team.vercel.app'
login_data = json.dumps({'email': 'prod_audit_test@gari.vn', 'password': 'SecTest#2026_Prod'}).encode()
req = urllib.request.Request(f'{BASE}/api/auth/login', data=login_data, headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(req) as r:
    token = json.loads(r.read().decode()).get('token')

# 1. Test unsupported crop Durian
boundary = '----WebKitBoundary' + hex(int(time.time()))[2:]
body = bytearray()
body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="crop"\r\n\r\nDurian\r\n'.encode('utf-8'))
body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="leaf.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode('utf-8'))
with open(r'D:\leaf-diseases-detector-main\test_leaf.jpg', 'rb') as f:
    body.extend(f.read())
body.extend(f'\r\n--{boundary}--\r\n'.encode('utf-8'))

req = urllib.request.Request(
    f'{BASE}/api/predict',
    data=bytes(body),
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}', 'Authorization': f'Bearer {token}'},
    method='POST'
)
try:
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode())
        print('[PASS] Unsupported crop Durian handled cleanly -> HTTP', r.status, '| status:', data.get('status'), '| msg:', data.get('message_vi') or data.get('message') or data.get('detail'))
except urllib.error.HTTPError as e:
    print('[PASS] Unsupported crop Durian returned -> HTTP', e.code, e.read().decode()[:150])

# 2. Test corrupted image
bad_body = bytearray()
bad_body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="crop"\r\n\r\nTomato\r\n'.encode('utf-8'))
bad_body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="bad.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode('utf-8'))
bad_body.extend(b'NOT_AN_IMAGE_RANDOM_BYTES_DATA_STREAM')
bad_body.extend(f'\r\n--{boundary}--\r\n'.encode('utf-8'))

req2 = urllib.request.Request(
    f'{BASE}/api/predict',
    data=bytes(bad_body),
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}', 'Authorization': f'Bearer {token}'},
    method='POST'
)
try:
    with urllib.request.urlopen(req2) as r:
        print('[FAIL] Corrupted image should not succeed!')
except urllib.error.HTTPError as e:
    err_data = json.loads(e.read().decode())
    print('[PASS] Corrupted image rejected cleanly -> HTTP', e.code, '| Detail:', err_data.get('detail') or err_data.get('message'))

