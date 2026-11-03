"""
GARI AI LAB — Safe PayOS Configuration Validator (tools/validate_payos_config.py)

Validates presence of required PayOS environment variables without exposing any secret values.
Reports only [SET] or [MISSING].

Usage:
    python tools/validate_payos_config.py
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


def validate_payos_configuration(exit_on_incomplete: bool = False) -> dict:
    """
    Checks each environment variable required for PayOS integration.
    CRITICAL: Never prints or logs actual secret values, prefixes, lengths, or hashes.
    """
    placeholders = {
        "your_payos_client_id_here",
        "your_payos_api_key_here",
        "your_payos_checksum_key_here",
        "your_client_id",
        "your_api_key",
        "your_checksum_key",
        "changeme",
        "default",
        ""
    }

    def check_var(name: str, is_secret: bool = True) -> tuple[str, bool]:
        val = os.getenv(name, "").strip()
        if not val or val.lower() in placeholders:
            return "[MISSING]", False
        return "[SET]", True

    # 1. Inspect required credentials
    p_provider_val = os.getenv("PAYMENT_PROVIDER", "").strip().lower()
    p_provider_status = "[SET] (payos)" if p_provider_val == "payos" else ("[SET] (" + p_provider_val + ")" if p_provider_val else "[MISSING] (defaults to payos)")

    client_id_status, has_client_id = check_var("PAYOS_CLIENT_ID", is_secret=True)
    api_key_status, has_api_key = check_var("PAYOS_API_KEY", is_secret=True)
    checksum_status, has_checksum = check_var("PAYOS_CHECKSUM_KEY", is_secret=True)

    # 2. Inspect URLs and operational parameters
    return_url_status, has_return_url = check_var("PAYMENT_RETURN_URL", is_secret=False)
    cancel_url_status, has_cancel_url = check_var("PAYMENT_CANCEL_URL", is_secret=False)

    # 3. Inspect public checkout safety switch
    # PayOS has no sandbox; public checkout must be explicitly enabled
    raw_checkout_switch = os.getenv("PAYOS_ENABLE_PUBLIC_CHECKOUT", "0").strip().lower()
    checkout_enabled = raw_checkout_switch in ("1", "true", "yes")
    checkout_status = "[ENABLED] (CAUTION: Real charges live)" if checkout_enabled else "[DISABLED] (Safe Default - Prevents live customer charges)"

    # 4. Webhook replay window
    max_age = os.getenv("PAYMENT_WEBHOOK_MAX_AGE_SECONDS", "86400").strip()

    print("\n" + "=" * 70)
    print(" GARI AI LAB — PAYOS INTEGRATION CONFIGURATION VALIDATION")
    print("=" * 70)
    print(f" PAYMENT_PROVIDER:               {p_provider_status}")
    print(f" PAYOS_CLIENT_ID:                {client_id_status}")
    print(f" PAYOS_API_KEY:                  {api_key_status}")
    print(f" PAYOS_CHECKSUM_KEY:             {checksum_status}")
    print(f" PAYMENT_RETURN_URL:             {return_url_status}")
    print(f" PAYMENT_CANCEL_URL:             {cancel_url_status}")
    print(f" PAYMENT_WEBHOOK_MAX_AGE:        [SET] ({max_age} seconds)")
    print(f" PAYOS_ENABLE_PUBLIC_CHECKOUT:   {checkout_status}")
    print("-" * 70)

    # Readiness assessments
    webhook_ready = has_checksum
    checkout_credentials_ready = has_client_id and has_api_key and has_checksum
    live_checkout_active = checkout_credentials_ready and checkout_enabled

    print(" READINESS STATUS:")
    print(f" - Webhook Verification:         {'[READY]' if webhook_ready else '[INCOMPLETE] (Missing PAYOS_CHECKSUM_KEY)'}")
    print(f" - Payment Creation API:         {'[READY]' if checkout_credentials_ready else '[INCOMPLETE] (Credentials missing or placeholder)'}")
    print(f" - Public Checkout Access:       {'[ACTIVE]' if live_checkout_active else '[SAFE / BLOCKED]'}")

    if not live_checkout_active:
        if not checkout_credentials_ready:
            print("   -> Public checkout remains safely disabled (credentials not configured).")
        else:
            print("   -> Credentials present, but public checkout is blocked by PAYOS_ENABLE_PUBLIC_CHECKOUT=0.")
            print("      (Safe for synthetic tests & webhook verification without real money transactions).")

    print("=" * 70 + "\n")

    report = {
        "has_client_id": has_client_id,
        "has_api_key": has_api_key,
        "has_checksum": has_checksum,
        "has_return_url": has_return_url,
        "has_cancel_url": has_cancel_url,
        "webhook_ready": webhook_ready,
        "checkout_credentials_ready": checkout_credentials_ready,
        "live_checkout_active": live_checkout_active
    }

    if exit_on_incomplete and not checkout_credentials_ready:
        sys.exit(1)

    return report


from tools.validate_payment_config import validate_payment_configuration

if __name__ == "__main__":
    validate_payment_configuration()
