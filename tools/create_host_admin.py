"""
GARI AI LAB — Dedicated Host Administrator Bootstrap Tool (create_host_admin.py)

Creates or recovers the dedicated system Host Administrator account.
Security specifications:
- One-time initial bootstrap: refuses to create additional host accounts if one exists,
  unless --force-recovery is explicitly authorized.
- Interactive terminal password input with mask (getpass).
- Bcrypt password hashing (salt rounds: 12) via gari_auth.
- Host privileges are separate from regular account types (farmer, cooperative, expert, enterprise).
- Never logs or prints plaintext passwords.
- Records immutable audit trail in host_audit_logs.
"""

import argparse
import getpass
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gari_auth
import gari_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_create_host_admin")

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def count_existing_host_admins() -> int:
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_host_admin = 1")
        return cursor.fetchone()[0]


def bootstrap_host_admin(
    email: str,
    password: str,
    confirm_password: str,
    full_name: str = "Host Administrator",
    force_recovery: bool = False
) -> int:
    email = (email or "").strip().lower()
    full_name = (full_name or "").strip() or "Host Administrator"

    if not email or not EMAIL_REGEX.match(email):
        raise ValueError("Invalid email address format.")

    if not password or len(password) < 8:
        raise ValueError("Host password must be at least 8 characters long.")

    if password != confirm_password:
        raise ValueError("Password confirmation does not match.")

    existing_count = count_existing_host_admins()
    if existing_count > 0 and not force_recovery:
        raise PermissionError(
            f"A Host Administrator already exists in this system ({existing_count} active). "
            "One-time initial bootstrap is locked. To reset or recover host credentials, "
            "use the --force-recovery flag."
        )

    pwd_hash = gari_auth.hash_password(password)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        # Check if email is already in users table
        cursor.execute("SELECT id, is_host_admin FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            user_id = existing_user["id"]
            cursor.execute("""
                UPDATE users
                SET password_hash = ?, full_name = ?, is_host_admin = 1, is_active = 1, updated_at = ?
                WHERE id = ?
            """, (pwd_hash, full_name, now_iso, user_id))
            action = "host_admin_recovered" if force_recovery else "host_admin_promoted"
            logger.info("Updated existing user #%d as Host Administrator.", user_id)
        else:
            cursor.execute("""
                INSERT INTO users (full_name, name, email, password_hash, account_type, is_admin, is_host_admin, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'expert', 1, 1, 1, ?, ?)
            """, (full_name, full_name, email, pwd_hash, now_iso, now_iso))
            user_id = cursor.lastrowid
            action = "host_admin_bootstrapped"
            logger.info("Created new Host Administrator account #%d.", user_id)

        # Audit the administrative action
        cursor.execute("""
            INSERT INTO host_audit_logs (host_admin_id, host_email, action_type, target_resource, details_json, reason, outcome)
            VALUES (?, ?, ?, 'host_system', '{"bootstrap_mode": "cli"}', 'Initial Host Setup / Recovery', 'success')
        """, (user_id, email, action))

        conn.commit()

    return user_id


def main():
    parser = argparse.ArgumentParser(description="GARI Secure Host Administrator Bootstrap & Recovery Tool")
    parser.add_argument("--email", help="Host Administrator Email Address", default=None)
    parser.add_argument("--full-name", help="Host Administrator Full Name", default="Host Administrator")
    parser.add_argument("--password", help="Host Password (optional; interactive prompt preferred)", default=None)
    parser.add_argument("--confirm-password", help="Confirm Password", default=None)
    parser.add_argument("--force-recovery", action="store_true", help="Authorize recovery/reset of Host Admin account")

    args = parser.parse_args()

    print("=" * 60)
    print("🌿 GARI AI LAB — HOST ADMINISTRATOR SETUP CONSOLE")
    print("=" * 60)

    email = args.email
    if not email:
        try:
            email = input("Enter Host Administrator Email: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    password = args.password
    confirm_password = args.confirm_password

    if not password:
        try:
            password = getpass.getpass("Enter Host Password (min 8 chars): ")
            confirm_password = getpass.getpass("Confirm Host Password: ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    try:
        host_id = bootstrap_host_admin(
            email=email,
            password=password,
            confirm_password=confirm_password,
            full_name=args.full_name,
            force_recovery=args.force_recovery
        )
        print("\n✅ SUCCESS: Host Administrator configured successfully!")
        print(f"   User ID: {host_id}")
        print(f"   Email:   {email}")
        print("   Permission: is_host_admin = 1")
        print("\nYou can now sign in at http://localhost:8000/frontend2/host-login.html")
    except Exception as exc:
        print(f"\n❌ ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
