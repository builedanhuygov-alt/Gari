"""
GARI AI LAB — Dedicated Host Admin CLI Bootstrap Tool
File: bootstrap_host.py

Establishes or promotes an authoritative GARI Host Admin identity:
- Interactive or argument-driven CLI input.
- Strong password hashing with Salt + SHA-256 / pbkdf2.
- Zero hardcoded passwords; zero automatic promotion of arbitrary users.
- Explicit Host Admin privilege assignment (is_host_admin = 1).
- Transactional audit log recording in host_audit_logs.
"""

import argparse
import getpass
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "database" / "disease_detector.db"

sys.path.insert(0, str(ROOT_DIR))
import gari_auth


def validate_password_strength(password: str) -> bool:
    """Ensure password meets production security criteria (min 8 chars, mixed case, number)."""
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    return True


def bootstrap_host(email: str, name: str, password: str, force: bool = False):
    email = email.strip().lower()
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        print(f"[-] Lỗi: Định dạng email không hợp lệ: {email}")
        sys.exit(1)

    if not validate_password_strength(password):
        print("[-] Lỗi: Mật khẩu không đủ mạnh! Yêu cầu tối thiểu 8 ký tự, có chữ hoa, chữ thường và chữ số.")
        sys.exit(1)

    if not DB_PATH.exists():
        print(f"[-] Lỗi: Không tìm thấy cơ sở dữ liệu tại {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    try:
        # Check if user already exists
        cursor.execute("SELECT id, name, is_host_admin FROM users WHERE LOWER(email) = ?", (email,))
        existing = cursor.fetchone()

        password_hash = gari_auth.hash_password(password)

        if existing:
            user_id, existing_name, is_host = existing
            if is_host and not force:
                print(f"[!] Tài khoản '{email}' (ID: {user_id}) đã là Host Admin.")
                update_pw = input("    Bạn có muốn đặt lại mật khẩu Host Admin không? (y/N): ").strip().lower()
                if update_pw != 'y':
                    print("[*] Giữ nguyên mật khẩu hiện tại. Hoàn tất.")
                    return user_id

            cursor.execute("""
                UPDATE users 
                SET password_hash = ?, is_host_admin = 1, is_admin = 1, is_active = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (password_hash, user_id))
            action = "promote_or_reset"
            print(f"[+] Thành công: Đã cấp quyền Host Admin và cập nhật chứng thực cho tài khoản ID #{user_id} ({email}).")
        else:
            cursor.execute("""
                INSERT INTO users (email, name, full_name, password_hash, account_type, is_admin, is_host_admin, is_active)
                VALUES (?, ?, ?, ?, 'expert', 1, 1, 1)
            """, (email, name, name, password_hash))
            user_id = cursor.lastrowid
            action = "create_host_account"
            print(f"[+] Thành công: Đã khởi tạo mới tài khoản Host Admin ID #{user_id} ({email}).")

        # Record Host Audit Log
        cursor.execute("""
            INSERT INTO host_audit_logs (
                host_admin_id, host_email, action_type, target_resource, details_json, reason, outcome
            ) VALUES (?, ?, ?, ?, ?, ?, 'success')
        """, (
            user_id,
            email,
            "BOOTSTRAP_HOST_ADMIN",
            f"user:{user_id}",
            f'{{"action": "{action}", "email": "{email}"}}',
            "CLI Host Bootstrap Procedure executed"
        ))

        conn.commit()
        print(f"[+] Đã ghi nhật ký kiểm toán hệ thống (host_audit_logs) cho Host Admin #{user_id}.")
        return user_id

    except Exception as e:
        conn.rollback()
        print(f"[-] Lỗi trong quá trình bootstrap Host Admin: {e}")
        sys.exit(1)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="GARI 2.0 Dedicated Host Admin CLI Bootstrap Tool")
    parser.add_argument("--email", type=str, help="Email của quản trị viên Host (VD: host@gari.vn)")
    parser.add_argument("--name", type=str, default="GARI Host Administrator", help="Tên hiển thị của quản trị viên Host")
    parser.add_argument("--password", type=str, help="Mật khẩu khởi tạo (nếu không cung cấp, CLI sẽ yêu cầu nhập ẩn)")
    parser.add_argument("--force", action="store_true", help="Bỏ qua xác nhận nếu tài khoản đã tồn tại")

    args = parser.parse_args()

    print("================================================================================")
    print(" GARI 2.0 — DEDICATED HOST ADMIN BOOTSTRAP")
    print("================================================================================")

    email = args.email
    if not email:
        email = input("Nhập địa chỉ Email Host Admin: ").strip()

    name = args.name

    password = args.password
    if not password:
        password = getpass.getpass("Nhập Mật khẩu an toàn (tối thiểu 8 ký tự, có hoa, thường, số): ")
        password_confirm = getpass.getpass("Xác nhận lại Mật khẩu: ")
        if password != password_confirm:
            print("[-] Lỗi: Hai mật khẩu nhập vào không trùng khớp!")
            sys.exit(1)

    bootstrap_host(email, name, password, force=args.force)
    print("================================================================================")
    print(" KHỞI TẠO HOST ADMIN HOÀN TẤT. TRUY CẬP CONSOLE TẠI: /frontend2/host.html")
    print("================================================================================")


if __name__ == "__main__":
    main()
