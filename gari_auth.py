"""
GARI AI LAB — Authentication & Application Security Layer (gari_auth.py)
Provides:
- Industry-standard Bcrypt password hashing (OWASP recommended)
- Secure session token management & HttpOnly cookie support
- In-memory rate limiting against brute-force attacks
- Strict email & credential input validation
- FastAPI dependencies for authenticated routes & user scoping
"""

import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Union

import bcrypt
import jwt
from jwt import PyJWKClient
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status

import gari_database

logger = logging.getLogger("gari_auth")

# Supabase Auth Configuration (Asymmetric RS256/ES256 Verification via JWKS)
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_JWKS_URL = os.getenv("SUPABASE_JWKS_URL") or (f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else "")
SUPABASE_EXPECTED_AUDIENCE = "authenticated"
SUPABASE_EXPECTED_ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else ""

_jwks_client: Optional[PyJWKClient] = None

def get_jwks_client() -> Optional[PyJWKClient]:
    """Retrieve or initialize singleton JWKS client with 1-hour cache lifetime."""
    global _jwks_client
    if not SUPABASE_JWKS_URL:
        return None
    if _jwks_client is None:
        try:
            _jwks_client = PyJWKClient(SUPABASE_JWKS_URL, cache_keys=True, lifespan=3600)
        except Exception as e:
            logger.warning("Could not initialize JWKS client for %s: %s", SUPABASE_JWKS_URL, e)
    return _jwks_client

# Session validity duration: 7 days default, 30 days if remember_me
SESSION_DURATION_DAYS = 7
REMEMBER_ME_DURATION_DAYS = 30

# In-memory rate limiter: tracks (ip, email) -> list of failure timestamps
# Max 5 failed attempts within 300 seconds (5 minutes)
_FAILED_ATTEMPTS: Dict[str, list] = {}
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 300

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# -----------------------------------------------------------------------------
# Canonical Single Active Account Types
# -----------------------------------------------------------------------------
ACCOUNT_TYPE_FARMER = "farmer"
ACCOUNT_TYPE_COOPERATIVE = "cooperative"
ACCOUNT_TYPE_EXPERT = "expert"
ACCOUNT_TYPE_ENTERPRISE = "enterprise"

VALID_ACCOUNT_TYPES = {
    ACCOUNT_TYPE_FARMER,
    ACCOUNT_TYPE_COOPERATIVE,
    ACCOUNT_TYPE_EXPERT,
    ACCOUNT_TYPE_ENTERPRISE,
}

ACCOUNT_TYPE_CONFIG = {
    ACCOUNT_TYPE_FARMER: {
        "key": ACCOUNT_TYPE_FARMER,
        "label": "Nông Hộ Cá Thể",
        "description": "Dành cho nông dân cá thể, chủ ruộng và người làm vườn gia đình."
    },
    ACCOUNT_TYPE_COOPERATIVE: {
        "key": ACCOUNT_TYPE_COOPERATIVE,
        "label": "Hợp Tác Xã",
        "description": "Dành cho Hợp tác xã nông nghiệp, ban quản lý vùng trồng tập trung."
    },
    ACCOUNT_TYPE_EXPERT: {
        "key": ACCOUNT_TYPE_EXPERT,
        "label": "Chuyên Gia BVTV",
        "description": "Dành cho kỹ sư nông học, chuyên viên khuyến nông và chẩn đoán bệnh cây."
    },
    ACCOUNT_TYPE_ENTERPRISE: {
        "key": ACCOUNT_TYPE_ENTERPRISE,
        "label": "Doanh Nghiệp",
        "description": "Dành cho doanh nghiệp chế biến xuất khẩu, chuỗi cung ứng vật tư BVTV."
    }
}

ACCOUNT_TYPE_NORMALIZATION = {
    "farmer": ACCOUNT_TYPE_FARMER,
    "nông hộ": ACCOUNT_TYPE_FARMER,
    "nong ho": ACCOUNT_TYPE_FARMER,
    "nông hộ cá thể": ACCOUNT_TYPE_FARMER,
    "cooperative": ACCOUNT_TYPE_COOPERATIVE,
    "hợp tác xã": ACCOUNT_TYPE_COOPERATIVE,
    "hop tac xa": ACCOUNT_TYPE_COOPERATIVE,
    "trang trại": ACCOUNT_TYPE_COOPERATIVE,
    "expert": ACCOUNT_TYPE_EXPERT,
    "chuyên gia": ACCOUNT_TYPE_EXPERT,
    "chuyên gia bvtv": ACCOUNT_TYPE_EXPERT,
    "đơn vị dịch vụ nông nghiệp": ACCOUNT_TYPE_EXPERT,
    "don vi dich vu nong nghiep": ACCOUNT_TYPE_EXPERT,
    "agronomist": ACCOUNT_TYPE_EXPERT,
    "enterprise": ACCOUNT_TYPE_ENTERPRISE,
    "doanh nghiệp": ACCOUNT_TYPE_ENTERPRISE,
    "doanh nghiep": ACCOUNT_TYPE_ENTERPRISE,
    "tập đoàn": ACCOUNT_TYPE_ENTERPRISE,
    "admin": ACCOUNT_TYPE_EXPERT,
    "platform admin": ACCOUNT_TYPE_EXPERT,
}


