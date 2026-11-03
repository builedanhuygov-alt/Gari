"""
GARI AI LAB — Safe Payment & Bank QR Configuration Validator (tools/validate_payment_config.py)

Validates presence of required Bank QR environment variables without exposing secret values.
Reports only [SET] or [MISSING].

Usage:
    python tools/validate_payment_config.py
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


def validate_payment_configuration(exit_on_incomplete: bool = False) -> dict:
    """
    Checks each environment variable required for Bank QR payment integration.
    CRITICAL: Never prints or logs actual secret values, account numbers, prefixes, lengths, or hashes.
    """
    placeholders = {
        "your_bank_id",
        "your_account_number",
        "your_account_name",
        "changeme",
        "default",
        ""
    }

    def check_var(name: str) -> tuple[str, bool]:
        val = os.getenv(name, "").strip()
        if not val or val.lower() in placeholders:
            return "[MISSING]", False
        return "[SET]", True

    # 1. Provider
    p_provider_val = os.getenv("PAYMENT_PROVIDER", "").strip().lower()
    p_provider_status = f"[SET] ({p_provider_val})" if p_provider_val else "[SET] (defaults to bank_qr)"

    # 2. Bank QR recipient account parameters
    bank_id_status, has_bank_id = check_var("BANK_QR_BANK_ID")
    acc_num_status, has_acc_num = check_var("BANK_QR_ACCOUNT_NUMBER")
    acc_name_status, has_acc_name = check_var("BANK_QR_ACCOUNT_NAME")

    # 3. Public checkout safety switch
    raw_checkout_switch = os.getenv("PAYMENT_PUBLIC_CHECKOUT_ENABLED", "0").strip().lower()
    checkout_enabled = raw_checkout_switch in ("1", "true", "yes")
    checkout_status = "[ENABLED] (CAUTION: Public users can generate payment QR)" if checkout_enabled else "[DISABLED] (Safe Default - Prevents unverified public checkout)"

    # 4. Order Expiration
    expiry_mins = os.getenv("PAYMENT_ORDER_EXPIRY_MINUTES", "15").strip()

    print("\n" + "=" * 70)
    print(" GARI AI LAB — VIETNAMESE BANK QR CONFIGURATION VALIDATION")
    print("=" * 70)
    print(f" PAYMENT_PROVIDER:                  {p_provider_status}")
    print(f" BANK_QR_BANK_ID:                   {bank_id_status}")
    print(f" BANK_QR_ACCOUNT_NUMBER:            {acc_num_status}")
    print(f" BANK_QR_ACCOUNT_NAME:              {acc_name_status}")
    print(f" PAYMENT_ORDER_EXPIRY_MINUTES:      [SET] ({expiry_mins} minutes)")
    print(f" PAYMENT_PUBLIC_CHECKOUT_ENABLED:   {checkout_status}")
    print("-" * 70)

    # Readiness assessments
    bank_details_ready = has_bank_id and has_acc_num and has_acc_name
    live_checkout_active = bank_details_ready and checkout_enabled

    print(" READINESS STATUS:")
    print(f" - Recipient Bank Account:          {'[READY]' if bank_details_ready else '[INCOMPLETE] (Missing Bank ID, Account Number, or Name)'}")
    print(f" - Public Checkout Access:          {'[ACTIVE]' if live_checkout_active else '[SAFE / BLOCKED]'}")

    if not live_checkout_active:
        if not bank_details_ready:
            print("   -> Public checkout remains safely disabled (bank recipient configuration incomplete).")
        else:
            print("   -> Bank details configured, but checkout is blocked by PAYMENT_PUBLIC_CHECKOUT_ENABLED=0.")
            print("      (Safe: enables controlled testing without exposing to general public).")

    print("=" * 70 + "\n")

    report = {
        "has_bank_id": has_bank_id,
        "has_acc_num": has_acc_num,
        "has_acc_name": has_acc_name,
        "bank_details_ready": bank_details_ready,
        "checkout_enabled": checkout_enabled,
        "is_ready_for_production": live_checkout_active
    }

    if exit_on_incomplete and not bank_details_ready:
        sys.exit(1)

    return report


if __name__ == "__main__":
    validate_payment_configuration()
