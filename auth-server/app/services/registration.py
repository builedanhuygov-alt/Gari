"""
GARI Auth Server 1.0 — Registration Service with Transaction-Safe Capacity Limiting
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.user import User
from app.services.password import hash_password
from app.config import settings


class RegistrationCapacityError(Exception):
    """Raised when the maximum registration capacity has been reached."""
    pass


class RegistrationClosedError(Exception):
    """Raised when public registration has been administratively disabled."""
    pass


class DuplicateEmailError(Exception):
    """Raised when an account with the normalized email already exists."""
    pass


def get_current_registered_count(db: Session) -> int:
    """
    Counts total eligible registered accounts toward the capacity limit.
    Only non-admin accounts count toward public test capacity.
    """
    return db.query(User).filter(User.account_type != "admin").count()


def register_user(
    db: Session,
    email: str,
    password: str,
    full_name: str
) -> User:
    """
    Executes transaction-safe user registration with atomic capacity limit enforcement.
    1. Checks if public registration is open.
    2. Starts an IMMEDIATE transaction to lock SQLite against concurrent race conditions.
    3. Counts active non-admin users.
    4. Rejects if capacity >= MAX_REGISTRATION_ACCOUNTS.
    5. Normalizes email and verifies uniqueness.
    6. Hashes password with Argon2id and inserts record.
    7. Strictly forces account_type='farmer'.
    """
    if not settings.REGISTRATION_OPEN:
        raise RegistrationClosedError("Cổng đăng ký tài khoản mới hiện đang tạm đóng.")

    normalized_email = email.strip().lower()

    # SQLite BEGIN IMMEDIATE ensures an exclusive write lock from the start of the transaction,
    # preventing concurrent threads/processes from reading count and inserting past 10.
    db.connection().execute(text("BEGIN IMMEDIATE"))

    # Check capacity limit inside the write-locked transaction
    current_count = db.query(User).filter(User.account_type != "admin").count()
    if current_count >= settings.MAX_REGISTRATION_ACCOUNTS:
        raise RegistrationCapacityError(
            f"Cổng đăng ký tài khoản mới hiện đã đạt giới hạn thử nghiệm "
            f"({settings.MAX_REGISTRATION_ACCOUNTS} tài khoản). Vui lòng liên hệ quản trị viên."
        )

    # Check email duplicate inside the transaction
    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        raise DuplicateEmailError("Địa chỉ email này đã được sử dụng.")

    # Create user with Argon2id hash and forced 'farmer' role
    hashed = hash_password(password)
    user = User(
        email=normalized_email,
        password_hash=hashed,
        full_name=full_name.strip(),
        account_type="farmer",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
