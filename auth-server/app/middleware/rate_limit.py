"""
GARI Auth Server 1.0 — In-Memory Sliding Window Rate Limiter
"""
import time
from typing import Dict, List, Tuple
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.config import settings


def get_client_ip(request: Request) -> str:
    """Extracts client IP, respecting proxy headers if configured."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


class RateLimiter:
    def __init__(self):
        # Key: "action:identifier", Value: List of timestamps (floats)
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Returns (is_allowed, retry_after_seconds).
        """
        now = time.time()
        cutoff = now - window_seconds

        timestamps = self._history.get(key, [])
        # Prune old timestamps
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= max_requests:
            oldest = timestamps[0]
            retry_after = max(1, int(oldest + window_seconds - now))
            self._history[key] = timestamps
            return False, retry_after

        timestamps.append(now)
        self._history[key] = timestamps
        return True, 0

    def reset(self, key: str):
        """Resets rate limit for a key upon successful authentication."""
        if key in self._history:
            del self._history[key]


rate_limiter = RateLimiter()
