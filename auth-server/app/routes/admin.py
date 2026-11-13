"""
GARI Auth Server 1.0 — Administrative Management Endpoints
"""
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.session import SessionModel
from app.models.security_event import SecurityEvent
from app.schemas.auth import UserResponse, MessageResponse
from app.schemas.admin import (
    AdminBootstrapRequest,
    AdminUserListResponse,
    AdminUserDetailResponse,
    AdminUpdateStatusRequest,
    AdminUpdateRoleRequest,
    SecurityEventResponse,
    AdminStatsResponse
)
from app.services.password import hash_password
from app.services.session import revoke_all_user_sessions
from app.services.security_event import log_security_event
from app.middleware.rate_limit import get_client_ip
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/v1/admin", tags=["Administration"])


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency: Restricts endpoint access strictly to accounts with account_type == 'admin'."""
    if user.account_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền quản trị viên hệ thống để thực hiện thao tác này."
        )
    return user


@router.post("/bootstrap", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(
    req: AdminBootstrapRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Initial one-time administrator bootstrap.
    Requires an explicit server-configured token (BOOTSTRAP_ADMIN_TOKEN).
    Cannot be reused once an admin account has been provisioned.
    """
    ip = get_client_ip(request)

    # 1. Verify token is configured
    configured_token = settings.BOOTSTRAP_ADMIN_TOKEN.strip()
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Quy trình khởi tạo quản trị viên chưa được kích hoạt trên máy chủ."
        )

    # 2. Constant-time token comparison
    if not secrets.compare_digest(req.bootstrap_token, configured_token):
        log_security_event(db, "BOOTSTRAP_FAILED_BAD_TOKEN", ip_address=ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Khóa bí mật khởi tạo không chính xác."
        )

    # 3. Prevent duplicate bootstrap: check if an admin already exists
    admin_exists = db.query(User).filter(User.account_type == "admin").first()
    if admin_exists:
        log_security_event(db, "BOOTSTRAP_REJECTED_ALREADY_EXISTS", ip_address=ip)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hệ thống đã có tài khoản quản trị viên. Quy trình khởi tạo ban đầu bị khóa vĩnh viễn."
        )

    # 4. Check email conflict
    normalized_email = req.email.strip().lower()
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Địa chỉ email này đã tồn tại trong hệ thống."
        )

    # 5. Create the initial administrator
    hashed = hash_password(req.password)
    admin_user = User(
        email=normalized_email,
        password_hash=hashed,
        full_name=req.full_name.strip(),
        account_type="admin",
        is_active=True,
        is_verified=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    log_security_event(
        db,
        "ADMIN_BOOTSTRAP_SUCCESS",
        user_id=admin_user.id,
        ip_address=ip,
        metadata={"email": admin_user.email}
    )

    return UserResponse.model_validate(admin_user)


@router.get("/stats", response_model=AdminStatsResponse)
def get_stats(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Retrieves operational stats and registration capacity metrics."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active.is_(True)).count()
    registered_farmers = db.query(User).filter(User.account_type != "admin").count()
    active_sessions = db.query(SessionModel).filter(SessionModel.revoked_at.is_(None)).count()

    remaining = max(0, settings.MAX_REGISTRATION_ACCOUNTS - registered_farmers)

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        registered_farmers=registered_farmers,
        capacity_limit=settings.MAX_REGISTRATION_ACCOUNTS,
        capacity_remaining=remaining,
        registration_open=settings.REGISTRATION_OPEN,
        active_sessions=active_sessions
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Lists users with pagination."""
    total = db.query(User).count()
    offset = (page - 1) * page_size
    users = db.query(User).order_by(User.id.desc()).offset(offset).limit(page_size).all()

    return AdminUserListResponse(
        total=total,
        page=page,
        page_size=page_size,
        users=[UserResponse.model_validate(u) for u in users]
    )


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
def get_user_detail(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Returns detailed user record including active session count."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

    active_sessions = db.query(SessionModel).filter(
        SessionModel.user_id == user_id,
        SessionModel.revoked_at.is_(None)
    ).count()

    resp = AdminUserDetailResponse.model_validate(user)
    resp.active_sessions_count = active_sessions
    return resp


@router.post("/users/{user_id}/status", response_model=MessageResponse)
def update_user_status(
    user_id: int,
    req: AdminUpdateStatusRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Activates or deactivates an account. Deactivation automatically revokes all sessions."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

    if user.id == admin.id and not req.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quản trị viên không thể tự vô hiệu hóa tài khoản của chính mình."
        )

    user.is_active = req.is_active
    db.commit()

    if not req.is_active:
        revoke_all_user_sessions(db, user_id)

    log_security_event(
        db,
        "ADMIN_USER_STATUS_CHANGED",
        user_id=admin.id,
        metadata={"target_user_id": user_id, "is_active": req.is_active}
    )

    state_str = "kích hoạt" if req.is_active else "vô hiệu hóa"
    return MessageResponse(success=True, message=f"Đã {state_str} tài khoản người dùng.")


@router.post("/users/{user_id}/revoke-sessions", response_model=MessageResponse)
def admin_revoke_sessions(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Revokes all active sessions for a given user."""
    revoked = revoke_all_user_sessions(db, user_id)
    log_security_event(
        db,
        "ADMIN_REVOKED_SESSIONS",
        user_id=admin.id,
        metadata={"target_user_id": user_id, "revoked_count": revoked}
    )
    return MessageResponse(success=True, message=f"Đã thu hồi {revoked} phiên hoạt động của người dùng.")


@router.post("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    req: AdminUpdateRoleRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Updates account role (e.g. promote to expert, enterprise, or admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

    old_role = user.account_type
    user.account_type = req.account_type
    db.commit()
    db.refresh(user)

    log_security_event(
        db,
        "ADMIN_USER_ROLE_CHANGED",
        user_id=admin.id,
        metadata={"target_user_id": user_id, "old_role": old_role, "new_role": req.account_type}
    )

    return UserResponse.model_validate(user)


@router.post("/registration/toggle", response_model=MessageResponse)
def toggle_registration(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Opens or closes public account registration."""
    settings.REGISTRATION_OPEN = not settings.REGISTRATION_OPEN
    status_str = "mở" if settings.REGISTRATION_OPEN else "đóng"

    log_security_event(
        db,
        "ADMIN_REGISTRATION_TOGGLED",
        user_id=admin.id,
        metadata={"registration_open": settings.REGISTRATION_OPEN}
    )

    return MessageResponse(success=True, message=f"Cổng đăng ký tài khoản mới hiện đã được {status_str}.")


@router.get("/security-events", response_model=dict)
def list_security_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Retrieves sanitized audit security events."""
    total = db.query(SecurityEvent).count()
    offset = (page - 1) * page_size
    events = db.query(SecurityEvent).order_by(SecurityEvent.id.desc()).offset(offset).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "events": [SecurityEventResponse.model_validate(e) for e in events]
    }