def normalize_account_type(raw_type: Optional[str]) -> Optional[str]:
    """Normalize any account type string to one of the 4 canonical slugs."""
    if not raw_type:
        return None
    cleaned = str(raw_type).strip().lower()
    return ACCOUNT_TYPE_NORMALIZATION.get(cleaned)


def get_account_type_display_name(account_type: Optional[str]) -> str:
    """Return Vietnamese display title for an account type slug."""
    norm = normalize_account_type(account_type)
    if norm and norm in ACCOUNT_TYPE_CONFIG:
        return ACCOUNT_TYPE_CONFIG[norm]["label"]
    return "Nông Hộ Cá Thể"



def hash_password(password: str) -> str:
    """Hash plaintext password with Bcrypt and a random salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against Bcrypt hash in constant time."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as exc:
        logger.warning("Password verification failed with exception: %s", exc)
        return False


def is_rate_limited(identifier: str) -> bool:
    """Check if the given identifier (IP or email) is temporarily locked."""
    now = time.time()
    attempts = _FAILED_ATTEMPTS.get(identifier, [])
    # Keep only attempts within the sliding window
    attempts = [t for t in attempts if now - t < RATE_LIMIT_WINDOW_SECONDS]
    _FAILED_ATTEMPTS[identifier] = attempts
    return len(attempts) >= RATE_LIMIT_MAX_ATTEMPTS


def record_failed_attempt(identifier: str) -> None:
    """Record a failed login attempt for rate limiting."""
    now = time.time()
    attempts = _FAILED_ATTEMPTS.get(identifier, [])
    attempts.append(now)
    _FAILED_ATTEMPTS[identifier] = attempts


def clear_failed_attempts(identifier: str) -> None:
    """Clear failed attempts upon successful login."""
    if identifier in _FAILED_ATTEMPTS:
        del _FAILED_ATTEMPTS[identifier]


def register_user(
    full_name: str,
    email: str,
    password: str,
    confirm_password: Optional[str] = None,
    account_type: str = "Nông hộ",
    phone: Optional[str] = None
) -> Dict[str, Any]:
    """Validate and register a new user account with secure password hashing."""
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    phone = (phone or "").strip() or None
    account_type = (account_type or "Nông hộ").strip()
    if confirm_password is None:
        confirm_password = password

    if not full_name or len(full_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Họ và tên không được để trống và phải có ít nhất 2 ký tự."
        )

    if not email or not EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Địa chỉ email không đúng định dạng."
        )

    if not password or len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu phải có độ dài tối thiểu 6 ký tự."
        )

    if password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Xác nhận mật khẩu không trùng khớp."
        )

    # Canonical Single Active Account Type
    canonical_account_type = normalize_account_type(account_type) or ACCOUNT_TYPE_FARMER

    # Check for existing email in database
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email này đã được đăng ký trong hệ thống. Vui lòng đăng nhập hoặc sử dụng email khác."
            )

        pwd_hash = hash_password(password)
        cursor.execute(
            """
            INSERT INTO users (full_name, name, email, password_hash, phone, account_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (full_name, full_name, email, pwd_hash, phone, canonical_account_type)
        )
        user_id = cursor.lastrowid

        # Audit initial account type creation
        cursor.execute(
            """
            INSERT INTO user_account_type_audit (user_id, previous_type, new_type, reason, changed_by_user_id)
            VALUES (?, NULL, ?, 'Đăng ký tài khoản mới', ?)
            """,
            (user_id, canonical_account_type, user_id)
        )

        # Security & Entitlement: New registrations always start on the 'free' tier.
        # User cannot self-elevate to VIP/Pro without admin assignment or pilot verification.
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT OR IGNORE INTO user_subscriptions (user_id, plan_id, status, billing_interval, start_date, notes)
            VALUES (?, 'free', 'active', 'daily', ?, 'Đăng ký tài khoản tiêu chuẩn')
            """,
            (user_id, now_iso)
        )
        conn.commit()

        cursor.execute("SELECT id, full_name, name, email, phone, account_type, created_at FROM users WHERE id = ?", (user_id,))
        new_user = dict(cursor.fetchone())
        # Ensure full_name is populated
        new_user["full_name"] = new_user.get("full_name") or new_user.get("name") or "Người dùng Gari"
        return new_user


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve user dictionary by ID."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, full_name, name, email, phone, address, province, avatar_url, bio,
                   account_type, is_admin, is_host_admin, is_expert, is_active, moderation_status,
                   feature_restrictions, moderation_reason, moderation_updated_at, firebase_uid, created_at, updated_at
            FROM users WHERE id = ?
            """,
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        res["is_expert"] = bool(res.get("is_expert"))
        return res


