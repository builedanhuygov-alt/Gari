"""
GARI Auth Server 1.0 — Authentication Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.session import SessionModel
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    ChangePasswordRequest,
    UserResponse,
    LoginResponse,
    MessageResponse
)
from app.services.password import hash_password, verify_password
from app.services.session import (
    create_session,
    validate_session,
    revoke_session,
    revoke_all_user_sessions
)
from app.services.registration import (
    register_user,
    RegistrationCapacityError,
    RegistrationClosedError,
    DuplicateEmailError
)
from app.services.security_event import log_security_event
from app.middleware.rate_limit import rate_limiter, get_client_ip
from app.middleware.csrf import generate_csrf_token

router = APIRouter(tags=["Authentication"])

# Dummy hash for constant-time rejection when user does not exist
DUMMY_ARGON2_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdHNhbHQxMjM0NTY3OA$9W/a2QG76m4B6f3x4f8wZg0kG8hR0mG0kG8hR0mG0kE"


def get_token_from_request(request: Request) -> Optional[str]:
    """Retrieves session token from HttpOnly cookie or Authorization Bearer header."""
    cookie_token = request.cookies.get(settings.COOKIE_NAME)
    if cookie_token:
        return cookie_token

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dependency: Resolves and validates the authenticated user from the session token."""
    raw_token = get_token_from_request(request)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu đăng nhập để truy cập tài nguyên này."
        )

    user, session_record = validate_session(db, raw_token)
    if not user or not session_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại."
        )

    return user


def set_session_cookie(response: Response, raw_token: str, remember_me: bool = False):
    """Sets a secure HttpOnly session cookie on the outgoing response."""
    max_age = settings.SESSION_MAX_LIFETIME_SECONDS if remember_me else settings.SESSION_TTL_SECONDS
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=raw_token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )


@router.get("/csrf", response_model=dict)
def get_csrf(request: Request, response: Response):
    """Generates or retrieves CSRF token for the frontend client."""
    token = request.cookies.get(settings.CSRF_COOKIE_NAME) or generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )
    return {"success": True, "csrf_token": token}


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(
    req: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Registers a new user within the strictly enforced 10-account limit."""
    ip = get_client_ip(request)
    ua = request.headers.get("User-Agent")

    # Rate limiting by IP: max 5 attempts per hour
    allowed, retry_after = rate_limiter.is_allowed(
        f"register:ip:{ip}",
        settings.RATE_LIMIT_REGISTER_MAX_ATTEMPTS,
        settings.RATE_LIMIT_REGISTER_WINDOW_SECONDS
    )
    if not allowed:
        log_security_event(db, "REGISTER_RATE_LIMITED", ip_address=ip, user_agent=ua)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quá nhiều yêu cầu đăng ký từ địa chỉ này. Vui lòng thử lại sau {retry_after} giây.",
            headers={"Retry-After": str(retry_after)}
        )

    try:
        user = register_user(db, req.email, req.password, req.resolved_name)
    except RegistrationCapacityError as e:
        log_security_event(db, "REGISTER_CAPACITY_REJECTED", ip_address=ip, user_agent=ua, metadata={"email": req.email})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RegistrationClosedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except DuplicateEmailError:
        log_security_event(db, "REGISTER_DUPLICATE_EMAIL", ip_address=ip, user_agent=ua, metadata={"email": req.email})
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Địa chỉ email này đã được sử dụng.")

    # Create initial session upon successful registration
    session_record, raw_token = create_session(db, user.id, remember_me=False)
    set_session_cookie(response, raw_token, remember_me=False)

    csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME) or generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )

    log_security_event(db, "REGISTER_SUCCESS", user_id=user.id, ip_address=ip, user_agent=ua)

    return LoginResponse(
        success=True,
        message="Đăng ký tài khoản thành công.",
        user=UserResponse.model_validate(user),
        csrf_token=csrf_token
    )


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Authenticates a user using email and Argon2id password."""
    ip = get_client_ip(request)
    ua = request.headers.get("User-Agent")

    # Rate limiting by IP and by account email
    allowed_ip, retry_ip = rate_limiter.is_allowed(
        f"login:ip:{ip}",
        settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS,
        settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS
    )
    allowed_email, retry_email = rate_limiter.is_allowed(
        f"login:email:{req.email}",
        settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS,
        settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS
    )
    if not allowed_ip or not allowed_email:
        retry_after = max(retry_ip, retry_email)
        log_security_event(db, "LOGIN_RATE_LIMITED", ip_address=ip, user_agent=ua, metadata={"email": req.email})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quá nhiều lần thử đăng nhập thất bại. Vui lòng thử lại sau {retry_after} giây.",
            headers={"Retry-After": str(retry_after)}
        )

    user = db.query(User).filter(User.email == req.email).first()

    # Constant-time password verification even if user does not exist
    if not user:
        verify_password(req.password, DUMMY_ARGON2_HASH)
        log_security_event(db, "LOGIN_FAILED_UNKNOWN_USER", ip_address=ip, user_agent=ua, metadata={"email": req.email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác."
        )

    if not user.is_active:
        log_security_event(db, "LOGIN_FAILED_INACTIVE_USER", user_id=user.id, ip_address=ip, user_agent=ua)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này hiện đang bị tạm khóa. Vui lòng liên hệ quản trị viên."
        )

    if not verify_password(req.password, user.password_hash):
        log_security_event(db, "LOGIN_FAILED_WRONG_PASSWORD", user_id=user.id, ip_address=ip, user_agent=ua)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác."
        )

    # Success: Reset rate limiter and issue session
    rate_limiter.reset(f"login:ip:{ip}")
    rate_limiter.reset(f"login:email:{req.email}")

    session_record, raw_token = create_session(db, user.id, remember_me=req.remember_me)
    set_session_cookie(response, raw_token, remember_me=req.remember_me)

    csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME) or generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/"
    )

    log_security_event(db, "LOGIN_SUCCESS", user_id=user.id, ip_address=ip, user_agent=ua)

    return LoginResponse(
        success=True,
        message="Đăng nhập thành công.",
        user=UserResponse.model_validate(user),
        csrf_token=csrf_token
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Revokes the current session and clears the session cookie."""
    raw_token = get_token_from_request(request)
    if raw_token:
        revoke_session(db, raw_token)

    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE
    )
    return MessageResponse(success=True, message="Đăng xuất thành công.")


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    """Returns the currently authenticated user profile."""
    return UserResponse.model_validate(user)


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    req: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Changes password and revokes all other sessions for security."""
    if not verify_password(req.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không chính xác."
        )

    user.password_hash = hash_password(req.new_password)
    db.commit()

    # Revoke all other active sessions except current
    current_token = get_token_from_request(request)
    revoked_count = revoke_all_user_sessions(db, user.id, except_raw_token=current_token)

    ip = get_client_ip(request)
    log_security_event(
        db,
        "PASSWORD_CHANGED",
        user_id=user.id,
        ip_address=ip,
        metadata={"other_sessions_revoked": revoked_count}
    )

    return MessageResponse(success=True, message="Đổi mật khẩu thành công.")


@router.post("/revoke-sessions", response_model=MessageResponse)
def revoke_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revokes all other active sessions for the user."""
    current_token = get_token_from_request(request)
    revoked = revoke_all_user_sessions(db, user.id, except_raw_token=current_token)
    return MessageResponse(success=True, message=f"Đã hủy {revoked} phiên đăng nhập khác.")
