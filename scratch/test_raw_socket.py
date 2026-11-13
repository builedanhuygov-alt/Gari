import socket
import ssl
import time

t0 = time.time()
sock = socket.create_connection(('gari-team.vercel.app', 443), timeout=10)
t_tcp = time.time()
ctx = ssl.create_default_context()
ctx.set_alpn_protocols(['http/1.1'])
ssock = ctx.wrap_socket(sock, server_hostname='gari-team.vercel.app')
t_tls = time.time()

print(f"TCP connect: {(t_tcp - t0)*1000:.1f}ms")
print(f"TLS handshake: {(t_tls - t_tcp)*1000:.1f}ms")

body = b'{"email":"test@gari.vn","password":"test"}'
req = (
    b"POST /api/auth/login HTTP/1.1\r\n"
    b"Host: gari-team.vercel.app\r\n"
    b"User-Agent: Mozilla/5.0\r\n"
    b"Content-Type: application/json\r\n"
    b"Content-Length: " + str(len(body)).encode() + b"\r\n"
    b"Connection: close\r\n\r\n" + body
)

ssock.sendall(req)
t_sent = time.time()
print(f"Request sent: {(t_sent - t_tls)*1000:.1f}ms")
print("Waiting for server response...")

try:
    ssock.settimeout(12)
    resp = ssock.recv(4096)
    t_recv = time.time()
    print(f"Received {len(resp)} bytes after {(t_recv - t_sent):.2f}s: {resp[:200]}")
except socket.timeout:
    print(f"Socket timed out after {(time.time() - t_sent):.2f}s with NO BYTES from Vercel!")
except Exception as e:
    print(f"Socket error after {(time.time() - t_sent):.2f}s: {e}")
finally:
    ssock.close()

