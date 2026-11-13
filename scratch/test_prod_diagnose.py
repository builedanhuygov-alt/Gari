import urllib.request
import urllib.error

url = 'https://gari-team.vercel.app/api/plant/diagnose'
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
with open('tests/fixtures/test_leaf.jpg', 'rb') as f:
    img_data = f.read()

part1 = f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="test_leaf.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode('utf-8')
part2 = f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="mode"\r\n\r\nauto_standard\r\n--{boundary}--\r\n'.encode('utf-8')
body = part1 + img_data + part2

req = urllib.request.Request(
    url,
    data=body,
    headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'User-Agent': 'Mozilla/5.0'
    },
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print('HTTP Status:', resp.status)
        print('Headers:', dict(resp.headers))
        print('Body:', resp.read().decode('utf-8', errors='ignore'))
except urllib.error.HTTPError as e:
    print('HTTPError Status:', e.code)
    print('HTTPError Headers:', dict(e.headers))
    print('HTTPError Body:', e.read().decode('utf-8', errors='ignore'))
except Exception as e:
    print('Error:', type(e), e)