def authenticate_user(
    email: str,
    password: str,
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """Authenticate email & password, applying rate limiting and constant-time password check."""
    email = (email or "").strip().lower()
    client_key = f"{ip_address or '0.0.0.0'}:{email}"

    if is_rate_limited(client_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều lần thử đăng nhập không thành công. Vui lòng thử lại sau 5 phút."
        )

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, full_name, name, email, password_hash, phone, account_type, is_admin, is_host_admin, is_expert, is_active, moderation_status, feature_restrictions, moderation_reason, created_at FROM users WHERE LOWER(email) = LOWER(?)",
            (email,)
        )
        row = cursor.fetchone()

        if not row:
            record_failed_attempt(client_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email hoặc mật khẩu không chính xác."
            )

        user_data = dict(row)
        stored_hash = user_data.get("password_hash")

        if not stored_hash or not verify_password(password, stored_hash):
            record_failed_attempt(client_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email hoặc mật khẩu không chính xác."
            )

        if user_data.get("moderation_status") == "banned":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản này đã bị cấm vĩnh viễn do vi phạm chính sách sử dụng GARI."
            )

        if user_data.get("is_active") == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản này đã bị tạm khóa. Vui lòng liên hệ Quản trị viên máy chủ để được hỗ trợ."
            )

        # Clear failed attempts on successful login
        clear_failed_attempts(client_key)
        
        # Remove hash from returned dict
        del user_data["password_hash"]
        user_data["full_name"] = user_data.get("full_name") or user_data.get("name") or "Người dùng Gari"
        user_data["is_admin"] = bool(user_data.get("is_admin"))
        user_data["is_host_admin"] = bool(user_data.get("is_host_admin"))
        user_data["is_expert"] = bool(user_data.get("is_expert"))
        user_data["is_active"] = bool(user_data.get("is_active", 1))
        user_data["moderation_status"] = user_data.get("moderation_status") or "clean"
        user_data["feature_restrictions"] = user_data.get("feature_restrictions") or ""
        return user_data


def resolve_account_provider(email: str) -> Dict[str, Any]:
    """
    Resolve authentication provider for an email address.
    Used by client login router to direct authentication safely without bypassing passwords.
    Returns:
        - "sqlite_only" if account exists with password_hash and no firebase_uid
        - "firebase" if account exists with firebase_uid and no password_hash
        - "hybrid" if account has both
        - "unknown" if account does not exist in SQLite
    """
    email = (email or "").strip().lower()
    if not email:
        return {"exists": False, "provider": "unknown"}
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash, firebase_uid FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        row = cursor.fetchone()
        if not row:
            return {"exists": False, "provider": "unknown"}
        has_pwd = bool(row["password_hash"])
        has_fb = bool(row["firebase_uid"])
        if has_pwd and not has_fb:
            provider = "sqlite_only"
        elif has_fb and not has_pwd:
            provider = "firebase"
        elif has_pwd and has_fb:
            provider = "hybrid"
        else:
            provider = "unknown"
        return {"exists": True, "provider": provider}


def create_session(user_id: int, remember_me: bool = False, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> str:
    """Generate and persist a cryptographically secure session token in database."""
    token = secrets.token_urlsafe(36)
    days = REMEMBER_ME_DURATION_DAYS if remember_me else SESSION_DURATION_DAYS
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    expires_iso = expires_at.strftime("%Y-%m-%d %H:%M:%S")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO user_sessions (token, user_id, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token, user_id, expires_iso, ip_address, user_agent)
        )
        conn.commit()

    return token


def get_expected_issuer() -> Optional[str]:
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    return f"{url}/auth/v1" if url else None

def get_expected_audience() -> str:
    return os.getenv("SUPABASE_EXPECTED_AUDIENCE") or "authenticated"

