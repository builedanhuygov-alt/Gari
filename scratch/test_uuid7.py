import time
import os
import uuid

def generate_uuid7() -> uuid.UUID:
    ns = time.time_ns()
    ms = ns // 1_000_000
    rand_bytes = os.urandom(10)
    b = bytearray(16)
    b[0:6] = ms.to_bytes(6, byteorder="big")
    b[6] = 0x70 | (rand_bytes[0] & 0x0f)
    b[7] = rand_bytes[1]
    b[8] = 0x80 | (rand_bytes[2] & 0x3f)
    b[9:16] = rand_bytes[3:10]
    return uuid.UUID(bytes=bytes(b))

u1 = generate_uuid7()
time.sleep(0.005)
u2 = generate_uuid7()

print(f"u1: {u1} (ver={u1.version}, var={u1.variant})")
print(f"u2: {u2} (ver={u2.version}, var={u2.variant})")
print(f"Time ordered: {str(u1) < str(u2)}")

