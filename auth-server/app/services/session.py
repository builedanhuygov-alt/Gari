"""
GARI Auth Server 1.0 — Session Management Service
"""
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.session import SessionModel
from app.models.user import User
from app.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a raw session token for storage and lookup."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_session_token() -> Tuple[str, str]:
    """Generates a cryptographically secure random session token and its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_token(raw_token)


def create_session(db: Session, user_id: int, remember_me: bool = False) -> Tuple[SessionModel, str]:
    """
    Creates an active session for the given user and returns (SessionModel, raw_token).
    The raw token is only returned once and NEVER stored plaintext.
    """
    raw_token, token_hash = generate_session_token()
    now = utcnow()

    # Determine expiration
    ttl_seconds = settings.SESSION_MAX_LIFETIME_SECONDS if remember_me else settings.SESSION_TTL_SECONDS
    expires_at = now + timedelta(seconds=ttl_seconds)

    session_record = SessionModel(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_at=now,
        last_seen_at=now,
        revoked_at=None
    )
    db.add(session_record)
    db.commit()
    db.refresh(session_record)
    return session_record, raw_token


def validate_session(db: Session, raw_token: str) -> Tuple[Optional[User], Optional[SessionModel]]:
    """
    Validates a raw session token:
    1. Looks up SHA-256 hash.
    2. Checks revocation status.
    3. Checks idle timeout and maximum lifetime.
    4. Checks account active status.
    5. Slides session expiration forward if valid.
    """
    if not raw_token:
        return None, None

    token_hash = hash_token(raw_token)
    session_record = db.query(SessionModel).filter(SessionModel.token_hash == token_hash).first()

    if not session_record:
        return None, None

    # Check revocation
    if session_record.revoked_at is not None:
        return None, None

    now = utcnow()

    # Ensure timestamps have timezone info for comparison
    expires_at = session_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    created_at = session_record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    # Check expiration
    if expires_at <= now:
        return None, None

    # Check absolute max lifetime
    max_lifetime = created_at + timedelta(seconds=settings.SESSION_MAX_LIFETIME_SECONDS)
    if now >= max_lifetime:
        session_record.revoked_at = now
        db.commit()
        return None, None

    # Verify user exists and is active
    user = db.query(User).filter(User.id == session_record.user_id).first()
    if not user or not user.is_active:
        return None, None

    # Slide expiration window up to max_lifetime
    new_expires = min(now + timedelta(seconds=settings.SESSION_TTL_SECONDS), max_lifetime)
    session_record.last_seen_at = now
    session_record.expires_at = new_expires
    db.commit()

    return user, session_record


def revoke_session(db: Session, raw_token: str) -> bool:
    """Revokes a specific session token."""
    if not raw_token:
        return False
    token_hash = hash_token(raw_token)
    session_record = db.query(SessionModel).filter(
        SessionModel.token_hash == token_hash,
        SessionModel.revoked_at.is_(None)
    ).first()

    if session_record:
        session_record.revoked_at = utcnow()
        db.commit()
        return True
    return False


def revoke_all_user_sessions(db: Session, user_id: int, except_raw_token: Optional[str] = None) -> int:
    """Revokes all active sessions for a user, optionally keeping the current one active."""
    query = db.query(SessionModel).filter(
        SessionModel.user_id == user_id,
        SessionModel.revoked_at.is_(None)
    )
    if except_raw_token:
        keep_hash = hash_token(except_raw_token)
        query = query.filter(SessionModel.token_hash != keep_hash)

    sessions = query.all()
    now = utcnow()
    count = 0
    for s in sessions:
        s.revoked_at = now
        count += 1
    db.commit()
    return count