def verify_supabase_jwt(token: str) -> Optional[Dict[str, Any]]:
    """
    Cryptographically verify Supabase asymmetric JWT using project JWKS public keys.
    Validates: signature, algorithm, audience ('authenticated'), issuer (if configured), expiration, subject (sub).
    Returns decoded token dictionary or None if invalid.
    """
    if not token or token.count(".") != 2:
        return None

    expected_iss = get_expected_issuer()
    expected_aud = get_expected_audience()

    # In production without JWKS configured, fail closed
    client = get_jwks_client()
    if not client:
        # Check if local test mock JWKS is provided via test fixture
        mock_secret = os.getenv("SUPABASE_TEST_JWT_SECRET")
        if mock_secret:
            try:
                return jwt.decode(
                    token,
                    mock_secret,
                    algorithms=["HS256", "RS256"],
                    audience=expected_aud,
                    issuer=expected_iss if expected_iss else None,
                    options={"require": ["exp", "sub", "aud"]}
                )
            except Exception as e:
                logger.warning("Mock Supabase JWT validation error: %s", e)
                return None

        app_env = os.getenv("APP_ENV", "development").lower()
        if app_env in ("production", "prod"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Dịch vụ xác thực Supabase chưa được cấu hình trên môi trường sản xuất."
            )
        return None

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256", "HS256"],
            audience=expected_aud,
            issuer=expected_iss if expected_iss else None,
            options={"require": ["exp", "sub", "aud"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Supabase JWT expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("Supabase JWT invalid signature or claims: %s", exc)
        return None
    except Exception as exc:
        logger.error("Supabase JWKS fetch or verification error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Máy chủ xác thực Supabase hiện không thể kết nối. Vui lòng thử lại sau."
        )


def resolve_or_provision_supabase_user(payload: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Resolves the SQLite internal user record mapped to a verified Supabase UID.
    If the identity mapping does not exist yet (e.g. newly registered user),
    performs an idempotent provisioning sequence.
    """
    supabase_uid = payload.get("sub")
    if not supabase_uid:
        return None

    email = (payload.get("email") or (metadata.get("email") if metadata else None) or "").strip().lower()

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()

        # 1. Check existing identity link
        cursor.execute(
            "SELECT sqlite_user_id, status FROM gari_identity_links WHERE supabase_uid = ?",
            (supabase_uid,)
        )
        link = cursor.fetchone()

        if link:
            if link["status"] != "ACTIVE":
                return None
            user_id = link["sqlite_user_id"]
        else:
            # 2. Idempotent Provisioning
            meta = metadata or {}
            user_meta = payload.get("user_metadata", {}) or {}
            full_name = meta.get("full_name") or meta.get("name") or user_meta.get("full_name") or user_meta.get("name") or "Người dùng Gari"
            phone = meta.get("phone") or user_meta.get("phone") or ""
            province = meta.get("province") or user_meta.get("province") or "Lâm Đồng"
            account_type = meta.get("account_type") or user_meta.get("account_type") or "farmer"
            account_type = normalize_account_type(account_type)

            # Check if user with this email already exists in SQLite
            cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                user_id = existing_user["id"]
            else:
                cursor.execute(
                    """
                    INSERT INTO users (full_name, name, email, phone, province, account_type, is_active, moderation_status)
                    VALUES (?, ?, ?, ?, ?, ?, 1, 'clean')
                    """,
                    (full_name, full_name, email, phone, province, account_type)
                )
                user_id = cursor.lastrowid

                # Initialize default free subscription and audit
                now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    """
                    INSERT INTO user_subscriptions (user_id, plan_id, status, billing_interval, start_date)
                    VALUES (?, 'free', 'active', 'lifetime', ?)
                    """,
                    (user_id, now_iso)
                )
                cursor.execute(
                    "INSERT INTO user_account_type_audit (user_id, previous_type, new_type, reason, changed_by_user_id) VALUES (?, NULL, ?, 'Supabase Signup', ?)",
                    (user_id, account_type, user_id)
                )

            # Create identity link and provisioning records
            cursor.execute(
                """
                INSERT INTO gari_identity_links (supabase_uid, sqlite_user_id, status)
                VALUES (?, ?, 'ACTIVE')
                ON CONFLICT(supabase_uid) DO UPDATE SET status='ACTIVE', updated_at=CURRENT_TIMESTAMP
                """,
                (supabase_uid, user_id)
            )
            cursor.execute(
                """
                INSERT INTO account_provisioning (supabase_uid, status, retry_count)
                VALUES (?, 'ACTIVE', 0)
                ON CONFLICT(supabase_uid) DO UPDATE SET status='ACTIVE', updated_at=CURRENT_TIMESTAMP
                """,
                (supabase_uid,)
            )
            conn.commit()

        # 3. Retrieve authoritative user context from SQLite
        cursor.execute(
            """
            SELECT id, full_name, name, email, phone, address, province,
                   avatar_url, bio, account_type, is_admin, is_host_admin, is_expert, is_active,
                   moderation_status, feature_restrictions, moderation_reason, created_at, updated_at
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        )
        row = cursor.fetchone()
        if not row or row["is_active"] == 0 or row["moderation_status"] == "banned":
            return None

        user = dict(row)
        user["supabase_uid"] = supabase_uid
        user["full_name"] = user.get("full_name") or user.get("name") or "Người dùng Gari"
        user["is_admin"] = bool(user.get("is_admin"))
        user["is_host_admin"] = bool(user.get("is_host_admin"))
        user["is_expert"] = bool(user.get("is_expert"))
        user["is_active"] = bool(user.get("is_active", 1))
        user["moderation_status"] = user.get("moderation_status") or "clean"
        user["feature_restrictions"] = user.get("feature_restrictions") or ""
        return user


def validate_session(token: str) -> Optional[Dict[str, Any]]:
    """Validate a Supabase JWT or legacy session token and return the associated user dict if valid and unexpired."""
    if not token or len(token) < 20:
        return None

    # 1. Primary Modern Authority: Supabase JWT verification
    if token.count(".") == 2:
        payload = verify_supabase_jwt(token)
        if payload:
            return resolve_or_provision_supabase_user(payload)
        # If token is formatted as a JWT but verification failed, reject explicitly (do not fall back)
        return None

    # 2. Local Database Legacy Session Verification (Temporary transition for unexpired sessions)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.token, s.expires_at, u.id, u.full_name, u.name, u.email, u.phone, u.address, u.province,
                   u.avatar_url, u.bio, u.account_type, u.is_admin, u.is_host_admin, u.is_expert, u.is_active,
                   u.moderation_status, u.feature_restrictions, u.moderation_reason, u.firebase_uid, u.created_at, u.updated_at
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, now_iso)
        )
        row = cursor.fetchone()
        if not row:
            return None

        if row["is_active"] == 0 or row["moderation_status"] == "banned":
            return None

        user = dict(row)
        user["full_name"] = user.get("full_name") or user.get("name") or "Người dùng Gari"
        user["is_admin"] = bool(user.get("is_admin"))
        user["is_host_admin"] = bool(user.get("is_host_admin"))
        user["is_expert"] = bool(user.get("is_expert"))
        user["is_active"] = bool(user.get("is_active", 1))
        user["moderation_status"] = user.get("moderation_status") or "clean"
        user["feature_restrictions"] = user.get("feature_restrictions") or ""
        return user


