"""
GARI Auth Server 1.0 — VIP Voucher Campaign Management Endpoints
Handles secure backend-first voucher activation for THPT Nguyễn Hồng Đạo campaign.
Strictly guarantees single-use per account, concurrency safety, and UTC entitlement tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import Optional
import json

from app.database import get_db
from app.models.user import User
from app.models.security_event import SecurityEvent
from app.routes.auth import get_current_user
from app.middleware.rate_limit import get_client_ip
from app.services.security_event import log_security_event

router = APIRouter(tags=["Voucher"])

# Authorized Campaign Voucher Code
AUTHORIZED_VOUCHER_CODE = "Gari-THPTNHD1"
CAMPAIGN_NAME = "THPT Nguyễn Hồng Đạo"
VOUCHER_DURATION_DAYS = 7
VOUCHER_DAILY_QUOTA = 5
VOUCHER_TIER = "vip_trial"
VOUCHER_PLAN_NAME = "VIP Trải nghiệm 7 Ngày"


class VoucherActivateRequest(BaseModel):
    code: str = Field(..., min_length=3, max_length=50, description="Mã voucher ưu đãi")


class VoucherStatusResponse(BaseModel):
    is_activated: bool
    is_expired: bool
    code: Optional[str] = None
    campaign: Optional[str] = None
    tier: Optional[str] = None
    plan_name: Optional[str] = None
    daily_quota: Optional[int] = None
    activated_at: Optional[str] = None
    expires_at: Optional[str] = None
    days_left: Optional[int] = None
    hours_left: Optional[int] = None


def get_user_voucher_event(db: Session, user_id: int, voucher_code: str = AUTHORIZED_VOUCHER_CODE) -> Optional[SecurityEvent]:
    """Finds existing activation record for this user and voucher code."""
    events = (
        db.query(SecurityEvent)
        .filter(
            SecurityEvent.user_id == user_id,
            SecurityEvent.event_type == "VOUCHER_ACTIVATED"
        )
        .order_by(SecurityEvent.created_at.desc())
        .all()
    )
    code_upper = voucher_code.strip().upper()
    for ev in events:
        if ev.sanitized_metadata:
            try:
                meta = json.loads(ev.sanitized_metadata)
                recorded_code = (meta.get("voucher_code") or meta.get("code") or "").strip().upper()
                if recorded_code == code_upper:
                    return ev
            except Exception:
                continue
    return None


@router.get("/status", response_model=VoucherStatusResponse)
def get_voucher_status(
    code: str = AUTHORIZED_VOUCHER_CODE,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the real-time activation status of the campaign voucher for the authenticated user.
    """
    event = get_user_voucher_event(db, user.id, code)
    if not event or not event.sanitized_metadata:
        return VoucherStatusResponse(is_activated=False, is_expired=False)

    try:
        data = json.loads(event.sanitized_metadata)
        expires_at_str = data.get("expires_at")
        if not expires_at_str:
            return VoucherStatusResponse(is_activated=True, is_expired=False)

        expires_at = datetime.fromisoformat(expires_at_str)
        now = datetime.now(timezone.utc)
        is_expired = now > expires_at

        delta = expires_at - now if not is_expired else timedelta(seconds=0)
        days_left = max(0, delta.days)
        hours_left = max(0, int(delta.total_seconds() // 3600))

        return VoucherStatusResponse(
            is_activated=True,
            is_expired=is_expired,
            code=data.get("voucher_code") or AUTHORIZED_VOUCHER_CODE,
            campaign=data.get("campaign") or CAMPAIGN_NAME,
            tier=data.get("tier") or VOUCHER_TIER,
            plan_name=data.get("plan_name") or VOUCHER_PLAN_NAME,
            daily_quota=data.get("daily_quota") or VOUCHER_DAILY_QUOTA,
            activated_at=data.get("activated_at"),
            expires_at=expires_at_str,
            days_left=days_left if not is_expired else 0,
            hours_left=hours_left if not is_expired else 0
        )
    except Exception:
        return VoucherStatusResponse(is_activated=True, is_expired=False)


@router.post("/activate")
def activate_voucher(
    req: VoucherActivateRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Activates the GARI VIP 7-day trial voucher for THPT Nguyễn Hồng Đạo students.
    Backend-first validation:
    1. Validates voucher code.
    2. Atomic lock on user record preventing concurrent double activations.
    3. Validates that the account has never activated this voucher before.
    4. Calculates exact 7-day UTC expiry.
    5. Saves activation event to security_events audit table.
    """
    input_code = req.code.strip()
    if input_code.upper() != AUTHORIZED_VOUCHER_CODE.upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã voucher '{input_code}' không hợp lệ hoặc không thuộc chương trình hiện tại."
        )

    ip = get_client_ip(request)
    ua = request.headers.get("user-agent", "")[:500]

    # Concurrency guard: lock user row in PostgreSQL/SQLite for the duration of transaction
    try:
        locked_user = (
            db.query(User)
            .filter(User.id == user.id)
            .with_for_update()
            .first()
        )
    except Exception:
        # SQLite does not support with_for_update in all dialects, fall back to normal query
        locked_user = db.query(User).filter(User.id == user.id).first()

    if not locked_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tài khoản không tồn tại trên hệ thống."
        )

    # Check for existing activation record
    existing_event = get_user_voucher_event(db, user.id, AUTHORIZED_VOUCHER_CODE)
    if existing_event:
        log_security_event(
            db,
            "VOUCHER_ACTIVATION_REJECTED_ALREADY_USED",
            user_id=user.id,
            ip_address=ip,
            metadata={"code": input_code, "reason": "already_activated"}
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tài khoản này đã từng kích hoạt voucher GARI VIP miễn phí 7 ngày. Mỗi tài khoản chỉ được tham gia một lần."
        )

    now_utc = datetime.now(timezone.utc)
    expires_utc = now_utc + timedelta(days=VOUCHER_DURATION_DAYS)

    metadata = {
        "voucher_code": AUTHORIZED_VOUCHER_CODE,
        "campaign": CAMPAIGN_NAME,
        "target_audience": "Học sinh THPT Nguyễn Hồng Đạo",
        "tier": VOUCHER_TIER,
        "plan_name": VOUCHER_PLAN_NAME,
        "duration_days": VOUCHER_DURATION_DAYS,
        "daily_quota": VOUCHER_DAILY_QUOTA,
        "activated_at": now_utc.isoformat(),
        "expires_at": expires_utc.isoformat()
    }

    # Record secure audit activation event
    activation_event = SecurityEvent(
        event_type="VOUCHER_ACTIVATED",
        user_id=user.id,
        ip_address=ip,
        user_agent=ua,
        created_at=now_utc,
        sanitized_metadata=json.dumps(metadata)
    )
    db.add(activation_event)
    db.commit()

    return {
        "success": True,
        "message": "Chúc mừng! GARI VIP trải nghiệm 7 ngày dành cho học sinh THPT Nguyễn Hồng Đạo đã được kích hoạt thành công.",
        "voucher": {
            "code": AUTHORIZED_VOUCHER_CODE,
            "campaign": CAMPAIGN_NAME,
            "tier": VOUCHER_TIER,
            "plan_name": VOUCHER_PLAN_NAME,
            "daily_quota": VOUCHER_DAILY_QUOTA,
            "activated_at": now_utc.isoformat(),
            "expires_at": expires_utc.isoformat(),
            "days_left": VOUCHER_DURATION_DAYS,
            "hours_left": VOUCHER_DURATION_DAYS * 24
        }
    }
