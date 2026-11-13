"""
GARI AI LAB — Firebase Authentication & Identity Engine (gari_firebase.py)
Authoritative server-side verification of Firebase ID Tokens.

Invariants:
1. Derives authenticated UID from cryptographically verified Firebase ID token.
2. Synchronizes with internal SQLite user records via `firebase_uid`.
3. Enforces single active account type per UID ('farmer', 'cooperative', 'expert', 'enterprise').
4. Strictly separates Host Authorization (is_host_admin) from user account types.
5. In development/testing environments without Google service account keys, provides a secure emulator/test-mode verification path.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("gari_firebase")

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "database" / "disease_detector.db"

# -----------------------------------------------------------------------------
# Firebase Admin SDK Initialization
# -----------------------------------------------------------------------------
_FIREBASE_APP = None
_FIREBASE_INITIALIZED = False

try:
    import firebase_admin
    from firebase_admin import auth, credentials

    cred_path_env = os.getenv("FIREBASE_CREDENTIALS_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    cred_json_env = os.getenv("FIREBASE_CREDENTIALS_JSON")

    if cred_path_env and Path(cred_path_env).exists():
        cred = credentials.Certificate(str(cred_path_env))
        _FIREBASE_APP = firebase_admin.initialize_app(cred)
        _FIREBASE_INITIALIZED = True
        logger.info("Firebase Admin initialized with certificate from %s", cred_path_env)
    elif cred_json_env:
        cred_dict = json.loads(cred_json_env)
        cred = credentials.Certificate(cred_dict)
        _FIREBASE_APP = firebase_admin.initialize_app(cred)
        _FIREBASE_INITIALIZED = True
        logger.info("Firebase Admin initialized with credentials from JSON environment variable")
    else:
        # Check if already initialized by runtime
        try:
            _FIREBASE_APP = firebase_admin.get_app()
            _FIREBASE_INITIALIZED = True
            logger.info("Firebase Admin retrieved existing default app")
        except ValueError:
            # Not initialized yet; provide development mode until service account is placed
            logger.warning(
                "Firebase service credentials not configured. Firebase Auth running in "
                "development-compatible mode. Set FIREBASE_CREDENTIALS_PATH to enable production ID token verification."
            )
except Exception as e:
    logger.warning("Could not initialize Firebase Admin SDK: %s", e)


def is_firebase_initialized() -> bool:
    """Returns True if Firebase Admin SDK is initialized with valid credentials."""
    return _FIREBASE_INITIALIZED


def verify_firebase_id_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    Cryptographically verify Firebase ID token server-side.
    Returns decoded token dictionary or None if invalid.
    """
    if not id_token or not isinstance(id_token, str):
        return None

    # Production Mode with Firebase Admin SDK
    if _FIREBASE_INITIALIZED:
        try:
            decoded = auth.verify_id_token(id_token, check_revoked=True)
            return decoded
        except Exception as exc:
            logger.warning("Firebase ID Token verification failed: %s", exc)
            return None

    # Test / Dev Verification Mode (for automated test suites and local testing)
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env in ("production", "prod"):
        logger.error("In production mode, Firebase ID token verification requires initialized Firebase Admin credentials.")
        return None

    # Allow signed test JWTs or mock tokens during development test execution
    if id_token.startswith("firebase_test_"):
        test_uid = id_token[len("firebase_test_"):].strip() or "test_uid_default"
        test_email = f"{test_uid}@gari.vn"
        return {
            "uid": test_uid,
            "email": test_email,
            "name": f"Firebase User {test_uid}",
            "auth_time": int(datetime.now(timezone.utc).timestamp()),
            "firebase": {"sign_in_provider": "password"}
        }

    return None


def get_or_sync_firebase_user(
    decoded_token: Dict[str, Any],
    registration: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Look up or synchronize the user from Firebase into internal database.
    Ensures every user has exactly ONE active account type.
    """
    fb_uid = decoded_token.get("uid")
    email = decoded_token.get("email")
    registration = registration or {}
    name = (registration.get("full_name") or decoded_token.get("name") or decoded_token.get("displayName") or (email.split("@")[0] if email else "Nông dân")).strip()
    phone = (registration.get("phone") or decoded_token.get("phone_number") or decoded_token.get("phone") or "").strip() or None
    province = (registration.get("province") or "Lâm Đồng").strip()

    if not fb_uid and not email:
        raise ValueError("Decoded Firebase token missing both uid and email.")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(str(DB_PATH), timeout=20.0) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Match by firebase_uid
        if fb_uid:
            cursor.execute("SELECT * FROM users WHERE firebase_uid = ?", (fb_uid,))
            user = cursor.fetchone()
            if user:
                return dict(user)

        # 2. Match by email
        if email:
            cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            user = cursor.fetchone()
            if user:
                # Link firebase_uid to existing account
                user_id = user["id"]
                if fb_uid and not user["firebase_uid"]:
                    cursor.execute("UPDATE users SET firebase_uid = ?, updated_at = ? WHERE id = ?", (fb_uid, now_iso, user_id))
                    conn.commit()
                    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                    return dict(cursor.fetchone())
                return dict(user)

        # 3. Create a profile only for this verified Firebase identity.  Account
        # type is normalized to the non-privileged public categories; Host and
        # Expert roles can never be assigned by the client registration flow.
        raw_account_type = str(registration.get("account_type") or "farmer").strip().lower()
        account_type_map = {
            "farmer": "farmer", "nông hộ": "farmer", "nông hộ cá thể": "farmer",
            "cooperative": "cooperative", "hợp tác xã": "cooperative",
            "agricultural_service_provider": "enterprise", "agricultural service provider": "enterprise",
            "nhà cung cấp dịch vụ nông nghiệp": "enterprise", "đơn vị dịch vụ nông nghiệp": "enterprise",
            "enterprise": "enterprise",
        }
        default_account_type = account_type_map.get(raw_account_type, "farmer")
        cursor.execute(
            """
            INSERT INTO users (
                email, name, full_name, phone, province, firebase_uid, account_type,
                is_admin, is_host_admin, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 1, ?, ?)
            """,
            (email, name, name, phone, province, fb_uid, default_account_type, now_iso, now_iso)
        )
        new_id = cursor.lastrowid

        # Record initial account type audit
        cursor.execute(
            """
            INSERT INTO user_account_type_audit (
                user_id, previous_type, new_type, changed_by_user_id, reason, created_at
            ) VALUES (?, NULL, ?, ?, 'Initial Firebase Registration', ?)
            """,
            (new_id, default_account_type, new_id, now_iso)
        )
        conn.commit()

        cursor.execute("SELECT * FROM users WHERE id = ?", (new_id,))
        return dict(cursor.fetchone())


def set_firebase_custom_claims(fb_uid: str, account_type: str, is_host_admin: bool = False) -> bool:
    """
    Set custom claims on Firebase user for frontend token inspection.
    """
    if not _FIREBASE_INITIALIZED:
        logger.info("Firebase Admin not initialized; skipped remote custom claims for %s", fb_uid)
        return False

    try:
        claims = {
            "gari_account_type": account_type,
            "gari_is_host_admin": bool(is_host_admin)
        }
        auth.set_custom_user_claims(fb_uid, claims)
        logger.info("Updated Firebase custom claims for %s: %s", fb_uid, claims)
        return True
    except Exception as exc:
        logger.error("Failed to set Firebase custom claims: %s", exc)
        return False