def destroy_session(token: str) -> None:
    """Invalidate and remove a session token."""
    if not token:
        return
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_sessions WHERE token = ?", (token,))
        conn.commit()


def create_password_reset_token(email: str) -> Tuple[str, Dict[str, Any]]:
    """Generate a 15-minute temporary password reset token for safe development recovery."""
    email = (email or "").strip().lower()
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name, name, email FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy tài khoản với địa chỉ email này."
            )

        user = dict(row)
        token = secrets.token_urlsafe(24)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        expires_iso = expires_at.strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            INSERT INTO password_resets (token, user_id, expires_at, used)
            VALUES (?, ?, ?, 0)
            """,
            (token, user["id"], expires_iso)
        )
        conn.commit()
        return token, user


def reset_password_with_token(token: str, new_password: str) -> None:
    """Verify reset token and update user password with new Bcrypt hash."""
    if not new_password or len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải có ít nhất 6 ký tự."
        )

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT token, user_id FROM password_resets
            WHERE token = ? AND used = 0 AND expires_at > ?
            """,
            (token, now_iso)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã khôi phục không hợp lệ hoặc đã hết hạn (15 phút)."
            )

        user_id = row["user_id"]
        pwd_hash = hash_password(new_password)

        # Update password
        cursor.execute("UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (pwd_hash, user_id))
        # Mark token as used
        cursor.execute("UPDATE password_resets SET used = 1 WHERE token = ?", (token,))
        # Revoke all existing sessions for this user for security
        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        conn.commit()


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract auth token from Authorization Header or Cookie."""
    # 1. Check Authorization Bearer header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    # 2. Check HttpOnly cookie
    cookie_token = request.cookies.get("gari_session")
    if cookie_token:
        return cookie_token.strip()

    return None


async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """FastAPI dependency to optionally retrieve authenticated user without raising 401."""
    token = extract_token_from_request(request)
    if not token:
        return None
    return validate_session(token)


async def get_current_user(request: Request) -> Dict[str, Any]:
    """FastAPI dependency that enforces authentication, raising HTTP 401 if unauthorized."""
    token = extract_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa đăng nhập. Vui lòng đăng nhập để tiếp tục."
        )

    user = validate_session(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại."
        )

    return user


async def get_current_admin_user(request: Request) -> Dict[str, Any]:
    """
    Enforces Platform Admin authorization.
    Rejects regular users with HTTP 403 Forbidden.
    """
    user = await get_current_user(request)
    account_type = (user.get("account_type") or "").strip().lower()
    email = (user.get("email") or "").strip().lower()

    # Admin check: account_type in ("admin", "quản trị viên", "platform_admin") or founder email
    is_admin = bool(user.get("is_admin")) or account_type in ("admin", "quản trị viên", "platform_admin") or email in ("danhuynh@gari.vn", "admin@gari.vn")
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Truy cập bị từ chối: Chỉ Quản trị viên nền tảng (Platform Admin) mới có quyền truy cập khu vực này."
        )
    return user


async def get_current_host_admin(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency strictly enforcing Host Server Admin (host_admin) authorization.
    Rejects all regular accounts and standard platform admins without is_host_admin=1.
    Never trusts client-submitted account types or UIDs.
    Returns HTTP 403 Forbidden on authorization failure.
    """
    user = await get_current_user(request)
    if not bool(user.get("is_host_admin")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Truy cập bị từ chối: Yêu cầu quyền Quản trị Máy chủ cấp cao (host_admin)."
        )
    return user


async def get_current_expert_user(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency strictly enforcing Agronomist / Expert (is_expert) authorization.
    Rejects standard users with HTTP 403 Forbidden.
    Allows verified experts or Host Administrators.
    """
    user = await get_current_user(request)
    if not (bool(user.get("is_expert")) or bool(user.get("is_host_admin"))):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Truy cập bị từ chối: Khu vực này chỉ dành riêng cho Chuyên gia Nông nghiệp được xác thực (Verified Agronomist)."
        )
    return user


def record_host_audit(
    host_admin_id: Optional[int],
    host_email: Optional[str],
    action_type: str,
    target_resource: Optional[str] = None,
    details: Optional[Union[str, Dict[str, Any]]] = None,
    reason: Optional[str] = None,
    outcome: str = "success",
    ip_address: Optional[str] = None
) -> int:
    """
    Record an immutable host administration event in host_audit_logs.
    Captures actor ID, action type, target resource, JSON/text details, audit reason, and IP.
    """
    import json
    if isinstance(details, (dict, list)):
        details_str = json.dumps(details, ensure_ascii=False)
    else:
        details_str = str(details) if details is not None else None

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO host_audit_logs (
                host_admin_id, host_email, action_type, target_resource,
                details_json, reason, outcome, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (host_admin_id, host_email, action_type, target_resource, details_str, reason, outcome, ip_address)
        )
        conn.commit()
        return cursor.lastrowid


def get_user_account_type_info(user_id: int) -> Dict[str, Any]:
    """Retrieve canonical single active account type and audit log for a given user ID."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, full_name, account_type, is_admin FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

        raw_type = row["account_type"]
        canonical = normalize_account_type(raw_type)

        # Audit trail
        cursor.execute(
            """
            SELECT id, previous_type, new_type, reason, changed_by_user_id, created_at
            FROM user_account_type_audit
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 15
            """,
            (user_id,)
        )
        audit_history = [dict(r) for r in cursor.fetchall()]

    available_types = [
        ACCOUNT_TYPE_CONFIG[ACCOUNT_TYPE_FARMER],
        ACCOUNT_TYPE_COOPERATIVE_CONFIG := ACCOUNT_TYPE_CONFIG[ACCOUNT_TYPE_COOPERATIVE],
        ACCOUNT_TYPE_CONFIG[ACCOUNT_TYPE_EXPERT],
        ACCOUNT_TYPE_CONFIG[ACCOUNT_TYPE_ENTERPRISE],
    ]

    return {
        "success": True,
        "user_id": user_id,
        "account_type": canonical,
        "display_name": ACCOUNT_TYPE_CONFIG.get(canonical, {}).get("label") if canonical else None,
        "is_locked": canonical is not None,
        "is_admin": bool(row["is_admin"]),
        "available_types": available_types,
        "audit_history": audit_history
    }


def set_initial_account_type(user_id: int, account_type: str) -> Dict[str, Any]:
    """
    Set account type when the user currently has no active type.
    Fails if the user already has an active account type (enforces single active type).
    """
    canonical = normalize_account_type(account_type)
    if not canonical or canonical not in VALID_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loại tài khoản không hợp lệ. Phải là một trong: {', '.join(sorted(VALID_ACCOUNT_TYPES))}."
        )

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, account_type FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

        current_canonical = normalize_account_type(row["account_type"])
        if current_canonical is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tài khoản đã có loại tài khoản đang kích hoạt và đã được cố định. Vui lòng sử dụng quy trình xác nhận đổi loại tài khoản."
            )

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE users SET account_type = ?, updated_at = ? WHERE id = ?",
            (canonical, now_iso, user_id)
        )
        cursor.execute(
            """
            INSERT INTO user_account_type_audit (user_id, previous_type, new_type, reason, changed_by_user_id)
            VALUES (?, NULL, ?, 'Thiết lập loại tài khoản ban đầu', ?)
            """,
            (user_id, canonical, user_id)
        )
        conn.commit()

    return get_user_account_type_info(user_id)


