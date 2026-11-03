"""
GARI AI LAB — Production Configuration & Environment Manager (gari_config.py)
Principal Engineer & SRE Architecture:
- Environment separation: development, test, staging, production
- Startup validation with fail-fast security on missing secrets
- Enforced rejection of development bypasses in production
- Strict CORS and trusted hosts allowlist management
- Sanitized config logging without credential leakage
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("gari_config")

ROOT_DIR = Path(__file__).resolve().parent

# Environment determination: APP_ENV or GARI_ENV (default: development)
APP_ENV = os.getenv("APP_ENV", os.getenv("GARI_ENV", "development")).lower().strip()
IS_PRODUCTION = APP_ENV in ("production", "prod")
IS_STAGING = APP_ENV in ("staging", "stage")
IS_TEST = APP_ENV in ("test", "testing")
IS_DEVELOPMENT = not (IS_PRODUCTION or IS_STAGING or IS_TEST)

# Debug mode: NEVER allowed in production
DEBUG = False if IS_PRODUCTION else (os.getenv("DEBUG", "0").lower() in ("1", "true", "yes"))

# Server Host & Port
HOST = os.getenv("GARI_HOST", "0.0.0.0")
PORT = int(os.getenv("GARI_PORT", "8000"))

# File System Directories
DATABASE_DIR = ROOT_DIR / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATABASE_DIR / "disease_detector.db"

UPLOADS_DIR = DATABASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

BACKUPS_DIR = DATABASE_DIR / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

MODELS_DIR = Path(os.getenv("MODELS_DIR", str(ROOT_DIR / "models")))

# Authentication & Cryptographic Secrets
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")

DEFAULT_DEV_SECRETS = {
    "gari_dev_secret_key_change_in_production_2026",
    "gari_jwt_dev_key_change_in_production_2026",
    "secret",
    "changeme",
    "default",
    ""
}

# Development Pro Bypass: STRICTLY FORBIDDEN IN PRODUCTION
_raw_dev_pro = os.getenv("GARI_ALLOW_DEV_PRO", "0" if IS_PRODUCTION else "1")
ALLOW_DEV_PRO_BYPASS = False if IS_PRODUCTION else (_raw_dev_pro in ("1", "true", "True"))

# CORS Allowed Origins
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
if _raw_origins:
    ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
elif IS_PRODUCTION:
    ALLOWED_ORIGINS = ["https://gari.vn", "https://app.gari.vn"]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000"
    ]

# Upload & Inference Limits
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(15 * 1024 * 1024)))  # 15 MB
INFERENCE_TIMEOUT_SECONDS = int(os.getenv("INFERENCE_TIMEOUT_SECONDS", "30"))


def validate_startup_configuration() -> None:
    """
    Validates essential environment variables and security constraints at system boot.
    If a critical configuration error is detected, raises SystemExit with safe diagnostic output.
    """
    errors: List[str] = []

    # 1. Production Secrets Verification
    if IS_PRODUCTION:
        if not SESSION_SECRET or SESSION_SECRET.lower() in DEFAULT_DEV_SECRETS:
            errors.append(
                "CRITICAL SECURITY: In production mode, SESSION_SECRET must be set to a secure, "
                "random string (min 32 characters) and cannot be the default development placeholder."
            )
        elif len(SESSION_SECRET) < 32:
            errors.append(
                f"CRITICAL SECURITY: SESSION_SECRET is too short ({len(SESSION_SECRET)} chars). "
                "Must be at least 32 characters in production."
            )

        if not JWT_SECRET or JWT_SECRET.lower() in DEFAULT_DEV_SECRETS:
            errors.append(
                "CRITICAL SECURITY: In production mode, JWT_SECRET must be set to a secure, "
                "random string (min 32 characters) and cannot be the default development placeholder."
            )
        elif len(JWT_SECRET) < 32:
            errors.append(
                f"CRITICAL SECURITY: JWT_SECRET is too short ({len(JWT_SECRET)} chars). "
                "Must be at least 32 characters in production."
            )

        # 2. CORS Safety
        if "*" in ALLOWED_ORIGINS:
            errors.append(
                "CRITICAL SECURITY: Wildcard CORS ('*') is strictly prohibited in production "
                "when session cookies or authorization headers are used."
            )

        # 3. Development Bypass Safety
        if ALLOW_DEV_PRO_BYPASS:
            errors.append(
                "CRITICAL SECURITY: Development Pro Bypass (GARI_ALLOW_DEV_PRO) cannot be enabled "
                "in production environment."
            )

        # 4. Debug Mode
        if DEBUG:
            errors.append("CRITICAL SECURITY: DEBUG mode cannot be enabled in production.")

    if errors:
        sys.stderr.write("\n" + "=" * 80 + "\n")
        sys.stderr.write(" GARI AI LAB — STARTUP CONFIGURATION VALIDATION FAILED\n")
        sys.stderr.write("=" * 80 + "\n")
        for err in errors:
            sys.stderr.write(f" [FAIL] {err}\n")
        sys.stderr.write("=" * 80 + "\n")
        sys.stderr.write(" Server boot aborted safely to prevent running in insecure state.\n\n")
        sys.exit(1)

    logger.info(
        "Gari AI Lab configuration validated successfully: env=%s, debug=%s, dev_bypass=%s",
        APP_ENV, DEBUG, ALLOW_DEV_PRO_BYPASS
    )


def get_safe_config_summary() -> dict:
    """Returns a sanitized summary of configuration without disclosing any credentials."""
    return {
        "app_env": APP_ENV,
        "is_production": IS_PRODUCTION,
        "is_staging": IS_STAGING,
        "debug": DEBUG,
        "host": HOST,
        "port": PORT,
        "database_file": str(DATABASE_PATH.name),
        "allowed_origins_count": len(ALLOWED_ORIGINS),
        "allow_dev_pro_bypass": ALLOW_DEV_PRO_BYPASS,
        "max_upload_size_mb": MAX_UPLOAD_SIZE_BYTES / (1024 * 1024),
        "session_secret_configured": bool(SESSION_SECRET and SESSION_SECRET not in DEFAULT_DEV_SECRETS),
        "jwt_secret_configured": bool(JWT_SECRET and JWT_SECRET not in DEFAULT_DEV_SECRETS),
    }
