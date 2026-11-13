"""
GARI Auth Server 1.0 — Security Event Audit Logging
"""
import json
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from app.models.security_event import SecurityEvent


def sanitize_dict(data: Optional[Dict[str, Any]]) -> Optional[str]:
    if not data:
        return None
    sensitive_keys = {"password", "token", "password_hash", "new_password", "current_password", "cookie", "authorization"}
    clean = {}
    for k, v in data.items():
        if any(s in k.lower() for s in sensitive_keys):
            clean[k] = "[REDACTED]"
        else:
            clean[k] = v
    try:
        return json.dumps(clean, ensure_ascii=False)
    except Exception:
        return None


def log_security_event(
    db: Session,
    event_type: str,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> SecurityEvent:
    """Logs a sanitized security event to the audit trail."""
    sanitized_str = sanitize_dict(metadata)
    event = SecurityEvent(
        event_type=event_type,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:490],
        sanitized_metadata=sanitized_str
    )
    db.add(event)
    db.commit()
    return event
