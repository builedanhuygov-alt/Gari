"""
GARI Auth Server 1.0 — Argon2id Password Service
"""
import argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

# Production-grade OWASP recommended parameters for Argon2id
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB RAM
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=argon2.Type.ID
)


def hash_password(plain_password: str) -> str:
    """Hashes a plaintext password using Argon2id with high-entropy salt."""
    if not plain_password:
        raise ValueError("Mật khẩu không được để trống.")
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against an Argon2id hash in constant time."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    except Exception:
        return False


def check_needs_rehash(hashed_password: str) -> bool:
    """Checks if the stored hash was created with older, weaker parameters."""
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except Exception:
        return True