def change_account_type(
    user_id: int,
    new_type: str,
    confirm: bool,
    reason: Optional[str] = None,
    actor_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Safely changes an existing user's single active account type.
    Requires explicit confirmation (confirm=True) and logs an audit record.
    Preserves all existing subscription & VIP entitlements without modification.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yêu cầu xác nhận rõ ràng (confirm: true) để thay đổi loại tài khoản."
        )

    canonical = normalize_account_type(new_type)
    if not canonical or canonical not in VALID_ACCOUNT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Loại tài khoản không hợp lệ. Phải là một trong: {', '.join(sorted(VALID_ACCOUNT_TYPES))}."
        )

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, account_type FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

        prev_canonical = normalize_account_type(row["account_type"])
        if prev_canonical == canonical:
            info = get_user_account_type_info(user_id)
            info["message"] = "Loại tài khoản hiện tại không thay đổi."
            return info

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE users SET account_type = ?, updated_at = ? WHERE id = ?",
            (canonical, now_iso, user_id)
        )
        audit_reason = (reason or "").strip() or "Xác nhận thay đổi loại tài khoản"
        actor_id = actor_user_id or user_id
        cursor.execute(
            """
            INSERT INTO user_account_type_audit (user_id, previous_type, new_type, reason, changed_by_user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, prev_canonical, canonical, audit_reason, actor_id)
        )
        conn.commit()

    info = get_user_account_type_info(user_id)
    info["message"] = f"Đã chuyển đổi loại tài khoản thành công sang '{ACCOUNT_TYPE_CONFIG[canonical]['label']}'."
    info["previous_type"] = prev_canonical
    return info


def require_account_type(*allowed_types: str):
    """
    FastAPI dependency factory enforcing backend account-type access control.
    Supports canonical slugs or aliases (e.g. 'expert', 'agronomist').
    Platform Admins automatically pass all checks.
    """
    normalized_allowed = set()
    for t in allowed_types:
        norm = normalize_account_type(t)
        if norm:
            normalized_allowed.add(norm)
        else:
            normalized_allowed.add(t.strip().lower())

    async def dependency(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if current_user.get("is_admin"):
            return current_user

        user_type = normalize_account_type(current_user.get("account_type"))
        if user_type not in normalized_allowed:
            allowed_labels = [ACCOUNT_TYPE_CONFIG.get(k, {}).get("label", k) for k in sorted(normalized_allowed)]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Truy cập bị từ chối: Tính năng này chỉ dành cho loại tài khoản: {', '.join(allowed_labels)}."
            )
        return current_user

    return dependency




# -----------------------------------------------------------------------------
# Module 01: Centralized User Profile & Enterprise RBAC Architecture
# -----------------------------------------------------------------------------

FORBIDDEN_PROFILE_UPDATE_FIELDS = {
    "is_admin",
    "is_host_admin",
    "is_expert",
    "account_type",
    "moderation_status",
    "feature_restrictions",
    "is_active",
    "id",
    "email",
    "password_hash",
    "firebase_uid",
    "role",
    "system_role",
    "system_roles"
}


def get_centralized_user_profile(user_id: int) -> Dict[str, Any]:
    """
    Centralized, authoritative user profile model following the 5-layer architecture:
    1. Identity (Firebase UID / session provider / email)
    2. User Demographics & Profile (name, phone, address, province, avatar, bio)
    3. Canonical Account Type (single active account type)
    4. System Roles (host_admin, admin, expert, farmer)
    5. Subscription Status (Entitlements, quotas, VIP)
    6. Organization Memberships (B2B RBAC & tenant roles)
    """
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, email, full_name, name, phone, address, province, avatar_url, bio,
                   account_type, is_admin, is_host_admin, is_expert, is_active,
                   moderation_status, feature_restrictions, moderation_reason,
                   firebase_uid, created_at, updated_at
            FROM users WHERE id = ?
            """,
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")
        user = dict(row)

    import gari_b2b
    import gari_plans

    # 1. Identity
    email = user.get("email") or ""
    firebase_uid = user.get("firebase_uid")
    display_name = user.get("full_name") or user.get("name") or (email.split("@")[0] if email else "Nông dân")
    identity = {
        "uid": firebase_uid or f"user_{user['id']}",
        "firebase_uid": firebase_uid,
        "email": email,
        "email_verified": bool(firebase_uid),
        "display_name": display_name,
        "photo_url": user.get("avatar_url"),
        "provider_id": "firebase" if firebase_uid else "password"
    }

    # 2. Demographic Profile
    profile = {
        "id": user["id"],
        "full_name": display_name,
        "name": user.get("name") or display_name,
        "phone": user.get("phone"),
        "address": user.get("address"),
        "province": user.get("province"),
        "avatar_url": user.get("avatar_url"),
        "bio": user.get("bio"),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at")
    }

    # 3. Canonical Single Active Account Type
    canonical_acc_type = normalize_account_type(user.get("account_type")) or ACCOUNT_TYPE_FARMER
    acc_config = ACCOUNT_TYPE_CONFIG.get(canonical_acc_type, {
        "key": canonical_acc_type,
        "label": canonical_acc_type.capitalize(),
        "description": ""
    })
    account_type_info = {
        "key": canonical_acc_type,
        "label": acc_config["label"],
        "description": acc_config["description"]
    }

    # 4. System Roles
    is_host_admin = bool(user.get("is_host_admin"))
    is_admin = bool(user.get("is_admin"))
    is_expert = bool(user.get("is_expert"))
    if is_host_admin:
        primary_role = "host_admin"
        primary_label = "Quản trị viên Máy chủ cấp cao"
    elif is_admin:
        primary_role = "admin"
        primary_label = "Quản trị viên Nền tảng"
    elif is_expert:
        primary_role = "expert"
        primary_label = "Chuyên gia BVTV"
    else:
        primary_role = canonical_acc_type
        primary_label = acc_config["label"]

    system_roles = {
        "primary_role": primary_role,
        "primary_label": primary_label,
        "is_host_admin": is_host_admin,
        "is_admin": is_admin,
        "is_expert": is_expert,
        "is_active": bool(user.get("is_active", 1)),
        "moderation_status": user.get("moderation_status") or "clean",
        "feature_restrictions": user.get("feature_restrictions") or ""
    }

    # 5. Subscription Status & Entitlements
    entitlement = gari_plans.resolve_user_entitlement(user)
    is_vip = bool(entitlement.get("has_vip_models"))
    plan_id = entitlement.get("plan_id", "free")
    plan_normalized = "pro" if plan_id in ("pro", "personal") else plan_id
    subscription = {
        "plan": plan_normalized,
        "plan_name": "Cá nhân Pro" if plan_normalized == "pro" else entitlement.get("plan_name", "Miễn phí"),
        "status": entitlement.get("subscription_status", "active"),
        "is_active": entitlement.get("is_active", True),
        "is_vip": is_vip,
        "has_vip_models": is_vip,
        "can_create_organization": entitlement.get("can_create_organization", False),
        "quota_limit": entitlement.get("quota_limit", 5),
        "current_period_end": entitlement.get("current_period_end")
    }

    # 6. Organization Memberships
    org_list = gari_b2b.get_user_organizations(user["id"], include_test=False)
    memberships = []
    for org in org_list:
        org_role = org.get("role", "member")
        memberships.append({
            "org_id": org.get("id"),
            "org_name": org.get("name"),
            "role": org_role,
            "status": org.get("status", "active"),
            "plan_id": org.get("plan_id", "pilot"),
            "permissions": sorted(gari_b2b.ROLE_PERMISSIONS.get(org_role, set()))
        })

    return {
        "success": True,
        "identity": identity,
        "profile": profile,
        "account_type": account_type_info,
        "system_roles": system_roles,
        "system_role": {"is_admin": is_admin, "role": primary_role},
        "subscription": subscription,
        "organizations": memberships,
        "has_organizations": len(memberships) > 0,
        "raw_user": user
    }


def update_user_profile(
    user_id: int,
    updates: Dict[str, Any],
    actor_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Safely update demographic profile fields for a user.
    Strictly forbids self-assignment or privilege escalation attempts.
    """
    if not isinstance(updates, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dữ liệu cập nhật không hợp lệ."
        )

    # Check for unauthorized privilege escalation keys
    attempted_forbidden = [k for k in updates.keys() if k.lower() in FORBIDDEN_PROFILE_UPDATE_FIELDS]
    if attempted_forbidden:
        logger.warning(
            "Security Alert: User %s attempted privilege escalation on fields %s",
            user_id, attempted_forbidden
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không được phép tự nâng cấp quyền hệ thống hoặc thay đổi thuộc tính bảo mật ({', '.join(attempted_forbidden)}) qua API thông tin cá nhân."
        )

    allowed_fields = {
        "full_name": str,
        "name": str,
        "phone": str,
        "address": str,
        "province": str,
        "avatar_url": str,
        "bio": str
    }

    set_clauses = []
    params = []

    for field in allowed_fields:
        if field in updates:
            val = updates[field]
            if val is not None:
                val = str(val).strip()
            if field == "full_name" and val:
                set_clauses.append("full_name = ?")
                params.append(val)
                if "name" not in updates:
                    set_clauses.append("name = ?")
                    params.append(val)
            elif field != "name":
                set_clauses.append(f"{field} = ?")
                params.append(val)

    if not set_clauses:
        return get_centralized_user_profile(user_id)

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.append(user_id)

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
        cursor.execute(sql, tuple(params))
        conn.commit()

    return get_centralized_user_profile(user_id)


def require_org_role(*allowed_roles: str, org_id_param: str = "org_id"):
    """
    FastAPI dependency factory enforcing tenant-isolated organization role checks.
    Supports single role or multiple permitted roles (e.g., 'owner', 'admin').
    Extracts org_id from path parameters, query parameters, or 'X-Organization-Id' header.
    Host Admins bypass tenant checks for platform administration.
    """
    permitted = {r.lower() for r in allowed_roles}

    async def dependency(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        # Host Admin bypass
        if current_user.get("is_host_admin"):
            return {"user": current_user, "role": "host_admin", "org_id": None}

        # Extract org_id from path params or query params or header
        raw_org_id = (
            request.path_params.get(org_id_param)
            or request.query_params.get(org_id_param)
            or request.headers.get("X-Organization-Id")
        )
        if not raw_org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Thiếu định danh tổ chức ({org_id_param})."
            )

        try:
            org_id = int(raw_org_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định danh tổ chức không hợp lệ."
            )

        import gari_b2b
        role = gari_b2b.get_member_role(org_id, current_user["id"])
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Truy cập bị từ chối: Bạn không phải thành viên của tổ chức này."
            )

        if permitted and role not in permitted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Truy cập bị từ chối: Vai trò '{role}' không có quyền thực hiện thao tác này. Yêu cầu: {', '.join(sorted(permitted))}."
            )

        return {"user": current_user, "role": role, "org_id": org_id}

    return dependency
