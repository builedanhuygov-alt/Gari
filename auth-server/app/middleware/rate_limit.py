"""
GARI Auth Server 1.0 — Hybrid In-Memory & Distributed Database Rate Limiter
Supports both single-instance in-memory tracking and distributed multi-instance serverless enforcement.
"""
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional
from starlette.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import settings

logger = logging.getLogger(__name__)


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
        Fast in-memory sliding window check.
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

    def is_allowed_distributed(
        self,
        db: Session,
        action: str,
        ip: str,
        identifier: Optional[str] = None,
        max_requests: int = 5,
        window_seconds: int = 300
    ) -> Tuple[bool, int]:
        """
        Distributed rate limit check using PostgreSQL/database security events.
        Ensures rate limits hold across multiple stateless/serverless instances.
        """
        # Fast path: check in-memory first
        mem_key = f"{action}:{ip}:{identifier or ''}"
        mem_allowed, mem_retry = self.is_allowed(mem_key, max_requests, window_seconds)
        if not mem_allowed:
            return False, mem_retry

        # Distributed check against database security_events
        try:
            from app.models.security_event import SecurityEvent
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)

            if action == "register":
                event_types = ["REGISTER_SUCCESS", "REGISTER_RATE_LIMITED", "REGISTER_CAPACITY_REJECTED"]
                query = db.query(SecurityEvent).filter(
                    SecurityEvent.ip_address == ip,
                    SecurityEvent.event_type.in_(event_types),
                    SecurityEvent.created_at >= cutoff
                )
            elif action == "login":
                event_types = ["LOGIN_FAILED", "LOGIN_RATE_LIMITED"]
                filters = [SecurityEvent.ip_address == ip]
                if identifier:
                    filters.append(SecurityEvent.sanitized_metadata.contains(identifier))

                query = db.query(SecurityEvent).filter(
                    SecurityEvent.event_type.in_(event_types),
                    SecurityEvent.created_at >= cutoff,
                    or_(*filters)
                )
            else:
                return True, 0

            events = query.order_by(SecurityEvent.created_at.asc()).all()
            if len(events) >= max_requests:
                oldest = events[0]
                now_ts = datetime.now(timezone.utc).timestamp()
                oldest_ts = oldest.created_at.timestamp() if oldest.created_at else now_ts
                retry_after = max(1, int(oldest_ts + window_seconds - now_ts))
                return False, retry_after

            return True, 0

        except Exception as e:
            logger.warning("Database rate limit check fallback to in-memory: %s", str(e))
            return True, 0

    def reset(self, key: str):
        """Resets rate limit for a key upon successful authentication."""
        if key in self._history:
            del self._history[key]


rate_limiter = RateLimiter()
