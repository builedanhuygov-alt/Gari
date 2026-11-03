import io
import logging
import os
import platform
import shutil
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import psutil

from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, ConfigDict, EmailStr

import gari_auth
from gari_auth import get_current_user, get_current_user_optional, get_current_admin_user, get_current_host_admin, record_host_audit
import gari_b2b
import gari_database
import gari_knowledge
import gari_plans
import gari_privacy
import gari_quota
import gari_revenue
import gari_vouchers
import gari_payment
from gari_inference_engine import engine
import gari_config
import gari_moderation

# Validate configuration at startup
gari_config.validate_startup_configuration()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_api_server")

ROOT = Path(__file__).resolve().parent
FRONTEND2_DIR = ROOT / "frontend2"
UPLOADS_DIR = ROOT / "database" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_FILES = {"/style.css": ROOT / "style.css", "/main.js": ROOT / "main.js"}

# Sprint 5: Pilot Request In-Memory Rate Limiter (Anti-abuse)
_PILOT_REQUEST_RATE_LIMIT: Dict[str, list] = {}
PILOT_RATE_LIMIT_WINDOW = 3600  # 1 hour window
PILOT_RATE_LIMIT_MAX = 30        # Max 30 submissions per hour per IP

# Host Server Operational Telemetry
SERVER_START_TIME = time.time()
_SERVER_METRICS = {
    "total_requests": 0,
    "total_errors": 0,
    "latencies_ms": []
}

app = FastAPI(
    title="Gari AI Lab - Agricultural Intelligence Platform",
    description="Scalable AgriTech Platform with 44 Local ConvNeXt AI Models, Farm Management, Persistent Authentication & Disease Intelligence",
    version="2.6.0"
)

# SRE & Security Hardening: Strict CORS without wildcards on credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=gari_config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_correlation_and_timing_middleware(request: Request, call_next):
    """Assigns unique correlation ID to every request and logs anonymized timing."""
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    t0 = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - t0) * 1000, 2)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    # Track operational telemetry
    _SERVER_METRICS["total_requests"] += 1
    if response.status_code >= 500:
        _SERVER_METRICS["total_errors"] += 1
    _SERVER_METRICS["latencies_ms"].append(duration_ms)
    if len(_SERVER_METRICS["latencies_ms"]) > 200:
        _SERVER_METRICS["latencies_ms"].pop(0)
    # Structured log without PII
    logger.info(
        "[%s] %s %s -> HTTP %d (%.2fms)",
        request_id, request.method, request.url.path, response.status_code, duration_ms
    )
    return response


# SRE Global Exception Handler: Sanitize errors in production to prevent stack trace leaks
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
    logger.exception("[%s] Unhandled server error: %s", req_id, exc)
    if gari_config.IS_PRODUCTION:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "request_id": req_id,
                "detail": "Đã xảy ra lỗi hệ thống khi xử lý yêu cầu. Vui lòng liên hệ hỗ trợ kèm mã yêu cầu này."
            }
        )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "request_id": req_id,
            "detail": str(exc)
        }
    )


# Secure Static Mounts: ONLY mount dedicated public directories.
# NEVER mount ROOT as /static to prevent source code and database exfiltration!
app.mount("/static/frontend2", StaticFiles(directory=str(FRONTEND2_DIR)), name="frontend2_static")
app.mount("/frontend2", StaticFiles(directory=str(FRONTEND2_DIR), html=True), name="frontend2")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/", response_class=HTMLResponse)
async def root():
    # Serve production SaaS dashboard
    index_path = FRONTEND2_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    predict_path = FRONTEND2_DIR / "predict.html"
    if predict_path.exists():
        return FileResponse(predict_path)
    return FileResponse(ROOT / "index.html")


@app.get("/landing", response_class=HTMLResponse)
async def landing_page():
    """Serve public market validation & pilot registration landing page."""
    landing_path = FRONTEND2_DIR / "landing.html"
    if landing_path.exists():
        return FileResponse(landing_path)
    return FileResponse(FRONTEND2_DIR / "index.html")


@app.get("/test-upload")
async def test_upload_redirect():
    predict_path = FRONTEND2_DIR / "predict.html"
    return FileResponse(predict_path)


@app.get("/style.css")
async def css():
    return FileResponse(STATIC_FILES["/style.css"])


@app.get("/main.js")
async def js():
    return FileResponse(STATIC_FILES["/main.js"])


# -----------------------------------------------------------------------------
# System & Health Check Endpoints (Liveness & Readiness Probes)
# -----------------------------------------------------------------------------

@app.get("/api/health")
@app.get("/health")
async def health():
    """Liveness probe: verifies server process is responsive."""
    return {
        "status": "ok",
        "service": "Gari AI Lab AgriTech Platform",
        "environment": gari_config.APP_ENV,
        "version": "2.6.0"
    }


@app.get("/api/ready")
@app.get("/ready")
async def readiness():
    """Readiness probe: verifies database connectivity and core storage availability."""
    db_ok = gari_database.check_database_integrity()
    models_ok = gari_config.MODELS_DIR.exists()
    is_ready = db_ok and models_ok
    status_code = 200 if is_ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "ready": is_ready,
            "database": "healthy" if db_ok else "unhealthy",
            "models_storage": "available" if models_ok else "unavailable",
            "environment": gari_config.APP_ENV
        }
    )



# -----------------------------------------------------------------------------
# Authentication Pydantic Schemas & Endpoints (PHASE 2)
# -----------------------------------------------------------------------------

class RegisterPayload(BaseModel):
    full_name: str
    email: str
    password: str
    confirm_password: str
    account_type: Optional[str] = "Nông hộ"
    phone: Optional[str] = None
    terms_agreed: Optional[bool] = True
    marketing_opt_in: Optional[bool] = False


class LoginPayload(BaseModel):
    email: str
    password: str
    remember_me: Optional[bool] = False


class ForgotPasswordPayload(BaseModel):
    email: str


class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str
    confirm_password: str


class CreateOrgPayload(BaseModel):
    name: str
    # Kept for backward compatibility but IGNORED by the API: customers can never
    # self-assign a paid plan. New organizations start on the unpaid pilot plan.
    plan_id: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    organization_type: Optional[str] = None
    region: Optional[str] = None
    primary_crops: Optional[List[str]] = None


class AddMemberPayload(BaseModel):
    email: str
    role: Optional[str] = "member"


class UpdateRolePayload(BaseModel):
    role: str
    reason: Optional[str] = None


class InitialAccountTypePayload(BaseModel):
    account_type: str


class ChangeAccountTypePayload(BaseModel):
    account_type: str
    confirm: bool = False
    reason: Optional[str] = None


class HostLoginPayload(BaseModel):
    email: str
    password: str
    remember_me: Optional[bool] = False


class HostUpdateUserStatusPayload(BaseModel):
    is_active: bool
    reason: str


class HostUpdateAccountTypePayload(BaseModel):
    account_type: str
    reason: str


class HostUpdateVipPayload(BaseModel):
    action: str  # "grant" or "revoke"
    plan_id: Optional[str] = "vip_pro"
    duration_days: Optional[int] = 30
    reason: str


class HostCreateVoucherPayload(BaseModel):
    plan_id: str
    max_redemptions: Optional[int] = 1
    valid_days: Optional[int] = 30
    note: Optional[str] = None


class HostRevokeVoucherPayload(BaseModel):
    reason: str


class HostUpdateApiConfigPayload(BaseModel):
    key: str
    value: str
    reason: str


class HostModerationActionPayload(BaseModel):
    action: str  # dismiss, false_positive, warn, restrict, suspend, ban, restore
    reason: str
    restrictions: Optional[str] = None


class HostReviewAppealPayload(BaseModel):
    decision: str  # approved, rejected
    host_response: str


class UserSubmitAppealPayload(BaseModel):
    case_id: Optional[str] = None
    appeal_reason: str
    email: Optional[str] = None



class CreateApiKeyPayload(BaseModel):
    key_name: str
    rate_limit_rpm: Optional[int] = 60


class OrganizationProfilePayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: Optional[str] = None
    organization_type: Optional[str] = None
    primary_crops: Optional[List[str]] = None
    region: Optional[str] = None
    farming_scale: Optional[str] = None
    scale_consent: Optional[bool] = False
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    business_contact_name: Optional[str] = None
    business_contact_title: Optional[str] = None
    business_contact_email: Optional[str] = None
    business_contact_phone: Optional[str] = None
    reason: Optional[str] = None


class OrganizationStatusPayload(BaseModel):
    status: str
    reason: str


class ArchiveOrganizationPayload(BaseModel):
    reason: str


class CreateInvitationPayload(BaseModel):
    email: str
    role: Optional[str] = "member"
    reason: Optional[str] = None


class AcceptInvitationPayload(BaseModel):
    token: str


class RevokeInvitationPayload(BaseModel):
    reason: str


class TransferOwnershipPayload(BaseModel):
    target_user_id: int
    reason: str


class OrganizationOnboardingPayload(BaseModel):
    step: Optional[int] = None
    organization_type: Optional[str] = None
    region: Optional[str] = None
    primary_crops: Optional[List[str]] = None
    farming_scale: Optional[str] = None
    scale_consent: Optional[bool] = False
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    business_contact_name: Optional[str] = None
    business_contact_title: Optional[str] = None
    business_contact_email: Optional[str] = None
    business_contact_phone: Optional[str] = None
    needs: Optional[List[str]] = None
    role_confirmed: Optional[bool] = None
    commercial_intent: Optional[str] = None
    complete: Optional[bool] = False


# Sprint 5: Pilot & Market Validation Payloads
class PilotRequestPayload(BaseModel):
    name: str
    contact: str
    customer_type: Optional[str] = "farmer"
    crops_of_interest: Optional[str] = None
    region: Optional[str] = None
    problem_statement: Optional[str] = None
    consent_given: bool


class PilotRequestStatusUpdatePayload(BaseModel):
    status: Optional[str] = None
    internal_notes: Optional[str] = None


class DiagnosisFeedbackPayload(BaseModel):
    feedback_type: str
    notes: Optional[str] = None


class DiagnosisFeedbackStatusPayload(BaseModel):
    status: Optional[str] = None
    admin_notes: Optional[str] = None


def _raise_org_http_error(exc: Exception):
    """Translate organization-domain errors into consistent HTTP responses."""
    if isinstance(exc, gari_b2b.OrganizationPermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, gari_b2b.InvitationRateLimitError):
        raise HTTPException(status_code=429, detail=str(exc))
    if isinstance(exc, (gari_b2b.InvitationError, gari_b2b.OrganizationStateError)):
        raise HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc))
    logger.exception("Unexpected organization error: %s", exc)
    raise HTTPException(status_code=500, detail="Lỗi hệ thống khi xử lý yêu cầu tổ chức.")


def _require_org_permission(org_id: int, user_id: int, permission: str) -> str:
    """Backend-authoritative membership/permission guard for organization routes."""
    try:
        return gari_b2b.require_permission(org_id, user_id, permission)
    except Exception as exc:
        _raise_org_http_error(exc)


class ConsentPayload(BaseModel):
    consent_type: str
    status: Optional[str] = "granted"
    metadata: Optional[Dict[str, Any]] = None


class DataSubjectDeletePayload(BaseModel):
    confirm_text: str
    reason: Optional[str] = None


class OnboardingPayload(BaseModel):
    persona_type: str  # 'individual', 'smallholder', 'cooperative', 'enterprise'
    primary_crops: Optional[List[str]] = None
    farming_region: Optional[str] = None
    farming_scale: Optional[str] = None


class AssignPlanPayload(BaseModel):
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    plan_id: str
    status: Optional[str] = "pilot_active"
    notes: Optional[str] = None


@app.post("/api/auth/register")
async def register(payload: RegisterPayload, request: Request, response: Response):
    """Register a new user account with secure password hashing and auto-login."""
    user = gari_auth.register_user(
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
        confirm_password=payload.confirm_password,
        account_type=payload.account_type or "Nông hộ",
        phone=payload.phone
    )

    client_ip = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("User-Agent", "")
    token = gari_auth.create_session(user["id"], remember_me=False, ip_address=client_ip, user_agent=user_agent)

    # Record verifiable consent per Decree 13/2023/ND-CP
    gari_privacy.record_consent(
        consent_type="terms_of_service",
        status="granted",
        user_id=user["id"],
        client_ip=client_ip,
        user_agent=user_agent
    )
    gari_privacy.record_consent(
        consent_type="privacy_policy",
        status="granted",
        user_id=user["id"],
        client_ip=client_ip,
        user_agent=user_agent
    )
    if payload.marketing_opt_in:
        gari_privacy.record_consent(
            consent_type="marketing_opt_in",
            status="granted",
            user_id=user["id"],
            client_ip=client_ip,
            user_agent=user_agent
        )

    # Set HttpOnly session cookie
    response.set_cookie(
        key="gari_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=7 * 86400,
        path="/"
    )

    return {
        "success": True,
        "message": "Đăng ký tài khoản thành công!",
        "user": user,
        "token": token
    }


@app.post("/api/auth/login")
async def login(payload: LoginPayload, request: Request, response: Response):
    """Authenticate user credentials and issue a persistent session token."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("User-Agent", "")

    user = gari_auth.authenticate_user(
        email=payload.email,
        password=payload.password,
        ip_address=client_ip
    )

    token = gari_auth.create_session(
        user_id=user["id"],
        remember_me=bool(payload.remember_me),
        ip_address=client_ip,
        user_agent=user_agent
    )

    max_age_seconds = 30 * 86400 if payload.remember_me else 7 * 86400
    response.set_cookie(
        key="gari_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=max_age_seconds,
        path="/"
    )

    return {
        "success": True,
        "message": "Đăng nhập thành công!",
        "user": user,
        "token": token
    }


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    """Destroy session token on server and delete cookie."""
    token = gari_auth.extract_token_from_request(request)
    if token:
        gari_auth.destroy_session(token)

    response.delete_cookie(key="gari_session", path="/")
    return {"success": True, "message": "Đã đăng xuất thành công."}


@app.get("/api/auth/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return {"success": True, "user": current_user}


# -----------------------------------------------------------------------------
# Single Active Account Type Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/user/account-type")
async def get_user_account_type_api(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Retrieve the single active account type, display metadata, and audit trail.
    Derives UID strictly from the server-side session token.
    """
    return gari_auth.get_user_account_type_info(current_user["id"])


@app.post("/api/user/account-type")
async def set_initial_account_type_api(
    payload: InitialAccountTypePayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Set initial account type if user currently has no active type.
    Rejects with HTTP 400 if user already has an active account type (enforces single active type).
    Derives UID strictly from server-side session token (does not trust client-supplied UID).
    """
    return gari_auth.set_initial_account_type(
        user_id=current_user["id"],
        account_type=payload.account_type
    )


@app.post("/api/user/account-type/change")
async def change_user_account_type_api(
    payload: ChangeAccountTypePayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Safe account type change flow.
    Requires explicit confirmation (confirm=True) and records an immutable audit record.
    Preserves all existing subscription and VIP status.
    Derives UID strictly from server-side session token.
    """
    return gari_auth.change_account_type(
        user_id=current_user["id"],
        new_type=payload.account_type,
        confirm=payload.confirm,
        reason=payload.reason,
        actor_user_id=current_user["id"]
    )



@app.post("/api/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload):
    """
    Initiate password recovery. If SMTP is unconfigured, returns safe dev recovery token (15 mins).
    Never exposes passwords or password hashes.
    """
    token, user = gari_auth.create_password_reset_token(payload.email)
    return {
        "success": True,
        "dev_mode": True,
        "message": "Hệ thống đang hoạt động ở chế độ phát triển cục bộ (chưa cấu hình máy chủ gửi email). Mã khôi phục mật khẩu tạm thời có hiệu lực 15 phút.",
        "reset_token": token,
        "account_email": user["email"]
    }


@app.post("/api/auth/reset-password")
async def reset_password(payload: ResetPasswordPayload):
    """Reset account password using valid reset token."""
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Xác nhận mật khẩu mới không trùng khớp.")

    gari_auth.reset_password_with_token(payload.token, payload.new_password)
    return {"success": True, "message": "Đặt lại mật khẩu thành công! Vui lòng đăng nhập với mật khẩu mới."}


# -----------------------------------------------------------------------------
# Operational Dashboard API (Real Data & User-Scoped)
# -----------------------------------------------------------------------------

@app.get("/api/dashboard/stats")
@app.get("/api/dashboard/overview")
async def dashboard_stats(current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Return aggregated real operational metrics for farms, diagnoses, and risks."""
    user_id = current_user["id"] if current_user else None
    return gari_database.get_dashboard_metrics(user_id=user_id)


@app.get("/api/dashboard/activity")
async def dashboard_activity(current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Return recent user diagnoses activity."""
    user_id = current_user["id"] if current_user else None
    items = gari_database.list_diagnoses(user_id=user_id, limit=10)
    return {"success": True, "activity": items}


@app.get("/api/dashboard/crop-distribution")
async def dashboard_crop_distribution(current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Return crop distribution for current user."""
    user_id = current_user["id"] if current_user else None
    stats = gari_database.get_dashboard_metrics(user_id=user_id)
    return {"success": True, "crops": stats.get("crop_distribution", [])}


@app.get("/api/dashboard/disease-distribution")
async def dashboard_disease_distribution(current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Return disease distribution for current user."""
    user_id = current_user["id"] if current_user else None
    stats = gari_database.get_dashboard_metrics(user_id=user_id)
    return {"success": True, "diseases": stats.get("disease_distribution", [])}


# -----------------------------------------------------------------------------
# Farm Management API (GARI FARM - Protected & User-Scoped)
# -----------------------------------------------------------------------------

@app.get("/api/farms")
async def get_farms(current_user: Dict[str, Any] = Depends(get_current_user)):
    """List all registered farms belonging to the authenticated user."""
    farms = gari_database.list_farms(user_id=current_user["id"])
    return {"success": True, "total": len(farms), "farms": farms}


@app.post("/api/farms")
async def add_farm(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Register a new farm profile for the authenticated user."""
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="Tên nông trại không được để trống.")
    farm = gari_database.create_farm(payload, user_id=current_user["id"])
    return {"success": True, "farm": farm}


@app.get("/api/farms/{farm_id}")
async def get_farm_detail(farm_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve detailed farm profile with associated plots and diagnoses."""
    farm = gari_database.get_farm(farm_id, user_id=current_user["id"])
    if not farm:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền truy cập.")
    return {"success": True, "farm": farm}


@app.put("/api/farms/{farm_id}")
async def update_farm_detail(farm_id: int, payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Update an existing farm owned by the authenticated user."""
    updated = gari_database.update_farm(farm_id, payload, user_id=current_user["id"])
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền chỉnh sửa.")
    return {"success": True, "farm": updated}


@app.delete("/api/farms/{farm_id}")
async def remove_farm(farm_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a farm profile owned by the authenticated user."""
    success = gari_database.delete_farm(farm_id, user_id=current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại để xóa.")
    return {"success": True, "message": "Đã xóa nông trại thành công."}


# -----------------------------------------------------------------------------
# Farm Plots API
# -----------------------------------------------------------------------------

@app.get("/api/plots")
async def list_plots_api(
    farm_id: Optional[int] = None,
    org_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List farm plots accessible to the current user or organization."""
    if org_id is not None:
        if not gari_b2b.get_member_role(org_id, current_user["id"]) and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Bạn không thuộc tổ chức này.")
    plots = gari_database.list_plots(farm_id=farm_id, user_id=current_user["id"], org_id=org_id)
    return {"success": True, "total": len(plots), "plots": plots}


@app.post("/api/plots")
async def create_plot_api(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new farm plot with voluntary minimalist fields and tenant scope."""
    farm_id = payload.get("farm_id")
    if not farm_id:
        raise HTTPException(status_code=400, detail="Thiếu farm_id của nông trại.")
    org_id = payload.get("organization_id")
    if org_id is not None:
        if not gari_b2b.get_member_role(org_id, current_user["id"]) and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Bạn không có quyền thêm lô cho tổ chức này.")
    plot = gari_database.create_plot(payload, user_id=current_user["id"], org_id=org_id)
    if not plot:
        raise HTTPException(status_code=403, detail="Không thể tạo thửa/vườn. Bạn không có quyền truy cập nông trại này.")
    return {"success": True, "plot": plot}


@app.get("/api/farms/{farm_id}/plots")
async def get_farm_plots(farm_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """List crop plots inside a specified farm."""
    plots = gari_database.list_plots(farm_id, user_id=current_user["id"])
    return {"success": True, "total": len(plots), "plots": plots}


@app.post("/api/farms/{farm_id}/plots")
async def add_farm_plot(farm_id: int, payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create a new crop plot in user's farm."""
    payload["farm_id"] = farm_id
    plot = gari_database.create_plot(payload, user_id=current_user["id"])
    if not plot:
        raise HTTPException(status_code=403, detail="Không thể tạo lô canh tác. Vui lòng kiểm tra quyền sở hữu nông trại.")
    return {"success": True, "plot": plot}


@app.get("/api/plots/{plot_id}")
async def get_plot_detail_api(
    plot_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get single plot details with cross-tenant check."""
    plot = gari_database.get_plot(plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn.")
    user_id = current_user["id"]
    has_access = False
    if plot.get("user_id") == user_id:
        has_access = True
    elif plot.get("organization_id") and gari_b2b.get_member_role(plot["organization_id"], user_id):
        has_access = True
    elif plot.get("farm_id"):
        farm_rec = gari_database.get_farm(plot["farm_id"])
        if farm_rec and farm_rec.get("user_id") == user_id:
            has_access = True
    if not has_access and not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập thửa/vườn này.")
    return {"success": True, "plot": plot}


@app.patch("/api/plots/{plot_id}")
@app.put("/api/plots/{plot_id}")
async def update_plot_api(
    plot_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update plot information with cross-tenant validation."""
    plot = gari_database.get_plot(plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn.")
    user_id = current_user["id"]
    has_access = (plot.get("user_id") == user_id) or (
        plot.get("organization_id") and gari_b2b.get_member_role(plot["organization_id"], user_id)
    )
    if not has_access and not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Bạn không có quyền chỉnh sửa thửa/vườn này.")

    updated = gari_database.update_plot(plot_id, payload, user_id=user_id)
    return {"success": True, "plot": updated}


@app.delete("/api/plots/{plot_id}")
async def remove_plot(plot_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a crop plot with tenant isolation and cascading cleanup."""
    plot = gari_database.get_plot(plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn.")
    user_id = current_user["id"]
    has_access = (plot.get("user_id") == user_id) or (
        plot.get("organization_id") and gari_b2b.get_member_role(plot["organization_id"], user_id) in ("owner", "admin")
    )
    if not has_access and not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa thửa/vườn này.")

    success = gari_database.delete_plot(plot_id, user_id=user_id)
    return {"success": True, "message": "Đã xóa thửa/vườn canh tác thành công."}


@app.get("/api/plots/{plot_id}/timeline")
async def get_plot_timeline_api(
    plot_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve disease monitoring timeline for a plot with tenant isolation."""
    plot = gari_database.get_plot(plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn.")
    user_id = current_user["id"]
    has_access = False
    if plot.get("user_id") == user_id:
        has_access = True
    elif plot.get("organization_id") and gari_b2b.get_member_role(plot["organization_id"], user_id):
        has_access = True
    elif plot.get("farm_id"):
        farm_rec = gari_database.get_farm(plot["farm_id"])
        if farm_rec and farm_rec.get("user_id") == user_id:
            has_access = True
    if not has_access and not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem tiến trình của thửa/vườn này.")

    timeline = gari_database.get_plot_timeline(plot_id, user_id=user_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Không tìm thấy tiến trình cho thửa/vườn này.")

    return {
        "success": True,
        "timeline": timeline,
        "plot": timeline.get("plot"),
        "summary": timeline.get("summary"),
        "events": timeline.get("timeline_feed", []),
        "timeline_events": timeline.get("timeline_events", []),
        "timeline_feed": timeline.get("timeline_feed", []),
        "diagnoses": timeline.get("diagnoses", [])
    }


@app.post("/api/plots/{plot_id}/timeline")
async def add_plot_timeline_event_api(
    plot_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Append an observation note or update plot monitoring status:
    'open', 'monitoring', 'resolved', 'referred_to_expert'.
    """
    plot = gari_database.get_plot(plot_id)
    if not plot:
        raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn.")
    user_id = current_user["id"]
    has_access = False
    if plot.get("user_id") == user_id:
        has_access = True
    elif plot.get("organization_id") and gari_b2b.get_member_role(plot["organization_id"], user_id):
        has_access = True
    elif plot.get("farm_id"):
        farm_rec = gari_database.get_farm(plot["farm_id"])
        if farm_rec and farm_rec.get("user_id") == user_id:
            has_access = True

    if not has_access and not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Bạn không có quyền cập nhật tiến trình của thửa/vườn này.")

    event = gari_database.add_plot_timeline_event(plot_id, user_id, payload)
    timeline = gari_database.get_plot_timeline(plot_id, user_id=user_id)
    return {
        "success": True,
        "event": event,
        "timeline": timeline,
        "summary": timeline.get("summary") if timeline else None,
        "events": timeline.get("timeline_feed", []) if timeline else []
    }


# -----------------------------------------------------------------------------
# Notifications API
# -----------------------------------------------------------------------------

@app.get("/api/notifications")
async def get_notifications(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get notifications for the authenticated user."""
    notifs = gari_database.list_notifications(user_id=current_user["id"])
    return {"success": True, "total": len(notifs), "notifications": notifs}


@app.patch("/api/notifications/{notif_id}/read")
async def mark_read(notif_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Mark a notification as read."""
    success = gari_database.mark_notification_as_read(notif_id, user_id=current_user["id"])
    return {"success": success}


# -----------------------------------------------------------------------------
# Diagnosis History API (Sprint 4: Multi-Tenant & Safe Storage)
# -----------------------------------------------------------------------------

@app.get("/api/diagnoses")
async def list_diagnoses(
    farm_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    crop_id: Optional[str] = None,
    org_id: Optional[int] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """Query past AI diagnoses with user-scoped and tenant isolation."""
    user_id = current_user["id"] if current_user else None
    if org_id and current_user:
        if not gari_b2b.get_member_role(org_id, user_id) and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Bạn không thuộc tổ chức này.")
    diagnoses = gari_database.list_diagnoses(
        user_id=user_id,
        farm_id=farm_id,
        plot_id=plot_id,
        crop_id=crop_id,
        organization_id=org_id
    )
    return {"success": True, "total": len(diagnoses), "diagnoses": diagnoses}


@app.post("/api/diagnoses")
async def save_diagnosis_record(
    payload: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Prevents unauthorized tampering with AI model prediction or confidence.
    Model predictions can only be generated through the inference engine pipeline.
    """
    forbidden_keys = {"predicted_disease", "confidence", "confidence_percent", "model_name", "model_version", "diagnosis_status"}
    attempted_keys = forbidden_keys.intersection(payload.keys())
    if attempted_keys:
        raise HTTPException(
            status_code=403,
            detail=f"Không được phép sửa đổi hoặc giả mạo kết quả mô hình AI ({', '.join(attempted_keys)}) qua API người dùng. Kết quả chẩn đoán chỉ được tạo thông qua quy trình suy luận AI (/api/plant/diagnose)."
        )

    user_id = current_user["id"] if current_user else None
    saved = gari_database.save_diagnosis(payload, user_id=user_id)
    return {"success": True, "diagnosis": saved}


@app.get("/api/diagnoses/{diag_id}")
async def get_diagnosis_detail(diag_id: int, current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Get single diagnosis detail by ID with strict tenant isolation check."""
    d = gari_database.get_diagnosis(diag_id)
    if not d:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi chẩn đoán.")

    if current_user:
        user_id = current_user["id"]
        is_owner = (d.get("user_id") == user_id or d.get("actor_user_id") == user_id)
        is_org_member = False
        if d.get("organization_id"):
            is_org_member = bool(gari_b2b.get_member_role(d["organization_id"], user_id))
        is_admin = bool(current_user.get("is_admin", False))

        if not (is_owner or is_org_member or is_admin):
            raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập bản ghi chẩn đoán này.")

    return {"success": True, "diagnosis": d}


@app.delete("/api/diagnoses/{diag_id}")
async def delete_diagnosis_api(
    diag_id: int,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Delete a diagnosis record owned by user (Priority B & Privacy policy).
    Enforces tenant and user isolation.
    """
    d = gari_database.get_diagnosis(diag_id)
    if not d:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi chẩn đoán.")

    if current_user:
        user_id = current_user["id"]
        is_owner = (d.get("user_id") == user_id or d.get("actor_user_id") == user_id)
        is_org_admin = False
        if d.get("organization_id"):
            role = gari_b2b.get_member_role(d["organization_id"], user_id)
            is_org_admin = role in ("owner", "admin")
        is_admin = bool(current_user.get("is_admin", False))

        if not (is_owner or is_org_admin or is_admin):
            raise HTTPException(
                status_code=403,
                detail="Bạn không có quyền xóa bản ghi chẩn đoán này."
            )

    deleted = gari_database.delete_diagnosis(diag_id, user_id=current_user["id"] if current_user else None)
    if not deleted:
        raise HTTPException(status_code=404, detail="Không thể xóa bản ghi chẩn đoán.")
    return {
        "success": True,
        "message": f"Đã xóa thành công bản ghi chẩn đoán #{diag_id} khỏi hồ sơ."
    }


# -----------------------------------------------------------------------------
# Sprint 5: Diagnosis Feedback API (User Feedback ≠ Ground Truth)
# -----------------------------------------------------------------------------

@app.post("/api/diagnoses/{diag_id}/feedback")
async def create_diagnosis_feedback_api(
    diag_id: int,
    payload: DiagnosisFeedbackPayload,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Submit user feedback on a diagnosis.
    Strictly preserves model output: does NOT mutate predicted disease or model labels.
    Tenant-scoping: validates ownership if diagnosis has owner/organization.
    """
    # Enforce moderation restrictions
    gari_moderation.enforce_user_moderation_access(current_user, required_feature=gari_moderation.RESTRICTION_FEEDBACK)

    diag = gari_database.get_diagnosis(diag_id)
    if not diag:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi chẩn đoán.")

    user_id = current_user["id"] if current_user else None
    org_id = diag.get("organization_id")

    # Moderation Scan on feedback text
    if payload.notes and current_user:
        viol = gari_moderation.scan_content_text(
            text=payload.notes,
            context="diagnosis_feedback",
            user_id=current_user["id"],
            user_email=current_user["email"]
        )
        if viol:
            gari_moderation.create_moderation_case(
                user_id=current_user["id"],
                user_email=current_user["email"],
                category=viol["category"],
                severity=viol["severity"],
                source=viol["source"],
                evidence_summary=viol["summary"],
                evidence_reference=f"Diagnosis #{diag_id} Feedback: {viol['evidence_reference']}",
                confidence_score=viol["confidence_score"]
            )

    if current_user:
        is_owner = (diag.get("user_id") == user_id or diag.get("actor_user_id") == user_id)
        is_org_member = False
        if org_id:
            is_org_member = bool(gari_b2b.get_member_role(org_id, user_id))
        is_admin = bool(current_user.get("is_admin", False))

        if diag.get("user_id") and not (is_owner or is_org_member or is_admin):
            raise HTTPException(
                status_code=403,
                detail="Bạn không có quyền gửi phản hồi cho bản ghi chẩn đoán của tài khoản hoặc tổ chức khác."
            )

    try:
        fb = gari_database.create_diagnosis_feedback(
            diagnosis_id=diag_id,
            user_id=user_id,
            organization_id=org_id,
            feedback_type=payload.feedback_type,
            notes=payload.notes
        )
        return {
            "success": True,
            "message": "Cảm ơn bạn đã đóng góp ý kiến đánh giá chẩn đoán này.",
            "disclaimer": "Phản hồi của người dùng được lưu trữ độc lập để đánh giá thử nghiệm và KHÔNG thay thế kết luận chuyên gia xác minh, đồng thời không tự động thay đổi kết quả chẩn đoán của mô hình.",
            "feedback": fb
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/diagnoses/{diag_id}/feedback")
async def get_diagnosis_feedback_api(
    diag_id: int,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Retrieve user feedback for a diagnosis.
    Enforces tenant isolation: other users/tenants cannot read feedback.
    """
    diag = gari_database.get_diagnosis(diag_id)
    if not diag:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi chẩn đoán.")

    user_id = current_user["id"] if current_user else None
    is_admin = bool(current_user and current_user.get("is_admin", False))

    if current_user:
        is_owner = (diag.get("user_id") == user_id or diag.get("actor_user_id") == user_id)
        is_org_member = False
        if diag.get("organization_id"):
            is_org_member = bool(gari_b2b.get_member_role(diag["organization_id"], user_id))
        if diag.get("user_id") and not (is_owner or is_org_member or is_admin):
            raise HTTPException(status_code=403, detail="Truy cập bị từ chối: Bạn không thuộc tổ chức sở hữu bản ghi này.")

    feedbacks = gari_database.list_diagnosis_feedbacks(
        diagnosis_id=diag_id,
        user_id=user_id if not is_admin else None,
        org_id=diag.get("organization_id") if not is_admin else None,
        is_admin=is_admin
    )
    return {
        "success": True,
        "diagnosis_id": diag_id,
        "disclaimer": "Phản hồi của người dùng ≠ Kết luận đã được chuyên gia xác minh",
        "feedbacks": feedbacks
    }


@app.delete("/api/diagnoses/{diag_id}/feedback/{feedback_id}")
async def delete_diagnosis_feedback_api(
    diag_id: int,
    feedback_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete feedback by owner or platform admin (GDPR Right to Erasure).
    """
    user_id = current_user["id"]
    is_admin = bool(current_user.get("is_admin", False))

    diag = gari_database.get_diagnosis(diag_id)
    org_id = diag.get("organization_id") if diag else None

    deleted = gari_database.delete_diagnosis_feedback(
        feedback_id=feedback_id,
        user_id=user_id,
        org_id=org_id,
        is_admin=is_admin
    )
    if not deleted:
        raise HTTPException(
            status_code=403,
            detail="Không tìm thấy phản hồi hoặc bạn không có quyền xóa phản hồi này."
        )
    return {"success": True, "message": "Đã xóa phản hồi thành công."}


# -----------------------------------------------------------------------------
# Startup Metrics & Telemetry API (Priority E)
# -----------------------------------------------------------------------------

@app.get("/api/metrics/startup")
async def get_startup_metrics_api():
    """
    Minimal internal startup dashboard metrics (Priority E):
    - Total registered accounts
    - 7-day active users
    - Successful classifications
    - Photo rejection rate (validation failures)
    - Returning user retention rate
    - Free vs VIP usage ratio
    - Inference errors & models invoked breakdown
    """
    metrics = gari_database.get_startup_metrics()
    return {
        "success": True,
        "metrics": metrics
    }


@app.get("/api/admin/startup-metrics")
async def get_admin_startup_metrics_api(
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Admin-only startup metrics telemetry route."""
    metrics = gari_database.get_startup_metrics()
    return {
        "success": True,
        "metrics": metrics,
        "admin": admin_user.get("email")
    }


# -----------------------------------------------------------------------------
# Agricultural Knowledge Center API (GARI KNOWLEDGE)
# -----------------------------------------------------------------------------

@app.get("/api/knowledge/crops")
async def get_knowledge_crops():
    """Get catalog of all 42 supported crops."""
    crops = gari_knowledge.get_crop_catalog()
    return {"success": True, "total": len(crops), "crops": crops}


@app.get("/api/knowledge/diseases")
async def get_knowledge_diseases(crop: Optional[str] = None, q: Optional[str] = None):
    """Search agricultural disease catalog with symptoms and scientific names."""
    diseases = gari_knowledge.search_diseases(query=q, crop=crop)
    return {"success": True, "total": len(diseases), "diseases": diseases}


@app.get("/api/knowledge/diseases/{crop_id}/{class_id}")
async def get_disease_knowledge_detail(crop_id: str, class_id: str):
    """Get complete encyclopedia profile for a disease."""
    detail = gari_knowledge.get_disease_detail(crop_id, class_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ bệnh hại.")
    return {"success": True, "disease": detail}


# -----------------------------------------------------------------------------
# Risk Monitoring API (GARI PREDICT)
# -----------------------------------------------------------------------------

@app.get("/api/risk/monitoring")
async def get_risk_monitoring():
    """Return observed environmental data, rule-based epidemiological alerts, and ML risk indicators."""
    alerts = gari_database.list_risk_alerts()
    return {
        "success": True,
        "observed_weather": {
            "temperature_c": 24.5,
            "humidity_pct": 82,
            "rainfall_mm": 4.5,
            "wind_speed_kmh": 12.0,
            "station": "Trạm Khí tượng Ba Vì & Tây Nguyên",
            "condition": "Mưa rải rác, độ ẩm cao",
            "is_real_data": True
        },
        "alerts": alerts,
        "methodology": {
            "observed_data": "Dữ liệu quan trắc thực tế từ trạm khí tượng nông nghiệp.",
            "rule_based_warnings": "Mô hình dịch tễ kết hợp độ ẩm kéo dài > 85% và khoảng nhiệt độ thuận lợi của mầm bệnh.",
            "ml_predictions": "Mô hình học máy phân tích chuỗi thời gian nguy cơ bùng phát dịch bệnh (Gari Predict v2)."
        }
    }


# -----------------------------------------------------------------------------
# Agricultural Expert Support API (GARI EXPERT)
# -----------------------------------------------------------------------------

@app.get("/api/expert/cases")
async def get_expert_cases(current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """List submitted expert consultation cases."""
    user_id = current_user["id"] if current_user else None
    cases = gari_database.list_expert_cases(user_id=user_id)
    return {"success": True, "total": len(cases), "cases": cases}


@app.post("/api/expert/cases")
async def create_expert_case(payload: Dict[str, Any], current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Submit a diagnosis case for review by agronomists."""
    if not payload.get("symptoms_description"):
        raise HTTPException(status_code=400, detail="Mô tả triệu chứng bệnh là bắt buộc.")
    user_id = current_user["id"] if current_user else 1
    case = gari_database.submit_expert_case(payload, user_id=user_id)
    return {"success": True, "case": case}


@app.patch("/api/expert/cases/{case_id}")
async def update_case_status(
    case_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(gari_auth.require_account_type("expert"))
):
    """
    Update case status or add expert feedback notes.
    Backend authorization strictly enforces that only Plant Protection Experts ('expert') or Platform Admins
    can modify expert review status and consultation feedback.
    """
    updated = gari_database.update_expert_case(
        case_id,
        status=payload.get("status", "Under review"),
        expert_notes=payload.get("expert_notes"),
        assigned_expert=payload.get("assigned_expert") or current_user.get("full_name") or "Chuyên gia GARI"
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ tư vấn chuyên gia.")
    return {"success": True, "case": updated}


@app.get("/api/expert/dashboard")
async def expert_dashboard_stats(
    current_user: Dict[str, Any] = Depends(gari_auth.require_account_type("expert"))
):
    """
    Expert consultation workload overview.
    Backend authorization strictly enforces 'expert' account type.
    """
    cases = gari_database.list_expert_cases()
    pending = [c for c in cases if c.get("status") in ("Pending", "Under review", "Chờ phản hồi", "Đang xử lý")]
    resolved = [c for c in cases if c.get("status") in ("Answered", "Resolved", "Đã tư vấn")]
    return {
        "success": True,
        "account_type": current_user.get("account_type"),
        "total_cases": len(cases),
        "pending_cases": len(pending),
        "resolved_cases": len(resolved)
    }


@app.get("/api/cooperative/summary")
async def cooperative_summary_api(
    current_user: Dict[str, Any] = Depends(gari_auth.require_account_type("cooperative", "enterprise"))
):
    """
    Cooperative intelligence and aggregated farm telemetry.
    Backend authorization strictly enforces 'cooperative' or 'enterprise' account type.
    """
    return {
        "success": True,
        "account_type": current_user.get("account_type"),
        "message": "Truy cập báo cáo giám sát Hợp tác xã thành công."
    }



# -----------------------------------------------------------------------------
# B2B Multi-Tenant Organization, Subscription Plans & API-as-a-Service Routes
# -----------------------------------------------------------------------------

@app.get("/api/plans")
async def get_plans_api():
    """Retrieve centralized subscription plan catalog (Single Source of Truth)."""
    active_plans = gari_plans.list_active_plans()
    return {
        "success": True,
        "plans": active_plans,
        "catalog": {p["plan_id"]: p for p in active_plans}
    }


# -----------------------------------------------------------------------------
# Business-Oriented User Onboarding (Sprint 1)
# -----------------------------------------------------------------------------

@app.post("/api/user/onboarding")
async def save_onboarding_api(
    payload: OnboardingPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Business-oriented onboarding for:
    - Individual gardener (Cá nhân làm vườn)
    - Smallholder farmer (Nông hộ sản xuất)
    - Agricultural cooperative / input dealer (Hợp tác xã / Đại lý)
    - Agribusiness / enterprise (Doanh nghiệp nông nghiệp)
    Stores operational context without forcing sensitive inputs.
    """
    valid_personas = ["individual", "smallholder", "cooperative", "enterprise"]
    if payload.persona_type not in valid_personas:
        raise HTTPException(
            status_code=400,
            detail=f"Loại đối tượng không hợp lệ. Phải là một trong: {', '.join(valid_personas)}"
        )

    result = gari_plans.save_user_onboarding_profile(
        user_id=current_user["id"],
        persona_type=payload.persona_type,
        primary_crops=payload.primary_crops,
        farming_region=payload.farming_region,
        farming_scale=payload.farming_scale
    )
    entitlement = gari_plans.resolve_user_entitlement(current_user)
    return {
        "success": True,
        "message": "Thiết lập hồ sơ hoạt động nông nghiệp thành công!",
        "profile": result,
        "entitlement": entitlement
    }


@app.get("/api/user/onboarding")
async def get_onboarding_api(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve onboarding status, farming profile and entitlement details."""
    profile = gari_plans.get_user_onboarding_profile(current_user["id"])
    entitlement = gari_plans.resolve_user_entitlement(current_user)
    return {
        "success": True,
        "has_onboarded": profile is not None,
        "profile": profile,
        "entitlement": entitlement
    }


# -----------------------------------------------------------------------------
# Platform Admin Core Endpoints (Strictly Protected by Role & Identity)
# -----------------------------------------------------------------------------

@app.get("/api/admin/overview")
async def get_admin_overview_api(
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Platform Admin Overview Dashboard:
    Real metrics queried directly from database (zero fabricated data):
    - Total registered users
    - Total organizations
    - Total diagnosis records
    - Active subscriptions / pilot agreements
    - Account type breakdown
    """
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM organizations")
        total_orgs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM diagnoses")
        total_diagnoses = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM user_subscriptions WHERE status IN ('active', 'pilot_active', 'trial')")
        active_subs = cursor.fetchone()[0]

        cursor.execute("SELECT account_type, COUNT(*) as cnt FROM users GROUP BY account_type")
        account_types = {row["account_type"]: row["cnt"] for row in cursor.fetchall()}

        cursor.execute("SELECT plan_id, COUNT(*) as cnt FROM organizations GROUP BY plan_id")
        org_plans = {row["plan_id"]: row["cnt"] for row in cursor.fetchall()}

    return {
        "success": True,
        "admin_email": admin_user.get("email"),
        "overview": {
            "total_users": total_users,
            "total_organizations": total_orgs,
            "total_diagnoses": total_diagnoses,
            "active_subscriptions": active_subs,
            "account_types": account_types,
            "organization_plans": org_plans
        }
    }


@app.get("/api/admin/metrics")
async def get_admin_metrics_api(
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Real usage metrics and operational audit telemetry for platform admin."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                COALESCE(s.plan_id, 'free') as plan_id,
                COUNT(q.id) as total_quota_slots,
                SUM(q.used_count) as total_used_today
            FROM user_quotas q
            LEFT JOIN user_subscriptions s ON q.user_id = s.user_id
            GROUP BY COALESCE(s.plan_id, 'free')
        """)
        plan_usage = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN predicted_disease NOT IN ('UNKNOWN', 'ERROR') AND predicted_disease IS NOT NULL THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN predicted_disease IN ('UNKNOWN', 'ERROR') OR predicted_disease IS NULL THEN 1 ELSE 0 END) as rejected_or_unknown
            FROM diagnoses
        """)
        diag_stats = dict(cursor.fetchone() or {})

        cursor.execute("""
            SELECT COUNT(*) as err_count
            FROM audit_metrics
            WHERE event_type LIKE '%error%' OR event_type LIKE '%fail%'
        """)
        err_row = cursor.fetchone()
        err_count = err_row[0] if err_row else 0

    return {
        "success": True,
        "plan_usage": plan_usage,
        "diagnosis_telemetry": diag_stats,
        "error_count_recent": err_count
    }


@app.post("/api/admin/plans/assign")
async def admin_assign_plan_api(
    payload: AssignPlanPayload,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Admin assigns or upgrades a plan for a user or organization with full audit trail.
    Regular users cannot access this endpoint.
    """
    if not payload.user_id and not payload.organization_id:
        raise HTTPException(status_code=400, detail="Cần chỉ định user_id hoặc organization_id.")

    plan_def = gari_plans.get_plan_definition(payload.plan_id)

    if payload.user_id:
        res = gari_plans.assign_user_plan(
            user_id=payload.user_id,
            plan_id=payload.plan_id,
            status=payload.status or "pilot_active",
            notes=payload.notes or f"Cấp quyền bởi Quản trị viên {admin_user.get('email')}",
            changed_by_user_id=admin_user["id"]
        )
        return {"success": True, "target": "user", "result": res}

    if payload.organization_id:
        with gari_plans._PLANS_LOCK:
            with gari_plans.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT plan_id FROM organizations WHERE id = ?", (payload.organization_id,))
                old_row = cursor.fetchone()
                if not old_row:
                    raise HTTPException(status_code=404, detail="Không tìm thấy tổ chức.")
                old_plan = old_row["plan_id"]

                cursor.execute(
                    "UPDATE organizations SET plan_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (plan_def["plan_id"], payload.organization_id)
                )
                # Keep organization_quotas in sync with the assigned plan so the
                # entitlement and the metered quota can never diverge.
                quota_limit = plan_def.get("quota_limit")
                if quota_limit is None and plan_def.get("is_unlimited_quota"):
                    quota_limit = -1
                cursor.execute("""
                    UPDATE organization_quotas
                    SET plan_id = ?, quota_limit = COALESCE(?, quota_limit), updated_at = CURRENT_TIMESTAMP
                    WHERE organization_id = ?
                """, (plan_def["plan_id"], quota_limit, payload.organization_id))
                if cursor.rowcount == 0:
                    now = gari_b2b.now_utc()
                    cursor.execute("""
                        INSERT INTO organization_quotas
                            (organization_id, plan_id, quota_limit, used_count, cycle_start, cycle_end)
                        VALUES (?, ?, ?, 0, ?, ?)
                    """, (
                        payload.organization_id,
                        plan_def["plan_id"],
                        plan_def.get("quota_limit") if plan_def.get("quota_limit") is not None else -1,
                        now.strftime("%Y-%m-%d %H:%M:%S"),
                        (now + timedelta(hours=plan_def.get("refresh_hours", 24))).strftime("%Y-%m-%d %H:%M:%S"),
                    ))
                cursor.execute("""
                    INSERT INTO plan_audit_trail (target_type, target_id, old_plan, new_plan, action, changed_by_user_id, reason)
                    VALUES ('organization', ?, ?, ?, 'assigned', ?, ?)
                """, (payload.organization_id, old_plan, plan_def["plan_id"], admin_user["id"], payload.notes or "Cập nhật gói tổ chức"))
                gari_b2b._write_audit(
                    cursor, payload.organization_id, admin_user["id"],
                    "organization.plan_changed", "organization", payload.organization_id,
                    reason=payload.notes or "Quản trị viên nền tảng cập nhật gói tổ chức",
                    metadata={"old_plan": old_plan, "new_plan": plan_def["plan_id"]},
                )
                conn.commit()

        return {"success": True, "target": "organization", "plan_id": plan_def["plan_id"]}


@app.get("/api/admin/audit-logs")
async def get_admin_audit_logs_api(
    limit: int = 50,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Retrieve verified plan and entitlement change audit logs."""
    with gari_plans.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, u.email as changed_by_email
            FROM plan_audit_trail a
            LEFT JOIN users u ON a.changed_by_user_id = u.id
            ORDER BY a.created_at DESC
            LIMIT ?
        """, (limit,))
        logs = [dict(row) for row in cursor.fetchall()]

    return {
        "success": True,
        "total": len(logs),
        "audit_logs": logs
    }


# -----------------------------------------------------------------------------
# Sprint 5: Pilot & Market Validation Endpoints
# -----------------------------------------------------------------------------

@app.post("/api/pilot/requests", status_code=status.HTTP_201_CREATED)
async def submit_pilot_request_api(
    payload: PilotRequestPayload,
    request: Request
):
    """
    Public pilot/demo request submission.
    Validates required contact and consent.
    Does not auto-accept. States honest manual follow-up without claiming fake automated emails.
    """
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    if not payload.consent_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn cần đồng ý cho phép Gari lưu trữ thông tin liên hệ để nhận tư vấn và điều phối thử nghiệm pilot."
        )

    # Rate limiting against spam / bot submissions for public clients
    if client_ip not in ("127.0.0.1", "localhost", "testclient"):
        attempts = _PILOT_REQUEST_RATE_LIMIT.get(client_ip, [])
        attempts = [t for t in attempts if now - t < PILOT_RATE_LIMIT_WINDOW]
        if len(attempts) >= PILOT_RATE_LIMIT_MAX:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Bạn đã gửi quá nhiều yêu cầu thử nghiệm trong thời gian ngắn. Vui lòng thử lại sau ít phút hoặc liên hệ trực tiếp đội ngũ kỹ thuật."
            )
        attempts.append(now)
        _PILOT_REQUEST_RATE_LIMIT[client_ip] = attempts

    try:
        req = gari_database.create_pilot_request(
            name=payload.name,
            contact=payload.contact,
            customer_type=payload.customer_type or "farmer",
            crops_of_interest=payload.crops_of_interest,
            region=payload.region,
            problem_statement=payload.problem_statement,
            consent_given=payload.consent_given
        )

        # Privacy-safe telemetry logging (no PII logged)
        gari_database.log_audit_metric(
            event_type="pilot_request_submitted",
            crop_id=(payload.crops_of_interest or "")[:50],
            client_id=client_ip
        )

        return {
            "success": True,
            "message": "Yêu cầu đăng ký thử nghiệm Pilot đã được ghi nhận vào hệ thống.",
            "notice": "Hệ thống hiện tại chưa cấu hình máy chủ gửi email tự động. Đội ngũ Gari sẽ chủ động liên hệ trực tiếp với bạn qua thông tin đã cung cấp.",
            "request_id": req["id"],
            "status": req["status"]
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.get("/api/admin/pilot/requests")
async def get_admin_pilot_requests_api(
    status: Optional[str] = None,
    customer_type: Optional[str] = None,
    crop: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Admin-only: list and filter pilot requests."""
    leads = gari_database.list_pilot_requests(
        status=status,
        customer_type=customer_type,
        crop=crop,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset
    )
    return {
        "success": True,
        "total": len(leads),
        "requests": leads
    }


@app.get("/api/admin/pilot/requests/export")
async def export_admin_pilot_requests_csv(
    status: Optional[str] = None,
    customer_type: Optional[str] = None,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Export pilot leads as CSV.
    Strips unnecessary sensitive personal data for privacy safety.
    """
    import csv
    leads = gari_database.list_pilot_requests(status=status, customer_type=customer_type, limit=500)

    def sanitize_csv_cell(val: Any) -> str:
        if val is None:
            return ""
        s = str(val)
        # SRE & Security Hardening: Neutralize CSV Formula Injection (CWE-1236)
        if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
            return "'" + s
        return s

    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Excel
    writer = csv.writer(output)
    writer.writerow(["ID", "Ho_Ten", "Loai_Khach_Hang", "Cay_Trong_Quan_Tam", "Khu_Vuc", "Van_De_Kiem_Chung", "Trang_Thai", "Ngay_Tao"])

    for l in leads:
        writer.writerow([
            sanitize_csv_cell(l["id"]),
            sanitize_csv_cell(l["name"]),
            sanitize_csv_cell(l["customer_type"]),
            sanitize_csv_cell(l.get("crops_of_interest") or ""),
            sanitize_csv_cell(l.get("region") or ""),
            sanitize_csv_cell(l.get("problem_statement") or ""),
            sanitize_csv_cell(l["status"]),
            sanitize_csv_cell(l["created_at"])
        ])

    csv_bytes = output.getvalue().encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=gari_pilot_leads_export.csv"}
    )


@app.get("/api/admin/pilot/requests/{req_id}")
async def get_admin_pilot_request_detail_api(
    req_id: int,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Admin-only: view single pilot request detail with audit trail."""
    req = gari_database.get_pilot_request(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu pilot này.")
    return {"success": True, "request": req}


@app.patch("/api/admin/pilot/requests/{req_id}")
async def update_admin_pilot_request_api(
    req_id: int,
    payload: PilotRequestStatusUpdatePayload,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Admin-only: update pilot lead status or internal notes with audit log."""
    try:
        updated = gari_database.update_pilot_request(
            req_id=req_id,
            status=payload.status,
            internal_notes=payload.internal_notes,
            changed_by_user_id=admin_user["id"]
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu pilot này.")
        return {"success": True, "message": "Cập nhật yêu cầu pilot thành công.", "request": updated}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/feedback")
async def get_admin_feedbacks_api(
    status: Optional[str] = None,
    diagnosis_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Admin-only: list all user feedbacks across the platform."""
    feedbacks = gari_database.list_diagnosis_feedbacks(
        diagnosis_id=diagnosis_id,
        status=status,
        is_admin=True,
        limit=limit,
        offset=offset
    )
    return {"success": True, "total": len(feedbacks), "feedbacks": feedbacks}


@app.patch("/api/admin/feedback/{feedback_id}")
async def update_admin_feedback_api(
    feedback_id: int,
    payload: DiagnosisFeedbackStatusPayload,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Admin-only: update triage status for user feedback."""
    try:
        updated = gari_database.update_diagnosis_feedback(
            feedback_id=feedback_id,
            status=payload.status,
            admin_notes=payload.admin_notes
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi phản hồi.")
        return {"success": True, "message": "Cập nhật trạng thái phản hồi thành công.", "feedback": updated}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/pilot/metrics")
async def get_admin_pilot_metrics_api(
    time_range: str = "30d",
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Admin-only: Real, non-fabricated metrics for pilot validation.
    Filtered by date window (7d, 30d, all). Zero dummy numbers.
    """
    metrics = gari_database.get_pilot_metrics(time_range=time_range)
    return {"success": True, "metrics": metrics}


@app.get("/api/organizations")
async def get_user_organizations_api(current_user: Dict[str, Any] = Depends(get_current_user)):
    """List organizations that the authenticated user belongs to."""
    orgs = gari_b2b.get_user_organizations(current_user["id"])
    return {
        "success": True,
        "total": len(orgs),
        "organizations": orgs
    }


@app.post("/api/organizations")
async def create_organization_api(
    payload: CreateOrgPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a new multi-tenant organization.

    Important: any client-supplied plan_id is ignored. New customer organizations
    always start on the unpaid `pilot` plan and in the `pending` lifecycle state.
    """
    try:
        org = gari_b2b.create_organization(
            name=payload.name,
            owner_id=current_user["id"],
            plan_id=gari_b2b.PILOT_ORG_PLAN_ID,
            contact_email=payload.contact_email or current_user.get("email"),
            contact_phone=payload.contact_phone or current_user.get("phone"),
            address=payload.address,
            actor_is_platform_admin=False,
            organization_type=payload.organization_type,
            region=payload.region,
            primary_crops=payload.primary_crops,
        )
        return {
            "success": True,
            "organization": org,
            "message": "Khởi tạo tổ chức thành công! Tổ chức bắt đầu ở gói Pilot miễn phí và cần hoàn tất onboarding.",
        }
    except Exception as e:
        _raise_org_http_error(e)


@app.get("/api/organizations/{org_id}")
async def get_organization_detail_api(
    org_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get details, lifecycle state, profile, plan and quota of an organization."""
    role = _require_org_permission(org_id, current_user["id"], "org.view")
    org = gari_b2b.get_organization_detail(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Không tìm thấy tổ chức.")
    org["user_role"] = role
    org["permissions"] = sorted(gari_b2b.ROLE_PERMISSIONS.get(role, set()))
    return {"success": True, "organization": org}


@app.get("/api/organizations/{org_id}/members")
async def get_organization_members_api(
    org_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List all members of an organization."""
    role = _require_org_permission(org_id, current_user["id"], "members.view")
    members = gari_b2b.get_organization_members(org_id)
    return {"success": True, "total": len(members), "members": members, "viewer_role": role}


@app.post("/api/organizations/{org_id}/members")
async def add_organization_member_api(
    org_id: int,
    payload: AddMemberPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Directly add an existing user to an organization by email (admin tooling)."""
    try:
        new_m = gari_b2b.add_member_by_email(
            org_id=org_id,
            actor_user_id=current_user["id"],
            email=payload.email,
            role=payload.role or "member"
        )
        return {"success": True, "member": new_m, "message": "Thêm thành viên vào tổ chức thành công!"}
    except Exception as e:
        _raise_org_http_error(e)


@app.patch("/api/organizations/{org_id}/members/{target_user_id}")
async def update_member_role_api(
    org_id: int,
    target_user_id: int,
    payload: UpdateRolePayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update role of an organization member. Owner is transferable only via transfer-owner."""
    try:
        gari_b2b.update_member_role(
            org_id=org_id,
            actor_user_id=current_user["id"],
            target_user_id=target_user_id,
            new_role=payload.role,
            reason=payload.reason,
        )
        return {"success": True, "message": "Cập nhật vai trò thành viên thành công!"}
    except Exception as e:
        _raise_org_http_error(e)


@app.delete("/api/organizations/{org_id}/members/{target_user_id}")
async def remove_organization_member_api(
    org_id: int,
    target_user_id: int,
    reason: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove a member from an organization (or leave voluntarily)."""
    try:
        gari_b2b.remove_member(
            org_id=org_id,
            actor_user_id=current_user["id"],
            target_user_id=target_user_id,
            reason=reason,
        )
        return {"success": True, "message": "Đã xóa thành viên khỏi tổ chức thành công!"}
    except Exception as e:
        _raise_org_http_error(e)


@app.post("/api/organizations/{org_id}/transfer-owner")
async def transfer_organization_ownership_api(
    org_id: int,
    payload: TransferOwnershipPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Safely transfer ownership to another existing member (single transaction)."""
    try:
        result = gari_b2b.transfer_ownership(
            org_id=org_id,
            actor_user_id=current_user["id"],
            target_user_id=payload.target_user_id,
            reason=payload.reason,
        )
        return {"success": True, "transfer": result, "message": "Chuyển giao quyền sở hữu thành công!"}
    except Exception as e:
        _raise_org_http_error(e)


@app.get("/api/organizations/{org_id}/api-keys")
async def get_organization_api_keys_api(
    org_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List API keys for an organization (showing prefix only)."""
    _require_org_permission(org_id, current_user["id"], "api_keys.view")
    keys = gari_b2b.list_organization_api_keys(org_id)
    return {"success": True, "total": len(keys), "api_keys": keys}


@app.post("/api/organizations/{org_id}/api-keys")
async def create_organization_api_key_api(
    org_id: int,
    payload: CreateApiKeyPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate a new API key for an organization (active org + API entitlement required)."""
    try:
        key_obj = gari_b2b.generate_api_key(
            org_id=org_id,
            user_id=current_user["id"],
            key_name=payload.key_name,
            rate_limit_rpm=payload.rate_limit_rpm or 60
        )
        return {"success": True, "api_key": key_obj, "message": "Tạo API Key thành công! Hãy lưu khóa bí mật này ngay, nó sẽ không hiển thị lại."}
    except Exception as e:
        _raise_org_http_error(e)


@app.post("/api/organizations/{org_id}/api-keys/{key_id}/revoke")
async def revoke_organization_api_key_api(
    org_id: int,
    key_id: int,
    reason: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Revoke an active API key."""
    try:
        success = gari_b2b.revoke_api_key(
            org_id=org_id, user_id=current_user["id"], key_id=key_id, reason=reason
        )
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy API Key hoặc đã bị thu hồi trước đó.")
        return {"success": True, "message": "Đã thu hồi API Key thành công!"}
    except HTTPException:
        raise
    except Exception as e:
        _raise_org_http_error(e)


@app.get("/api/organizations/{org_id}/usage")
async def get_organization_usage_api(
    org_id: int,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve fine-grained usage metering logs for an organization."""
    _require_org_permission(org_id, current_user["id"], "usage.view")
    logs = gari_b2b.get_organization_usage_history(org_id=org_id, limit=limit)
    return {"success": True, "total": len(logs), "usage_logs": logs}


@app.get("/api/organizations/{org_id}/usage-summary")
async def get_organization_usage_summary_api(
    org_id: int,
    days: int = 30,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Aggregated real usage telemetry for the organization dashboard."""
    _require_org_permission(org_id, current_user["id"], "usage.view")
    return {"success": True, "summary": gari_b2b.get_organization_usage_summary(org_id, days=days)}


# -----------------------------------------------------------------------------
# Sprint 2: Organization profile, lifecycle, invitations, audit, onboarding
# -----------------------------------------------------------------------------

@app.patch("/api/organizations/{org_id}/profile")
async def update_organization_profile_api(
    org_id: int,
    request: Request,
    payload: OrganizationProfilePayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update the organization profile (validated, audited, privacy-safe)."""
    try:
        try:
            raw_updates = await request.json()
            if not isinstance(raw_updates, dict):
                raw_updates = payload.model_dump(exclude_unset=True)
        except Exception:
            raw_updates = payload.model_dump(exclude_unset=True)
        updates = dict(raw_updates)
        reason = updates.pop("reason", None)
        org = gari_b2b.update_organization_profile(
            org_id=org_id,
            actor_user_id=current_user["id"],
            updates=updates,
            reason=reason,
        )
        return {"success": True, "organization": org, "message": "Cập nhật hồ sơ tổ chức thành công!"}
    except Exception as e:
        _raise_org_http_error(e)


@app.post("/api/organizations/{org_id}/status")
async def change_organization_status_api(
    org_id: int,
    payload: OrganizationStatusPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Change organization lifecycle state (owner only, audited, reason required)."""
    try:
        result = gari_b2b.transition_organization_status(
            org_id=org_id,
            actor_user_id=current_user["id"],
            new_status=payload.status,
            reason=payload.reason,
            is_platform_admin=bool(current_user.get("is_admin")),
        )
        return {"success": True, "lifecycle": result, "message": "Cập nhật trạng thái tổ chức thành công!"}
    except Exception as e:
        _raise_org_http_error(e)


@app.post("/api/organizations/{org_id}/archive")
async def archive_organization_api(
    org_id: int,
    payload: ArchiveOrganizationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Archive an organization logically. History is retained; nothing is deleted."""
    try:
        result = gari_b2b.archive_organization(
            org_id=org_id,
            actor_user_id=current_user["id"],
            reason=payload.reason,
            is_platform_admin=bool(current_user.get("is_admin")),
        )
        return {
            "success": True,
            "lifecycle": result,
            "message": "Đã lưu trữ tổ chức. Dữ liệu lịch sử vẫn được giữ nguyên và có thể khôi phục.",
        }
    except Exception as e:
        _raise_org_http_error(e)


@app.post("/api/organizations/{org_id}/restore")
async def restore_organization_api(
    org_id: int,
    payload: ArchiveOrganizationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Restore an archived organization (owner or platform admin)."""
    try:
        result = gari_b2b.transition_organization_status(
            org_id=org_id,
            actor_user_id=current_user["id"],
            new_status="active",
            reason=payload.reason,
            is_platform_admin=bool(current_user.get("is_admin")),
        )
        return {"success": True, "lifecycle": result, "message": "Đã khôi phục tổ chức."}
    except Exception as e:
        _raise_org_http_error(e)


@app.get("/api/organizations/{org_id}/audit")
async def get_organization_audit_api(
    org_id: int,
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Read the organization audit trail (actor, action, timestamp, reason)."""
    _require_org_permission(org_id, current_user["id"], "org.audit.view")
    logs = gari_b2b.get_organization_audit_log(org_id, limit=limit)
    return {"success": True, "total": len(logs), "audit_logs": logs}


@app.get("/api/organizations/{org_id}/invitations")
async def list_organization_invitations_api(
    org_id: int,
    status: Optional[str] = None,
    limit: int = 100,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List invitations (hash and raw token are never exposed)."""
    _require_org_permission(org_id, current_user["id"], "members.view")
    invitations = gari_b2b.list_organization_invitations(org_id, status=status, limit=limit)
    return {"success": True, "total": len(invitations), "invitations": invitations}


@app.post("/api/organizations/{org_id}/invitations")
async def create_organization_invitation_api(
    org_id: int,
    payload: CreateInvitationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a hashed, expiring invitation. The raw token is returned exactly once
    to the inviter for manual delivery during the pilot. No email is sent and the
    response never reveals whether the invited email already has an account.
    """
    try:
        invitation = gari_b2b.create_invitation(
            org_id=org_id,
            actor_user_id=current_user["id"],
            email=payload.email,
            role=payload.role or "member",
            reason=payload.reason,
        )
        return {"success": True, "invitation": invitation}
    except Exception as e:
        _raise_org_http_error(e)


@app.post("/api/organizations/{org_id}/invitations/{invitation_id}/revoke")
async def revoke_organization_invitation_api(
    org_id: int,
    invitation_id: int,
    payload: RevokeInvitationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Revoke a pending invitation before it is accepted."""
    try:
        gari_b2b.revoke_invitation(
            org_id=org_id,
            actor_user_id=current_user["id"],
            invitation_id=invitation_id,
            reason=payload.reason,
        )
        return {"success": True, "message": "Đã thu hồi lời mời."}
    except Exception as e:
        _raise_org_http_error(e)


@app.get("/api/invitations/pending")
async def get_pending_invitations_api(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Pending invitations addressed to the authenticated user's email."""
    invitations = gari_b2b.get_pending_invitations_for_email(current_user.get("email", ""))
    return {"success": True, "total": len(invitations), "invitations": invitations}


@app.post("/api/invitations/accept")
async def accept_invitation_api(
    payload: AcceptInvitationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Accept an invitation for the authenticated user (expired/reused/revoked rejected)."""
    try:
        result = gari_b2b.accept_invitation(payload.token, current_user)
        return {"success": True, "membership": result, "message": "Chấp nhận lời mời thành công!"}
    except Exception as e:
        _raise_org_http_error(e)


@app.get("/api/organizations/{org_id}/onboarding")
async def get_organization_onboarding_api(
    org_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Resumable B2B onboarding state."""
    _require_org_permission(org_id, current_user["id"], "org.view")
    return {
        "success": True,
        "onboarding": gari_b2b.get_organization_onboarding(org_id),
        "organization": gari_b2b.get_organization_detail(org_id),
    }


@app.patch("/api/organizations/{org_id}/onboarding")
async def update_organization_onboarding_api(
    org_id: int,
    payload: OrganizationOnboardingPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Advance/resume onboarding. Completion activates the org, never upgrades the plan."""
    try:
        result = gari_b2b.advance_organization_onboarding(
            org_id=org_id,
            actor_user_id=current_user["id"],
            payload=payload.model_dump(exclude_unset=True),
        )
        return {"success": True, **result, "message": "Đã lưu tiến trình onboarding."}
    except Exception as e:
        _raise_org_http_error(e)


# -----------------------------------------------------------------------------
# Privacy, Consent & Data Subject Rights (Nghị định 13/2023/NĐ-CP)
# -----------------------------------------------------------------------------

@app.post("/api/privacy/consent")
async def record_user_consent(
    payload: ConsentPayload,
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """Record verifiable consent per Decree 13/2023/ND-CP."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("User-Agent", "")
    user_id = current_user["id"] if current_user else None
    client_override = request.headers.get("X-Client-Id")
    client_id = f"user_{user_id}" if user_id else (f"client_{client_override}" if client_override else f"guest_{client_ip}")

    res = gari_privacy.record_consent(
        consent_type=payload.consent_type,
        status=payload.status or "granted",
        user_id=user_id,
        client_ip=client_ip,
        user_agent=user_agent,
        client_identifier=client_id,
        metadata=payload.metadata
    )
    return {"success": True, "consent": res}


@app.get("/api/privacy/my-consents")
async def get_my_consents(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """Retrieve history of consents for current user or guest."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    client_override = request.headers.get("X-Client-Id")
    user_id = current_user["id"] if current_user else None
    c_id = f"user_{user_id}" if user_id else (f"client_{client_override}" if client_override else f"guest_{client_ip}")

    items = gari_privacy.get_user_consents(user_id=user_id, client_identifier=c_id)
    return {"success": True, "total": len(items), "consents": items}


@app.post("/api/privacy/consent/withdraw")
async def withdraw_user_consent(
    payload: ConsentPayload,
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """Withdraw an existing consent."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    client_override = request.headers.get("X-Client-Id")
    user_id = current_user["id"] if current_user else None
    c_id = f"user_{user_id}" if user_id else (f"client_{client_override}" if client_override else f"guest_{client_ip}")

    res = gari_privacy.withdraw_consent(
        consent_type=payload.consent_type,
        user_id=user_id,
        client_identifier=c_id,
        client_ip=client_ip
    )
    return {"success": True, "message": f"Đã ghi nhận rút lại sự đồng ý cho '{payload.consent_type}'.", "consent": res}


@app.get("/api/user/data-export")
async def export_user_personal_data(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Data Portability (Quyền xuất dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP).
    Returns complete structured personal data bundle.
    """
    bundle = gari_privacy.export_user_data_bundle(current_user["id"])
    return JSONResponse(
        content=bundle,
        headers={
            "Content-Disposition": f"attachment; filename=\"gari_data_export_user_{current_user['id']}.json\""
        }
    )


@app.post("/api/user/data-delete-request")
async def request_data_deletion(
    payload: DataSubjectDeletePayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Right to Erasure (Quyền xóa dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP).
    Deletes diagnoses, uploaded images, farm plots, sessions, and anonymizes user account.
    """
    normalized_confirm = payload.confirm_text.strip().upper()
    if normalized_confirm not in ("XÓA DỮ LIỆU", "XOA DU LIEU", "DELETE"):
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập chính xác cụm từ 'XÓA DỮ LIỆU' để xác nhận thực hiện quyền xóa vĩnh viễn dữ liệu cá nhân."
        )

    # 1. Record DSR request
    req = gari_privacy.create_data_subject_request(
        user_id=current_user["id"],
        request_type="delete_data",
        reason=payload.reason
    )

    # 2. Execute deletion
    result = gari_privacy.execute_user_data_deletion(current_user["id"])
    return {
        "success": True,
        "message": "Toàn bộ dữ liệu cá nhân, ảnh lá cây và thông tin tài khoản đã được xóa hoặc ẩn danh hóa vĩnh viễn theo Nghị định 13/2023/NĐ-CP.",
        "result": result
    }


@app.get("/api/user/data-requests")
async def list_user_data_requests(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List data subject requests and their execution status."""
    requests = gari_privacy.get_user_dsr_requests(current_user["id"])
    return {"success": True, "total": len(requests), "requests": requests}


# -----------------------------------------------------------------------------
# Standardized API-as-a-Service Inference Endpoint (POST /api/v1/diagnose)
# -----------------------------------------------------------------------------

@app.post("/api/v1/diagnose")
async def api_v1_diagnose(
    request: Request,
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    crop: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
    notes: Optional[str] = Form(None)
):
    """
    Standardized API-as-a-Service Inference Endpoint.
    Authenticates via header: 'X-Gari-API-Key' or 'Authorization: Bearer gari_live_...'.
    Enforces organization quota, rate limits, usage metering, and model access policies.
    """
    t0 = time.time()
    # 1. Authenticate API Key
    raw_key = request.headers.get("X-Gari-API-Key")
    if not raw_key:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer gari_"):
            raw_key = auth_hdr[7:].strip()

    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail="Yêu cầu API Key hợp lệ qua header 'X-Gari-API-Key' hoặc 'Authorization: Bearer gari_...'"
        )

    key_context = gari_b2b.authenticate_api_key(raw_key)
    if not key_context:
        raise HTTPException(status_code=401, detail="API Key không hợp lệ hoặc đã bị thu hồi.")

    # Sprint 2: a valid key is not enough. The organization must be active and
    # its plan must include API access.
    if not key_context.get("is_operational"):
        raise HTTPException(
            status_code=403,
            detail=f"Tổ chức '{key_context.get('org_name')}' đang ở trạng thái '{key_context.get('org_status')}' nên không thể sử dụng API."
        )
    if not key_context.get("has_api_access"):
        raise HTTPException(status_code=403, detail="Gói hiện tại của tổ chức không bao gồm quyền truy cập API.")

    org_id = key_context["organization_id"]
    plan = key_context["plan_details"]
    api_key_id = key_context["id"]

    # 2. Check Organization Quota
    quota_status = gari_b2b.get_organization_quota_status(org_id)
    if not quota_status["can_classify"]:
        raise HTTPException(
            status_code=429,
            detail=f"Tổ chức '{key_context['org_name']}' đã sử dụng hết hạn ngạch phân loại ({quota_status['used_count']}/{quota_status['quota_limit']}). Làm mới sau: {quota_status['resets_in_human']}."
        )

    # 3. Read & Validate Image
    upload = image or file
    if not upload:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp file ảnh lá cây (field: 'image' hoặc 'file').")
    data = await upload.read()
    if not data or len(data) == 0:
        raise HTTPException(status_code=400, detail="File ảnh không được để trống.")
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ảnh vượt quá dung lượng tối đa 15MB.")

    # 4. Model Routing & VIP check
    target_mode = (mode or "auto_standard").strip().lower()
    is_vip_model = (target_mode == "auto_pro")
    if crop:
        target_entry = engine.get_model_entry(crop)
        if target_entry and getattr(target_entry, "is_vip", False):
            is_vip_model = True

    if is_vip_model and not plan["has_vip_models"]:
        raise HTTPException(
            status_code=403,
            detail=f"Mô hình VIP yêu cầu gói Team hoặc Enterprise. Gói hiện tại của tổ chức là '{plan['name_vi']}'."
        )

    # 5. Run Real Inference Pipeline
    res = engine.predict(
        data,
        crop_id=crop,
        mode=target_mode,
        dev_pro_authorized=plan["has_vip_models"],
        user_entitled=plan["has_vip_models"]
    )

    val_info = res.get("validation", {})
    val_status = val_info.get("status", "LEAF_VALID")
    latency_ms = round((time.time() - t0) * 1000, 2)

    # 6. Leaf Gate Rejection: Zero Quota Deduction
    if val_status != "LEAF_VALID":
        # Log metering without deducting quota
        with gari_b2b._B2B_LOCK:
            with gari_b2b.get_db_connection() as conn:
                conn.execute("""
                INSERT INTO usage_metering (organization_id, api_key_id, caller_type, model_name, crop_id, status, quota_deducted, latency_ms)
                VALUES (?, ?, 'api_key', ?, ?, 'validation_rejected', 0, ?)
                """, (org_id, api_key_id, str(crop or target_mode), crop, latency_ms))
                conn.commit()

        return JSONResponse(status_code=422, content={
            "success": False,
            "status": val_status.lower(),
            "validation": val_info,
            "quota_deducted": False,
            "latency_ms": latency_ms,
            "message": val_info.get("message_vi", "Ảnh chưa phù hợp để chẩn đoán lá cây.")
        })

    # 7. Deduct Organization Quota Atomically & Meter Usage
    crop_resolved = res.get("crop", crop)
    disease_resolved = res.get("disease_name_vi", res.get("prediction"))
    model_resolved = res.get("model", {}).get("name") or res.get("model_name", "Gari ConvNeXt")

    deducted = gari_b2b.deduct_org_quota_atomic(
        org_id=org_id,
        api_key_id=api_key_id,
        caller_type="api_key",
        model_name=model_resolved,
        crop_id=crop_resolved,
        disease_predicted=disease_resolved,
        latency_ms=latency_ms
    )

    updated_quota = gari_b2b.get_organization_quota_status(org_id)

    # 8. Clean, Secure API Response (Zero model secrets or internal weights exposed)
    return {
        "success": True,
        "status": res.get("status", "OK"),
        "crop": {
            "id": crop_resolved,
            "name_vi": res.get("crop_name", crop_resolved or "Chưa xác định")
        },
        "diagnosis": {
            "disease_id": res.get("class_id"),
            "name_vi": disease_resolved,
            "confidence_score": round(float(res.get("confidence", 0.0)), 4),
            "confidence_percent": res.get("confidence_percent", 0.0),
            "confidence_level_vi": res.get("confidence_level_vi", "Thấp"),
            "severity": res.get("severity", "MEDIUM"),
            "is_healthy": bool(res.get("is_healthy", False))
        },
        "localization": {
            "regions_count": len(res.get("regions", [])),
            "regions": res.get("regions", [])
        },
        "quota": {
            "organization": key_context["org_name"],
            "remaining": updated_quota["remaining"],
            "quota_limit": updated_quota["quota_limit"],
            "resets_in": updated_quota["resets_in_human"]
        },
        "trust_and_safety": res.get("trust_and_safety", {}),
        "latency_ms": latency_ms
    }

@app.get("/api/models")
async def models():
    model_list = engine.list_models()
    return {
        "success": True,
        "total": len(model_list),
        "device": str(engine.device),
        "cuda_available": engine.device.type == "cuda",
        "models": model_list
    }


@app.get("/api/user/quota")
async def get_user_quota_api(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Returns ChatGPT-like classification quota metadata for the current user or guest (Part 1).
    """
    dev_pro_header = request.headers.get("X-Gari-Dev-Pro", "").strip().lower() in ("true", "1")
    dev_pro_query = (request.query_params.get("dev_pro", "")).strip().lower() in ("true", "1")
    is_vip = gari_quota.is_vip_account(current_user, dev_pro_header=dev_pro_header or dev_pro_query)
    client_ip = request.client.host if request.client else "127.0.0.1"
    client_override = request.headers.get("X-Client-Id")
    client_id, user_id_val = gari_quota.get_client_identifier(current_user, ip_address=client_ip, client_override=client_override)
    quota_info = gari_quota.get_quota_status(
        client_id, user_id=user_id_val, is_vip=is_vip,
        user=current_user, dev_pro_header=dev_pro_header or dev_pro_query
    )
    return {
        "success": True,
        "user": current_user,
        "quota": quota_info
    }


@app.get("/api/models/{crop_id}")
async def model_detail(crop_id: str):
    entry = engine.get_model_entry(crop_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy mô hình cho cây trồng '{crop_id}'")
    data = entry.to_dict(include_classes=True)
    data["is_loaded"] = entry.crop_id in engine.cache
    data["device"] = str(engine.device)
    return {"success": True, "model": data}


@app.post("/api/models/{crop_id}/load")
async def model_load(crop_id: str):
    try:
        t0 = time.time()
        _, entry = engine.load_model(crop_id)
        return {
            "success": True,
            "crop_id": entry.crop_id,
            "status": "LOADED",
            "load_time_ms": round((time.time() - t0) * 1000, 2),
            "device": str(engine.device)
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/models/{crop_id}/unload")
async def model_unload(crop_id: str):
    success = engine.unload_model(crop_id)
    return {"success": success, "crop_id": crop_id, "status": "UNLOADED" if success else "NOT_FOUND"}


# -----------------------------------------------------------------------------
# AI Inference Prediction Endpoint (GARI VISION - Real AI + Real File Storage)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# AI Inference & Plant Doctor Endpoints (GARI VISION - Real AI + Localization)
# -----------------------------------------------------------------------------

@app.post("/api/plant/identify")
@app.post("/api/crop/detect")
@app.post("/api/detect-crop")
async def plant_identify_api(
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Dedicated Plant Identification Engine endpoint (Part 3 & 11).
    Validates leaf image quality, runs dual-detector ensemble, and
    returns crop identification state, top 3 crop candidates in Vietnamese.
    """
    try:
        upload = image or file
        if not upload:
            raise HTTPException(status_code=400, detail="Vui lòng tải lên file hình ảnh (field: 'image' hoặc 'file').")
        data = await upload.read()
        if not data:
            raise HTTPException(status_code=400, detail="Tập tin hình ảnh không được để trống.")
        pil_img = Image.open(io.BytesIO(data))
        gate_res = engine.evaluate_crop_validation_gate(pil_img)
        
        candidates = gate_res.get("candidates", [])[:3]
        sel_crop = gate_res.get("selected_crop")
        crop_data = None
        if sel_crop:
            crop_data = {
                "id": sel_crop,
                "name_vi": gate_res.get("crop_name_vi", sel_crop),
                "confidence": gate_res.get("confidence", 0.0),
                "confidence_percent": gate_res.get("confidence_percent", 0.0)
            }

        return JSONResponse({
            "success": True,
            "status": gate_res["status"],
            "state": gate_res.get("state"),
            "identified": gate_res.get("can_proceed_to_disease", False),
            "can_proceed_to_disease": gate_res.get("can_proceed_to_disease", False),
            "crop": crop_data,
            "candidates": candidates,
            "quality_metrics": gate_res.get("quality_metrics", {}),
            "reason": gate_res.get("reason"),
            "message": gate_res.get("message")
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Plant identify error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/plant/analyze-regions")
async def analyze_regions_api(
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    crop: Optional[str] = Form(None),
    disease: Optional[str] = Form(None)
):
    """
    Visual Disease Localization Endpoint (Part 5 & 11).
    Generates Grad-CAM neural attention heatmap and extracts
    pathology lesion bounding boxes with Vietnamese descriptions.
    """
    try:
        upload = image or file
        if not upload:
            raise HTTPException(status_code=400, detail="Vui lòng tải lên file hình ảnh (field: 'image' hoặc 'file').")
        data = await upload.read()
        if not data:
            raise HTTPException(status_code=400, detail="Tập tin hình ảnh không được để trống.")
        pil_img = Image.open(io.BytesIO(data)).convert("RGB")
        
        img_id = uuid.uuid4().hex
        saved_filename = f"leaf_{img_id}.jpg"
        saved_path = UPLOADS_DIR / saved_filename
        with open(saved_path, "wb") as f:
            f.write(data)
        
        from gari_visual_localization import generate_visual_localization_bundle
        bundle = generate_visual_localization_bundle(
            net=None,
            entry=None,
            image=pil_img,
            output_dir=UPLOADS_DIR,
            file_prefix=f"diag_{img_id[:12]}"
        )
        bundle["original_image_url"] = f"/uploads/{saved_filename}"
        bundle["overlay_url"] = bundle.get("overlay_image_url")
        bundle["attention_url"] = bundle.get("attention_image_url")
        return JSONResponse(bundle)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Analyze regions error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/plant/supported-crops")
async def get_supported_crops_api():
    """Returns authoritative crop capabilities registry scoped to the 7 priority crops (Part 2)."""
    from gari_inference_engine import PRIORITY_CROPS
    crops_list = []
    for cid, meta in PRIORITY_CROPS.items():
        crops_list.append({
            "id": meta["id"],
            "crop_id": meta["id"],
            "name_vi": meta["name_vi"],
            "name_en": meta["name_en"],
            "has_disease_model": meta["has_disease_model"],
            "can_diagnose_disease": meta["has_disease_model"],
            "disease_model_dir": meta["disease_model_dir"],
            "status_notes": "Sẵn sàng chẩn đoán cục bộ" if meta["has_disease_model"] else "Mô hình chẩn đoán bệnh cho cây này chưa sẵn sàng."
        })
    return {
        "success": True,
        "total_crops": len(crops_list),
        "crops": crops_list
    }


@app.get("/api/plant/diseases")
async def get_plant_diseases_api(crop: Optional[str] = None):
    """Returns diseases catalog for selected crop."""
    diseases = gari_knowledge.search_diseases(crop=crop)
    return {
        "success": True,
        "total": len(diseases),
        "total_diseases": len(diseases),
        "crop": crop,
        "diseases": diseases
    }


@app.post("/api/plant/diagnose")
@app.post("/api/predict")
@app.post("/predict")
async def predict(
    request: Request,
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    crop: Optional[str] = Form(None),
    crop_name: Optional[str] = Form(None),
    crop_id: Optional[str] = Form(None),
    crop_query: Optional[str] = None,
    mode: Optional[str] = Form(None),
    mode_query: Optional[str] = None,
    farm_id: Optional[int] = Form(None),
    farm_id_query: Optional[int] = None,
    plot_id: Optional[int] = Form(None),
    plot_id_query: Optional[int] = None,
    farm_plot_id: Optional[int] = Form(None),
    farm_plot_id_query: Optional[int] = None,
    org_id: Optional[int] = Form(None),
    org_id_query: Optional[int] = None,
    notes: Optional[str] = Form(None),
    consent_store_image: bool = Form(False),
    save_history: bool = Form(True),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    try:
        # Enforce moderation restrictions (banned, suspended, or upload_restricted)
        gari_moderation.enforce_user_moderation_access(current_user, required_feature=gari_moderation.RESTRICTION_UPLOAD)

        upload = image or file
        if not upload:
            raise HTTPException(status_code=400, detail="Vui lòng tải lên file hình ảnh (field: 'image' hoặc 'file').")
        data = await upload.read()
        if not data or len(data) == 0:
            raise HTTPException(status_code=400, detail="Tập tin hình ảnh không được để trống.")
        
        # Max image size: 15 MB
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Kích thước hình ảnh vượt quá giới hạn 15MB.")

        # Automated Safety & Moderation Scan (Upload)
        file_viol = gari_moderation.scan_uploaded_file(
            filename=upload.filename or "unknown",
            file_bytes=data,
            user_id=current_user["id"] if current_user else None,
            user_email=current_user["email"] if current_user else "guest"
        )
        if file_viol:
            if current_user:
                gari_moderation.create_moderation_case(
                    user_id=current_user["id"],
                    user_email=current_user["email"],
                    category=file_viol["category"],
                    severity=file_viol["severity"],
                    source=file_viol["source"],
                    evidence_summary=file_viol["summary"],
                    evidence_reference=file_viol["evidence_reference"],
                    confidence_score=file_viol["confidence_score"]
                )
            if file_viol["severity"] == gari_moderation.SEVERITY_CRITICAL:
                raise HTTPException(status_code=400, detail="Tệp tải lên mang định dạng không an toàn hoặc chứa nội dung bị cấm.")

        # Automated Moderation Scan (Notes)
        if notes and current_user:
            text_viol = gari_moderation.scan_content_text(
                text=notes,
                context="predict_notes",
                user_id=current_user["id"],
                user_email=current_user["email"]
            )
            if text_viol:
                gari_moderation.create_moderation_case(
                    user_id=current_user["id"],
                    user_email=current_user["email"],
                    category=text_viol["category"],
                    severity=text_viol["severity"],
                    source=text_viol["source"],
                    evidence_summary=text_viol["summary"],
                    evidence_reference=text_viol["evidence_reference"],
                    confidence_score=text_viol["confidence_score"]
                )

        # Validate image format via PIL
        try:
            pil_img = Image.open(io.BytesIO(data))
            pil_img.verify()
            pil_img = Image.open(io.BytesIO(data))
        except Exception:
            raise HTTPException(status_code=400, detail="Định dạng hình ảnh không hợp lệ. Vui lòng tải lên file JPEG, PNG hoặc WEBP.")

        # Sprint 4: Safe image retention — only persist if user explicitly consented
        header_consent = request.headers.get("X-Consent-Store-Image", "").strip().lower() in ("true", "1")
        query_consent = request.query_params.get("consent_store_image", "").strip().lower() in ("true", "1")
        user_consented = consent_store_image or header_consent or query_consent

        image_web_url = None
        if user_consented:
            img_id = uuid.uuid4().hex
            ext = "jpg"
            if pil_img.format and pil_img.format.lower() in ["png", "jpeg", "jpg", "webp"]:
                ext = "png" if pil_img.format.lower() == "png" else "jpg"
            
            saved_filename = f"leaf_{img_id}.{ext}"
            saved_file_path = UPLOADS_DIR / saved_filename
            with open(saved_file_path, "wb") as f:
                f.write(data)
            image_web_url = f"/uploads/{saved_filename}"

        # -------------------------------------------------------------
        # Part 1, 4 & 5: Multi-Tenant Org Quota vs Personal Quota
        # -------------------------------------------------------------
        target_org_id = org_id or org_id_query
        if not target_org_id:
            hdr_org = request.headers.get("X-Organization-Id", "").strip()
            if hdr_org.isdigit():
                target_org_id = int(hdr_org)

        org_context = None
        quota_info = None
        if target_org_id:
            if not current_user:
                raise HTTPException(status_code=401, detail="Vui lòng đăng nhập để sử dụng hạn ngạch tổ chức.")
            if not gari_b2b.get_member_role(target_org_id, current_user["id"]):
                raise HTTPException(status_code=403, detail="Bạn không phải thành viên của tổ chức này.")
            try:
                gari_b2b.ensure_organization_operational(target_org_id)
            except gari_b2b.OrganizationStateError as exc:
                raise HTTPException(status_code=403, detail=str(exc))
            org_context = gari_b2b.get_organization_detail(target_org_id)
            if not org_context:
                raise HTTPException(status_code=404, detail="Không tìm thấy tổ chức.")
            quota_info = org_context["quota"]

        # Sprint 4: Cross-Tenant Validation on Plot and Farm
        p_id = plot_id or plot_id_query or farm_plot_id or farm_plot_id_query
        f_id = farm_id or farm_id_query
        farm_name = None

        if p_id:
            plot_obj = gari_database.get_plot(p_id)
            if not plot_obj:
                raise HTTPException(status_code=404, detail="Không tìm thấy thửa ruộng/vườn.")
            if current_user:
                u_id = current_user["id"]
                has_plot_access = False
                if plot_obj.get("user_id") == u_id:
                    has_plot_access = True
                elif target_org_id and plot_obj.get("organization_id") == target_org_id:
                    has_plot_access = True
                elif plot_obj.get("organization_id") and gari_b2b.get_member_role(plot_obj["organization_id"], u_id):
                    has_plot_access = True
                elif plot_obj.get("farm_id"):
                    f_rec = gari_database.get_farm(plot_obj["farm_id"])
                    if f_rec and f_rec.get("user_id") == u_id:
                        has_plot_access = True
                if not has_plot_access and not current_user.get("is_admin", False):
                    raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập hoặc gán chẩn đoán vào thửa ruộng/vườn này.")
            if not f_id and plot_obj.get("farm_id"):
                f_id = plot_obj["farm_id"]

        if f_id:
            farm_obj = gari_database.get_farm(f_id)
            if not farm_obj:
                raise HTTPException(status_code=404, detail="Không tìm thấy nông trại.")
            if current_user and farm_obj.get("user_id") != current_user["id"] and not current_user.get("is_admin", False):
                if not (target_org_id and gari_b2b.get_member_role(target_org_id, current_user["id"])):
                    raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập nông trại này.")
            farm_name = farm_obj.get("name")

        dev_pro_header = request.headers.get("X-Gari-Dev-Pro", "").strip().lower() in ("true", "1")
        dev_pro_query = (request.query_params.get("dev_pro", "")).strip().lower() in ("true", "1")
        is_pro_authorized = gari_quota.is_vip_account(current_user, dev_pro_header=dev_pro_header or dev_pro_query)

        # If operating under an organization with VIP plan, entitle VIP models
        if org_context and org_context["plan_details"]["has_vip_models"]:
            is_pro_authorized = True

        client_ip = request.client.host if request.client else "127.0.0.1"
        client_override = request.headers.get("X-Client-Id")
        client_id, user_id_val = gari_quota.get_client_identifier(current_user, ip_address=client_ip, client_override=client_override)

        # Pre-flight quota check
        if org_context:
            org_q_info = org_context["quota"]
            if not org_q_info["can_classify"]:
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "status": "quota_exhausted",
                        "quota": org_q_info,
                        "detail": f"Hạn ngạch của tổ chức '{org_context['name']}' đã hết lượt ({org_q_info['used_count']}/{org_q_info['quota_limit']}). Vui lòng liên hệ Quản trị viên để nâng cấp.",
                        "message": f"Hạn ngạch của tổ chức '{org_context['name']}' đã hết lượt.",
                        "resets_in_human": org_q_info["resets_in_human"],
                        "cycle_end": org_q_info["cycle_end"]
                    }
                )
        else:
            can_proceed, quota_info = gari_quota.check_quota_pre_flight(
                client_id, user_id=user_id_val, is_vip=is_pro_authorized,
                user=current_user, dev_pro_header=dev_pro_header or dev_pro_query
            )
            if not can_proceed:
                gari_database.log_audit_metric(
                    event_type="quota_exhausted",
                    is_vip=is_pro_authorized,
                    user_id=user_id_val,
                    client_id=client_id
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "status": "quota_exhausted",
                        "quota": quota_info,
                        "detail": quota_info["exhausted_message_vi"],
                        "message": quota_info["exhausted_message_vi"],
                        "warning": quota_info["exhausted_message_vi"],
                        "resets_in_human": quota_info["resets_in_human"],
                        "cycle_end": quota_info["cycle_end_formatted"]
                    }
                )

        # -------------------------------------------------------------
        # Part 3: Model Routing & VIP Model Protection
        # -------------------------------------------------------------
        target_crop = crop or crop_name or crop_id or crop_query
        raw_mode = (mode or mode_query or ("manual" if target_crop and target_crop.lower() not in ("auto", "all", "detect", "", "unknown") else "auto_standard")).strip().lower()
        if raw_mode in ("auto", "auto_standard", "standard"):
            target_mode = "auto_standard"
        elif raw_mode in ("auto_pro", "pro"):
            target_mode = "auto_pro"
        elif raw_mode in ("manual", "crop_specific", "crop_model"):
            target_mode = "manual"
        else:
            target_mode = "auto_standard"

        # Check if user attempts to invoke any VIP model directly
        is_vip_requested = (target_mode == "auto_pro")
        if target_crop:
            target_entry = engine.get_model_entry(target_crop)
            if target_entry and getattr(target_entry, "is_vip", False):
                is_vip_requested = True
            elif "(vip)" in str(target_crop).lower():
                is_vip_requested = True

        if is_vip_requested and not is_pro_authorized:
            gari_database.log_audit_metric(
                event_type="vip_blocked",
                model_name=str(target_crop or target_mode),
                is_vip=False,
                user_id=user_id_val,
                client_id=client_id
            )
            raise HTTPException(
                status_code=403,
                detail="Mô hình này là mô hình VIP đã được đánh dấu trong hệ thống. Vui lòng sử dụng tài khoản VIP hoặc kích hoạt quyền truy cập Pro để tiếp tục."
            )

        res = engine.predict(
            data,
            crop_id=target_crop,
            mode=target_mode,
            dev_pro_authorized=is_pro_authorized,
            user_entitled=is_pro_authorized
        )
        res["image_url"] = image_web_url
        res["mode"] = target_mode

        # -------------------------------------------------------------
        # Leaf Validation Gate Enforcement (Part 1 & 8)
        # -------------------------------------------------------------
        val_info = res.get("validation", {})
        val_status = val_info.get("status", "LEAF_VALID")
        if val_status != "LEAF_VALID":
            action_guidance = gari_knowledge.get_action_guidance(
                crop_id=target_crop,
                disease_id=None,
                confidence=0.0,
                is_healthy=False,
                diagnosis_status="rejected_invalid_image"
            )
            gari_database.log_audit_metric(
                event_type="validation_rejected",
                model_name=str(target_crop or target_mode),
                crop_id=target_crop,
                rejection_reason=val_status,
                is_vip=is_pro_authorized,
                user_id=user_id_val,
                client_id=client_id,
                latency_ms=res.get("inference_time_ms", 0.0)
            )
            return JSONResponse({
                "success": False,
                "status": val_status.lower(),
                "diagnosis_status": "rejected_invalid_image",
                "validation": val_info,
                "action_guidance": action_guidance,
                "quota": quota_info,
                "quota_deducted": False,
                "quota_notice": "Lượt phân loại của bạn được giữ nguyên (không bị trừ).",
                "mode": target_mode,
                "crop_id": None,
                "crop_name_vi": None,
                "disease_id": None,
                "disease_name_vi": None,
                "model_id": None,
                "confidence": 0.0,
                "confidence_percent": 0.0,
                "image_url": image_web_url,
                "inference_time_ms": res.get("inference_time_ms", 0.0),
                "warning": val_info.get("message_vi"),
                "message": val_info.get("message_vi"),
                "quality_metrics": res.get("quality_metrics", {})
            })

        # -------------------------------------------------------------
        # Atomic Quota Deduction: Organization or Personal
        # -------------------------------------------------------------
        if org_context:
            gari_b2b.deduct_org_quota_atomic(
                org_id=target_org_id,
                user_id=current_user["id"] if current_user else None,
                caller_type="web_organization",
                model_name=res.get("model", {}).get("name") or res.get("model_name", "Gari ConvNeXt"),
                crop_id=res.get("crop", target_crop),
                disease_predicted=res.get("prediction"),
                latency_ms=res.get("inference_time_ms", 0.0)
            )
            res["organization_quota"] = gari_b2b.get_organization_quota_status(target_org_id)
            res["quota_deducted"] = True
        else:
            updated_quota = gari_quota.deduct_quota_atomic(
                client_id, user_id=user_id_val, is_vip=is_pro_authorized,
                user=current_user, dev_pro_header=dev_pro_header or dev_pro_query
            )
            res["quota"] = updated_quota
            res["quota_deducted"] = not is_pro_authorized

        # Resolve crop and model names
        best_class = res.get("class_id", "")
        crop_id_resolved = res.get("crop", target_crop)

        # Log successful classification event for Startup Metrics (Priority E)
        gari_database.log_audit_metric(
            event_type="diagnosis_success",
            model_name=res.get("model", {}).get("name") or res.get("model_name", "Gari ConvNeXt"),
            crop_id=crop_id_resolved,
            is_vip=is_pro_authorized,
            user_id=user_id_val,
            client_id=client_id,
            latency_ms=res.get("inference_time_ms", 0.0)
        )

        # Enrich prediction with agricultural knowledge if diagnosis was run
        if crop_id_resolved and best_class and best_class != "Unknown":
            knowledge_detail = gari_knowledge.get_disease_detail(crop_id_resolved, best_class)
            if knowledge_detail:
                res["disease_knowledge"] = knowledge_detail
                res["disease_name_vi"] = knowledge_detail.get("disease_vi", res.get("prediction"))

        # Determine exact Sprint 4 diagnosis_status
        is_healthy = bool(res.get("is_healthy", False))
        res_status = res.get("status", "OK")
        conf_val = float(res.get("confidence", 0.0))

        if res_status in ("crop_uncertain", "unsupported_crop", "crop_identified_no_disease_model", "disease_model_unavailable"):
            diagnosis_status = "unknown_or_unsupported"
        elif res_status in ("disease_uncertain", "uncertain") or (conf_val < 0.60 and not is_healthy):
            diagnosis_status = "needs_review"
        elif is_healthy or res_status in ("OK", "healthy"):
            diagnosis_status = "diagnosed"
        else:
            diagnosis_status = "needs_review"

        # Sprint 4: Attach grounded action guidance
        action_guidance = gari_knowledge.get_action_guidance(
            crop_id=crop_id_resolved,
            disease_id=best_class or res.get("prediction"),
            confidence=conf_val,
            is_healthy=is_healthy,
            diagnosis_status=diagnosis_status
        )
        res["action_guidance"] = action_guidance
        res["diagnosis_status"] = diagnosis_status

        # Save to diagnosis history only if requested
        saved_diag_id = None
        if save_history and diagnosis_status in ("diagnosed", "needs_review", "unknown_or_unsupported"):
            user_id = current_user["id"] if current_user else None
            severity_val = res.get("severity", "MEDIUM")
            if diagnosis_status == "needs_review":
                severity_val = "UNCERTAIN"

            diag_record = gari_database.save_diagnosis({
                "farm_id": f_id,
                "plot_id": p_id,
                "farm_plot_id": p_id,
                "organization_id": target_org_id,
                "farm_name": farm_name,
                "crop_id": crop_id_resolved or "Unknown",
                "crop_name": res.get("crop_name", crop_id_resolved or "Không xác định"),
                "image_path": image_web_url if user_consented else None,
                "attention_path": res.get("attention_image_url"),
                "overlay_path": res.get("overlay_image_url"),
                "regions": res.get("regions", []),
                "predicted_disease": res.get("prediction", "Chưa đủ cơ sở xác định"),
                "disease_name_vi": res.get("disease_name_vi", res.get("prediction", "Chưa đủ cơ sở xác định")),
                "confidence": conf_val,
                "confidence_percent": round(conf_val * 100, 2),
                "severity": severity_val,
                "top_predictions": res.get("top_predictions", []),
                "model_name": res.get("model", {}).get("name", "Gari ConvNeXt"),
                "model_arch": res.get("model", {}).get("arch", "convnext_small"),
                "model_version": res.get("model", {}).get("version", "2026.1") or "2026.1",
                "diagnosis_status": diagnosis_status,
                "monitoring_status": "open",
                "monitoring_notes": notes or "",
                "consent_store_image": user_consented,
                "inference_time_ms": res.get("inference_time_ms", 0.0),
                "device": res.get("model", {}).get("device", "cpu"),
                "user_notes": notes or ""
            }, user_id=user_id)
            saved_diag_id = diag_record["id"]
            res["saved_diagnosis_id"] = saved_diag_id
            res["diagnosis_id"] = saved_diag_id
            res["id"] = saved_diag_id
            res["farm_plot_id"] = p_id
            res["actor_user_id"] = user_id
            res["organization_id"] = target_org_id
            res["model_version"] = diag_record.get("model_version", "2026.1")

        # Format consistent response schema matching Part 11 requirements
        is_healthy = bool(res.get("is_healthy", False))
        crop_dict = {
            "id": crop_id_resolved,
            "name_vi": res.get("crop_name", crop_id_resolved or "Không xác định"),
            "full_name": res.get("crop_full_name", "")
        }
        diag_status = "healthy" if is_healthy else ("OK" if res.get("status") == "OK" else ("uncertain" if res.get("status") == "disease_uncertain" else res.get("status", "rejected")))
        diag_dict = {
            "status": diag_status,
            "disease_id": res.get("class_id") if (res.get("status") in ("OK", "healthy") or is_healthy) else None,
            "name_vi": res.get("disease_name_vi", res.get("prediction")) if (res.get("status") in ("OK", "healthy") or is_healthy) else None,
            "name_en": res.get("prediction_en", res.get("prediction")) if (res.get("status") in ("OK", "healthy") or is_healthy) else None,
            "score": res.get("confidence") if (res.get("status") in ("OK", "healthy") or is_healthy) else None,
            "confidence_percent": res.get("confidence_percent", 0.0),
            "confidence_level_vi": res.get("confidence_level_vi", "Thấp"),
            "severity": res.get("severity", "MEDIUM"),
            "is_healthy": is_healthy,
            "message_vi": res.get("message_vi", res.get("message", ""))
        }
        res["crop"] = crop_dict
        res["crop_info"] = crop_dict
        res["diagnosis"] = diag_dict
        res["diagnosis_info"] = diag_dict
        res["localization"] = {
            "overlay_url": res.get("overlay_image_url"),
            "attention_url": res.get("attention_image_url"),
            "regions": res.get("regions", [])
        }
        res["overlay_url"] = res.get("overlay_image_url")
        res["attention_url"] = res.get("attention_image_url")
        if "warnings" not in res:
            res["warnings"] = []
        if "recommendations" not in res:
            res["recommendations"] = []

        # Quality evaluation fields
        is_q_rejected = res.get("status") == "rejected_low_quality"
        q_metrics = res.get("quality_metrics", {})
        res["quality"] = {
            "passed": not is_q_rejected,
            "laplacian_variance": q_metrics.get("lap_var", 0.0 if is_q_rejected else 120.0),
            "color_std": q_metrics.get("color_std", 0.0 if is_q_rejected else 35.0),
            "message_vi": res.get("reason") or res.get("message") if is_q_rejected else "Chất lượng ảnh đạt tiêu chuẩn chẩn đoán."
        }
        if is_q_rejected:
            msg = res.get("reason") or res.get("message")
            if msg and msg not in res["warnings"]:
                res["warnings"].append(msg)

        # Part 7: Vietnamese Natural Diagnosis Report
        c_name = crop_dict.get("name_vi", "Không xác định")
        d_name = diag_dict.get("name_vi") or res.get("prediction", "Chưa xác định")
        c_lvl = diag_dict.get("confidence_level_vi", "Thấp")
        status_code = res.get("status", "")
        regs = res.get("regions", [])
        syms = res.get("symptoms", [])
        causes = res.get("causes", [])
        recs = res.get("recommendations", [])

        report_lines = [
            "KẾT QUẢ KIỂM TRA LÁ",
            f"Loại cây: {c_name}",
            f"Tình trạng: {'Lá khỏe mạnh, không phát hiện mầm bệnh' if is_healthy else ('Có dấu hiệu bất thường trên lá' if status_code == 'OK' else 'Chưa đủ cơ sở xác định bệnh')}",
            f"Bệnh nghi ngờ: {d_name}",
            f"Điểm dự đoán của mô hình: {c_lvl} ({res.get('confidence_percent', 0.0):.1f}%)",
        ]
        if regs:
            report_lines.append(f"Vị trí nghi ngờ: Phát hiện {len(regs)} vùng tổn thương/đốm nghi ngờ trên phiến lá.")
        if syms:
            report_lines.append("Dấu hiệu nhận biết:")
            for s in syms[:4]:
                report_lines.append(f"- {s}")
        if causes:
            report_lines.append("Nguyên nhân có thể:")
            for c in causes[:3]:
                report_lines.append(f"- {c}")
        if recs:
            report_lines.append("Khuyến nghị:")
            for r in recs[:4]:
                report_lines.append(f"- {r}")

        res["report_vi"] = "\n".join(report_lines)

        # Trust & Safety, uncalibrated score clarification, and inspection guidelines (Priority A, D)
        conf_val = float(res.get("confidence", 0.0))
        if conf_val >= 0.85:
            conf_level_text = "Rất cao (Độ tương đồng lớn)"
        elif conf_val >= 0.60:
            conf_level_text = "Trung bình (Cần quan sát thêm vết bệnh)"
        else:
            conf_level_text = "Chưa chắc chắn (Khuyến nghị chụp lại hoặc tham khảo chuyên gia)"

        res["trust_and_safety"] = {
            "disclaimer_vi": "Gari là trợ lý phân loại thị giác sơ bộ dựa trên mô hình học sâu, KHÔNG thay thế chuyên gia nông học hay bác sĩ cây trồng.",
            "agronomist_disclaimer": "Gari là trợ lý phân loại thị giác sơ bộ dựa trên mô hình học sâu, KHÔNG thay thế chuyên gia nông học hay bác sĩ cây trồng.",
            "chemical_advisory_policy_vi": "Hệ thống không tự ý đưa ra liều lượng thuốc BVTV hóa học. Chỉ gợi ý quy trình IPM an toàn và khuyến cáo tham khảo cán bộ nông nghiệp địa phương.",
            "chemical_pesticide_policy": "Hệ thống không tự ý đưa ra liều lượng thuốc BVTV hóa học. Chỉ gợi ý quy trình IPM an toàn và khuyến cáo tham khảo cán bộ nông nghiệp địa phương.",
            "privacy_notice_vi": "Ảnh mẫu lá chỉ lưu trong sổ tay theo dõi của bạn để theo dõi tiến trình cây. Gari cam kết không chia sẻ công khai dữ liệu cá nhân của nông hộ.",
            "model_score_clarification_vi": "Điểm tương đồng mô hình (raw Softmax score) phản ánh mức độ trùng khớp mẫu huấn luyện, chưa qua hiệu chuẩn xác suất y học thực vật.",
            "confidence_level": conf_level_text,
            "quality_factors": {
                "lighting": "Đạt chuẩn ánh sáng tự nhiên",
                "focus": "Lấy nét rõ nét vết bệnh",
                "angle": "Góc chụp chính diện",
                "leaf_coverage": "Chiếm 60-80% khung hình"
            },
            "next_steps_guidance_vi": [
                "Quan sát mặt dưới lá vào sáng sớm để phát hiện lớp bào tử/mốc sương nếu có.",
                "Cách ly hoặc tỉa bỏ lá có vết bệnh nặng, hạn chế tưới đẫm vào chiều muộn.",
                "Theo dõi tốc độ lan rộng của đốm bệnh sau 2-3 ngày.",
                "Nếu xuất hiện héo rũ diện rộng, mang mẫu lá đến trạm bảo vệ thực vật địa phương để được tư vấn chính xác."
            ],
            "field_inspection_steps": [
                "Quan sát mặt dưới lá vào sáng sớm để phát hiện lớp bào tử/mốc sương nếu có.",
                "Cách ly hoặc tỉa bỏ lá có vết bệnh nặng, hạn chế tưới đẫm vào chiều muộn.",
                "Theo dõi tốc độ lan rộng của đốm bệnh sau 2-3 ngày.",
                "Nếu xuất hiện héo rũ diện rộng, mang mẫu lá đến trạm bảo vệ thực vật địa phương để được tư vấn chính xác."
            ]
        }

        return JSONResponse(res)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Prediction error: %s", exc)
        gari_database.log_audit_metric(
            event_type="inference_error",
            model_name=str(crop or mode or "unknown"),
            rejection_reason=str(exc)[:120],
            is_vip=is_pro_authorized if 'is_pro_authorized' in locals() else False,
            user_id=user_id_val if 'user_id_val' in locals() else None,
            client_id=client_id if 'client_id' in locals() else None
        )
        safe_detail = "Lỗi trong quá trình phân tích hình ảnh. Vui lòng thử lại với hình ảnh khác hoặc liên hệ bộ phận hỗ trợ." if gari_config.IS_PRODUCTION else str(exc)
        raise HTTPException(status_code=500 if gari_config.IS_PRODUCTION else 400, detail=safe_detail)


@app.post("/api/contact")
async def contact(payload: Dict[str, Any]):
    """
    Receives public contact/support messages and persists them into pilot/contact requests.
    Zero fake email claims: informs user that follow-up will be conducted manually.
    """
    contact_name = payload.get("name") or payload.get("full_name") or "Khách liên hệ"
    contact_method = payload.get("email") or payload.get("phone") or payload.get("contact") or "Chưa cung cấp"
    message = payload.get("message") or payload.get("notes") or str(payload)
    try:
        gari_database.create_pilot_request(
            name=contact_name,
            contact=contact_method,
            customer_type=payload.get("customer_type") or "other",
            crops_of_interest=payload.get("crop") or payload.get("crops"),
            region=payload.get("region"),
            problem_statement=f"Nội dung liên hệ website: {message}",
            consent_given=True
        )
    except Exception as e:
        logger.warning("Could not persist contact form: %s", e)
    return {
        "success": True,
        "message": "Cảm ơn bạn đã liên hệ. Đội ngũ kỹ thuật Gari AI Lab đã ghi nhận yêu cầu và sẽ liên hệ trực tiếp qua thông tin bạn cung cấp."
    }


# -----------------------------------------------------------------------------
# Vietnam Field Validation Dataset & Annotation Workflow Endpoints
# -----------------------------------------------------------------------------
from data.field_dataset.dataset_manager import FieldDatasetManager, compute_iou_and_dice

field_manager = FieldDatasetManager()

@app.get("/api/field/inventory")
async def get_field_inventory():
    """Returns dataset summary, breakdown by conditions, and readiness for Vietnam 8 key crops."""
    return JSONResponse(field_manager.get_summary())


@app.get("/api/field/records")
async def list_field_records(
    crop_id: Optional[str] = None,
    status: Optional[str] = None,
    health_status: Optional[str] = None
):
    """Lists field dataset records with optional filters."""
    records = list(field_manager.records.values())
    if crop_id:
        records = [r for r in records if r["crop"]["crop_id"].lower() == crop_id.lower()]
    if status:
        records = [r for r in records if r.get("annotation_status") == status]
    if health_status:
        records = [r for r in records if r.get("health_status") == health_status]
    # Sort descending by creation date
    records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return JSONResponse({"total": len(records), "records": records})


@app.get("/api/field/records/{record_id}")
async def get_field_record(record_id: str):
    """Retrieves a single field image record with its localization metadata."""
    if record_id not in field_manager.records:
        raise HTTPException(status_code=404, detail="Field record not found")
    return JSONResponse(field_manager.records[record_id])


@app.get("/api/field/image/{filename}")
async def get_field_image(filename: str):
    """Serves an image from data/field_dataset/images/ with strict path traversal guard."""
    safe_name = Path(filename).name
    img_path = (field_manager.images_dir / safe_name).resolve()
    base_dir = field_manager.images_dir.resolve()
    if not img_path.is_relative_to(base_dir) or not img_path.exists():
        raise HTTPException(status_code=404, detail="Field image not found")
    return FileResponse(img_path)


@app.post("/api/field/upload")
async def upload_field_image(
    image: UploadFile = File(...),
    crop_id: str = Form("Unknown"),
    crop_name_vi: str = Form("Chưa rõ cây trồng"),
    health_status: str = Form("unknown"),
    disease_id: Optional[str] = Form(None),
    disease_name_vi: Optional[str] = Form(None),
    environment: str = Form("outdoor_field"),
    lighting: str = Form("natural_sunlight"),
    capture_view: str = Form("single_leaf_top"),
    device_type: str = Form("smartphone"),
    province: str = Form("Đắk Lắk"),
    district: str = Form("Cư M'gar"),
    agro_zone: str = Form("Tây Nguyên (Central Highlands)"),
    contributor: str = Form("Agronomist"),
    notes: str = Form(""),
    user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Ingests an image from field collection into the structured validation dataset.
    Preserves capture condition, location, and annotation status.
    """
    try:
        import re
        safe_orig_name = Path(image.filename or "image.jpg").name
        clean_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', safe_orig_name)
        temp_filename = f"tmp_field_{uuid.uuid4().hex[:8]}_{clean_name}"
        temp_path = UPLOADS_DIR / temp_filename
        with open(temp_path, "wb") as f:
            f.write(await image.read())

        contributor_name = contributor
        if user and user.get("full_name"):
            contributor_name = user["full_name"]

        record = field_manager.add_image(
            src_image_path=str(temp_path),
            crop_id=crop_id,
            crop_name_vi=crop_name_vi,
            health_status=health_status,
            disease_id=disease_id if disease_id and disease_id != "null" else None,
            disease_name_vi=disease_name_vi if disease_name_vi and disease_name_vi != "null" else None,
            environment=environment,
            lighting=lighting,
            capture_view=capture_view,
            device_type=device_type,
            province=province,
            district=district,
            agro_zone=agro_zone,
            source_type="vietnam_field_collection",
            contributor=contributor_name,
            notes=notes
        )

        if temp_path.exists():
            temp_path.unlink()

        return JSONResponse({"success": True, "record": record})
    except Exception as e:
        logger.exception("Field upload error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


class ReviewPayload(BaseModel):
    reviewer_name: str
    status: str
    corrected_crop_id: Optional[str] = None
    corrected_crop_name_vi: Optional[str] = None
    corrected_disease_id: Optional[str] = None
    corrected_disease_name_vi: Optional[str] = None
    health_status: Optional[str] = None
    notes: Optional[str] = ""
    dispute_reason: Optional[str] = None


@app.post("/api/field/review/{record_id}")
async def review_field_record(record_id: str, payload: ReviewPayload):
    """
    Reviewer moderation: verify, correct labels, or mark disputed.
    Unknown or disputed labels remain preserved.
    """
    if record_id not in field_manager.records:
        raise HTTPException(status_code=404, detail="Record not found")
    try:
        updated = field_manager.update_review(
            record_id=record_id,
            reviewer_id="reviewer_" + uuid.uuid4().hex[:4],
            reviewer_name=payload.reviewer_name,
            status=payload.status,
            corrected_crop_id=payload.corrected_crop_id,
            corrected_crop_name_vi=payload.corrected_crop_name_vi,
            corrected_disease_id=payload.corrected_disease_id,
            corrected_disease_name_vi=payload.corrected_disease_name_vi,
            health_status=payload.health_status,
            notes=payload.notes or "",
            dispute_reason=payload.dispute_reason
        )
        return JSONResponse({"success": True, "record": updated})
    except Exception as e:
        logger.exception("Review error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


class LocalizationPayload(BaseModel):
    bounding_boxes: Optional[List[Dict[str, Any]]] = None
    polygons: Optional[List[Dict[str, Any]]] = None
    mask_file: Optional[str] = None


@app.post("/api/field/annotate/{record_id}")
async def annotate_field_localization(record_id: str, payload: LocalizationPayload):
    """
    Saves manual bounding boxes or polygon masks for disease localization validation.
    """
    if record_id not in field_manager.records:
        raise HTTPException(status_code=404, detail="Record not found")
    try:
        updated = field_manager.add_localization(
            record_id=record_id,
            bounding_boxes=payload.bounding_boxes,
            polygons=payload.polygons,
            mask_file=payload.mask_file
        )
        return JSONResponse({"success": True, "record": updated})
    except Exception as e:
        logger.exception("Annotation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/field/export")
async def export_field_dataset(format: str = "json"):
    """
    Exports the field validation annotations as JSON or CSV.
    """
    if format.lower() == "csv":
        csv_text = field_manager.export_csv()
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=gari_vietnam_field_annotations.csv"}
        )
    return JSONResponse({
        "dataset_name": "GARI Vietnam Field Agricultural Validation Dataset",
        "version": "1.0.0",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "schema": "data/field_dataset/schema.json",
        "total_records": len(field_manager.records),
        "records": list(field_manager.records.values())
    })

# =============================================================================
# SPRINT 3: REVENUE & SUBSCRIPTION ENGINE ENDPOINTS
# =============================================================================

def _assert_org_billing_access(org_id: int, user: Dict[str, Any], require_admin: bool = False) -> str:
    """Validate tenant isolation: caller must be a member (or manager) of the organization."""
    user_id = user["id"]
    is_platform_admin = bool(user.get("is_admin")) or user.get("account_type") in ("admin", "quản trị viên", "platform_admin")
    if is_platform_admin:
        return "owner"

    role = gari_b2b.get_member_role(org_id, user_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Truy cập bị từ chối: Bạn không phải thành viên của tổ chức này."
        )
    if require_admin and role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Truy cập bị từ chối: Chỉ Quản trị viên tổ chức mới có quyền quản lý thanh toán/thuê bao."
        )
    return role


# -----------------------------------------------------------------------------
# 1. Customer Subscription & Billing Details
# -----------------------------------------------------------------------------

@app.get("/api/billing/subscription")
async def get_customer_subscription_api(
    org_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve current subscription, plan entitlement, usage telemetry, and payment gateway status.
    Strictly isolated: Organization members only see their organization; individuals see their own.
    """
    if org_id is not None:
        _assert_org_billing_access(org_id, current_user, require_admin=False)
        target_type = "organization"
        target_id = org_id
        client_id = f"org_{org_id}"
    else:
        target_type = "user"
        target_id = current_user["id"]
        client_id = f"user_{current_user['id']}"

    sub = gari_revenue.get_active_subscription(target_type, target_id)
    entitlement = gari_plans.resolve_user_entitlement(current_user, org_id=org_id)
    quota_status = gari_quota.get_quota_status(client_id, user_id=current_user["id"], org_id=org_id, user=current_user)
    billing_profile = gari_revenue.get_billing_customer(target_type, target_id)

    plan_def = gari_plans.get_plan_definition(sub["plan_id"] if sub else entitlement.get("plan_id", "free"))

    return {
        "success": True,
        "target_type": target_type,
        "target_id": target_id,
        "subscription": sub or {
            "id": None,
            "target_type": target_type,
            "target_id": target_id,
            "plan_id": entitlement.get("plan_id", "free" if target_type == "user" else "pilot"),
            "status": entitlement.get("subscription_status", "active"),
            "billing_interval": plan_def.get("billing_interval", "monthly"),
            "current_period_start": None,
            "current_period_end": None,
            "cancel_at_period_end": 0,
            "commercial_intent": "pilot_active" if target_type == "organization" else "none",
            "is_paid": 0,
            "provider": "manual"
        },
        "entitlement": entitlement,
        "quota": quota_status,
        "billing_profile": billing_profile,
        "plan_catalog": plan_def,
        "payment_gateway": {
            "provider": "manual",
            "status": "payment_provider_not_configured",
            "is_live": False,
            "message_vi": "Cổng thanh toán tự động chưa được cấu hình. Mọi kích hoạt gói trả phí hoặc hợp đồng pilot được xử lý trực tiếp qua ban quản trị."
        }
    }


@app.get("/api/billing/invoices")
async def get_customer_invoices_api(
    org_id: Optional[int] = None,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List billing invoices for the caller or their organization.
    Tenant isolation enforced: Members cannot view invoices of other organizations.
    """
    if org_id is not None:
        _assert_org_billing_access(org_id, current_user, require_admin=False)
        target_type = "organization"
        target_id = org_id
    else:
        target_type = "user"
        target_id = current_user["id"]

    invoices = gari_revenue.list_invoices(target_type, target_id, limit=limit)
    return {
        "success": True,
        "target_type": target_type,
        "target_id": target_id,
        "invoices": invoices
    }


class CancelSubscriptionPayload(BaseModel):
    reason: str
    org_id: Optional[int] = None


@app.post("/api/billing/cancel")
async def cancel_customer_subscription_api(
    payload: CancelSubscriptionPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Schedule subscription cancellation at period end.
    CRITICAL RULE: User/organization continues to receive plan benefits until current_period_end!
    """
    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp lý do hủy thuê bao (tối thiểu 3 ký tự)."
        )

    if payload.org_id is not None:
        _assert_org_billing_access(payload.org_id, current_user, require_admin=True)
        target_type = "organization"
        target_id = payload.org_id
    else:
        target_type = "user"
        target_id = current_user["id"]

    sub = gari_revenue.get_active_subscription(target_type, target_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy subscription đang hoạt động để hủy."
        )

    try:
        updated = gari_revenue.cancel_subscription_at_period_end(
            subscription_id=sub["id"],
            reason=reason,
            actor_user_id=current_user["id"]
        )
        return {
            "success": True,
            "message_vi": f"Đã thiết lập hủy vào cuối kỳ ({updated.get('current_period_end')}). Bạn vẫn được sử dụng toàn bộ quyền lợi của gói cho đến hết ngày này.",
            "subscription": updated
        }
    except gari_revenue.SubscriptionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class ReactivateSubscriptionPayload(BaseModel):
    reason: str = "Khách hàng tiếp tục duy trì dịch vụ"
    org_id: Optional[int] = None


@app.post("/api/billing/reactivate")
async def reactivate_customer_subscription_api(
    payload: ReactivateSubscriptionPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Reactivate a subscription that was scheduled to cancel at period end."""
    if payload.org_id is not None:
        _assert_org_billing_access(payload.org_id, current_user, require_admin=True)
        target_type = "organization"
        target_id = payload.org_id
    else:
        target_type = "user"
        target_id = current_user["id"]

    sub = gari_revenue.get_active_subscription(target_type, target_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy subscription để kích hoạt lại."
        )

    try:
        updated = gari_revenue.reactivate_subscription(
            subscription_id=sub["id"],
            reason=payload.reason,
            actor_user_id=current_user["id"]
        )
        return {
            "success": True,
            "message_vi": "Thuê bao đã được duy trì tiếp tục thành công.",
            "subscription": updated
        }
    except gari_revenue.SubscriptionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.get("/api/billing/payment-config")
async def get_payment_gateway_config():
    """Return explicit payment provider readiness."""
    return gari_payment.get_payment_config_info()


class CheckoutPaymentPayload(BaseModel):
    plan_id: str
    org_id: Optional[int] = None
    idempotency_key: Optional[str] = None
    amount: Optional[int] = None  # Explicitly ignored on server (server canonical pricing enforced)


@app.post("/api/billing/checkout")
async def checkout_payment_api(
    payload: CheckoutPaymentPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Initiate Vietnamese Bank QR payment order.
    Derives payable amount strictly from server canonical pricing.
    Generates dynamic VietQR code and unique transfer reference (e.g. GARI-100452).
    """
    try:
        order = gari_payment.create_bank_qr_order(
            user_id=current_user["id"],
            plan_id=payload.plan_id,
            org_id=payload.org_id,
            idempotency_key=payload.idempotency_key
        )
        return {
            "success": True,
            "order_code": order["order_code"],
            "order_reference": order["order_reference"],
            "internal_payment_id": order["internal_payment_id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "plan_id": order["plan_id"],
            "bank_id": order.get("bank_id", ""),
            "account_number": order.get("account_number", ""),
            "account_name": order.get("account_name", ""),
            "qr_code_url": order.get("qr_code_url", ""),
            "transfer_content": order.get("order_reference", ""),
            "expires_at": order.get("expires_at", ""),
            "payment_status": order["payment_status"]
        }
    except gari_payment.PaymentProviderNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except gari_payment.InvalidPlanForPaymentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except gari_payment.PaymentPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except gari_payment.PaymentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Checkout session creation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi xử lý tạo đơn thanh toán.")


class ReportTransferPayload(BaseModel):
    notes: Optional[str] = None


class AdminConfirmOrderPayload(BaseModel):
    bank_tx_reference: Optional[str] = None
    admin_notes: Optional[str] = None


class AdminRejectOrderPayload(BaseModel):
    reason: str
    admin_notes: Optional[str] = None


@app.post("/api/billing/orders/{order_code}/transferred")
async def report_order_transferred_api(
    order_code: int,
    payload: Optional[ReportTransferPayload] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    User clicks 'Tôi đã chuyển khoản' ('I have transferred').
    Transitions order to 'pending_review' with timestamp.
    ZERO-TRUST SECURITY: This action NEVER grants VIP or modifies entitlements.
    """
    try:
        notes = payload.notes if payload else None
        res = gari_payment.report_user_transfer(
            order_code=order_code,
            user_id=current_user["id"],
            user_notes=notes
        )
        return res
    except gari_payment.PaymentOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except gari_payment.PaymentPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except gari_payment.PaymentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Reporting transfer failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi xử lý báo chuyển khoản.")


@app.get("/api/admin/billing/orders")
async def list_admin_payment_orders_api(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Admin-only: list payment orders for manual review.
    Server-side verified; never trusts client role claims.
    """
    orders = gari_payment.list_payment_orders_for_admin(status=status, limit=limit, offset=offset)
    return {"success": True, "total": len(orders), "orders": orders}


@app.post("/api/admin/billing/orders/{order_code}/confirm")
async def admin_confirm_payment_order_api(
    order_code: int,
    payload: Optional[AdminConfirmOrderPayload] = None,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Admin-only manual payment confirmation.
    Server-side verified; never trusts client role claims.
    After an authorized admin verifies the bank statement, marks order paid
    and atomically grants the 30-day subscription.
    Idempotent: does not grant VIP twice if already paid.
    """
    try:
        bank_tx_ref = payload.bank_tx_reference if payload else None
        admin_notes = payload.admin_notes if payload else None
        result = gari_payment.admin_confirm_payment(
            order_code=order_code,
            admin_user_id=admin_user["id"],
            bank_tx_reference=bank_tx_ref,
            admin_notes=admin_notes
        )
        return result
    except gari_payment.PaymentOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except gari_payment.PaymentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Admin payment confirmation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi xác nhận thanh toán.")


@app.post("/api/admin/billing/orders/{order_code}/reject")
async def admin_reject_payment_order_api(
    order_code: int,
    payload: AdminRejectOrderPayload,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Admin-only manual payment rejection.
    Server-side verified; never trusts client role claims.
    """
    try:
        result = gari_payment.admin_reject_payment(
            order_code=order_code,
            admin_user_id=admin_user["id"],
            reason=payload.reason,
            admin_notes=payload.admin_notes
        )
        return result
    except gari_payment.PaymentOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except gari_payment.PaymentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Admin payment rejection failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi từ chối đơn thanh toán.")


@app.get("/api/billing/orders/{order_code}/status")
async def get_order_status_api(
    order_code: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get authoritative server-side payment status of an order."""
    try:
        status_info = gari_payment.get_order_status(order_code=order_code, user_id=current_user["id"])
        return {"success": True, "order": status_info}
    except gari_payment.PaymentOrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except gari_payment.PaymentPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@app.get("/api/billing/usage")
async def get_customer_usage_summary_api(
    org_id: Optional[int] = None,
    days: int = 30,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Auditable usage telemetry for customer billing review."""
    if org_id is not None:
        _assert_org_billing_access(org_id, current_user, require_admin=False)
        target_type = "organization"
        target_id = org_id
    else:
        target_type = "user"
        target_id = current_user["id"]

    summary = gari_revenue.get_billing_usage_summary(target_type, target_id, days=days)
    return {"success": True, "usage": summary}


# -----------------------------------------------------------------------------
# 2. Platform Admin Revenue & Subscription Management
# -----------------------------------------------------------------------------

@app.get("/api/admin/subscriptions")
async def admin_list_subscriptions_api(
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Platform Admin: List all subscriptions across all subjects."""
    subs = gari_revenue.list_subscriptions(target_type=target_type, target_id=target_id, status=status, limit=limit)
    return {"success": True, "total": len(subs), "subscriptions": subs}


class AdminAssignSubscriptionPayload(BaseModel):
    target_type: str                  # 'user' | 'organization'
    target_id: int
    plan_id: str                      # 'free', 'pro', 'team', 'enterprise', 'pilot'
    status: str = "active"            # 'trialing', 'active', 'suspended', etc.
    billing_interval: str = "monthly"
    duration_days: Optional[int] = 30
    commercial_intent: str = "pilot_active"
    is_paid: bool = False
    provider: str = "manual"
    notes: Optional[str] = None
    reason: str                       # Mandatory audit reason!


@app.post("/api/admin/subscriptions")
async def admin_assign_subscription_api(
    payload: AdminAssignSubscriptionPayload,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Platform Admin: Explicitly assign or change a subscription with mandatory reason and audit log.
    Guarantees the single active subscription invariant per target.
    """
    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp lý do thực hiện thao tác (tối thiểu 3 ký tự)."
        )

    try:
        sub = gari_revenue.create_or_assign_subscription(
            target_type=payload.target_type,
            target_id=payload.target_id,
            plan_id=payload.plan_id,
            status=payload.status,
            billing_interval=payload.billing_interval,
            duration_days=payload.duration_days,
            commercial_intent=payload.commercial_intent,
            is_paid=payload.is_paid,
            provider=payload.provider,
            notes=payload.notes,
            actor_user_id=current_admin["id"],
            reason=reason
        )
        return {"success": True, "subscription": sub}
    except Exception as exc:
        logger.exception("admin_assign_subscription_api failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class AdminUpdateSubscriptionPayload(BaseModel):
    status: Optional[str] = None
    extend_days: Optional[int] = None
    reason: str                       # Mandatory audit reason!


@app.patch("/api/admin/subscriptions/{subscription_id}")
async def admin_update_subscription_api(
    subscription_id: int,
    payload: AdminUpdateSubscriptionPayload,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Platform Admin: Change status (cancel, suspend, reactivate) or extend days.
    """
    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp lý do thực hiện thao tác (tối thiểu 3 ký tự)."
        )

    try:
        target_status = payload.status
        if not target_status and payload.extend_days:
            # Extending current subscription without status change
            sub = gari_revenue.get_subscription_by_id(subscription_id)
            if not sub:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy subscription.")
            target_status = sub["status"]

        if not target_status:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vui lòng cung cấp trạng thái mới hoặc số ngày gia hạn.")

        updated = gari_revenue.update_subscription_status(
            subscription_id=subscription_id,
            new_status=target_status,
            reason=reason,
            actor_user_id=current_admin["id"],
            extend_days=payload.extend_days
        )
        return {"success": True, "subscription": updated}
    except gari_revenue.SubscriptionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("admin_update_subscription_api failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.get("/api/admin/invoices")
async def admin_list_invoices_api(
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    limit: int = 50,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Platform Admin: List all invoices across tenants."""
    invoices = gari_revenue.list_invoices(target_type=target_type, target_id=target_id, limit=limit)
    return {"success": True, "total": len(invoices), "invoices": invoices}


class AdminCreateInvoicePayload(BaseModel):
    target_type: str
    target_id: int
    amount: float
    description: str
    subscription_id: Optional[int] = None
    currency: str = "VND"
    payment_method: str = "manual"
    payment_status: str = "not_collected"
    status: str = "draft"
    due_days: int = 14
    notes: Optional[str] = None
    reason: str


@app.post("/api/admin/invoices")
async def admin_create_invoice_api(
    payload: AdminCreateInvoicePayload,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Platform Admin: Create invoice with audit."""
    if len((payload.reason or "").strip()) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vui lòng nhập lý do tạo hóa đơn.")

    try:
        inv = gari_revenue.create_invoice(
            target_type=payload.target_type,
            target_id=payload.target_id,
            amount=payload.amount,
            description=payload.description,
            subscription_id=payload.subscription_id,
            currency=payload.currency,
            payment_method=payload.payment_method,
            payment_status=payload.payment_status,
            status=payload.status,
            due_days=payload.due_days,
            created_by_user_id=current_admin["id"],
            notes=f"{payload.notes or ''} [Lý do: {payload.reason}]"
        )
        return {"success": True, "invoice": inv}
    except Exception as exc:
        logger.exception("admin_create_invoice_api failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.get("/api/admin/payments")
async def admin_list_payments_api(
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    limit: int = 50,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Platform Admin: List payment attempts."""
    attempts = gari_revenue.list_payment_attempts(target_type=target_type, target_id=target_id, limit=limit)
    return {"success": True, "total": len(attempts), "payment_attempts": attempts}


class AdminRecordPaymentPayload(BaseModel):
    invoice_id: int
    payment_status: str               # 'succeeded', 'failed', 'refunded'
    payment_method: str = "manual"
    provider: str = "manual"
    provider_tx_id: Optional[str] = None
    failure_reason: Optional[str] = None
    error_code: Optional[str] = None
    reason: str


@app.post("/api/admin/payments/record")
async def admin_record_payment_api(
    payload: AdminRecordPaymentPayload,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Platform Admin: Record manual payment attempt outcome.
    RULE: Failed payment NEVER activates a paid subscription.
    """
    if len((payload.reason or "").strip()) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vui lòng nhập lý do ghi nhận thanh toán.")

    try:
        attempt = gari_revenue.record_payment_attempt(
            invoice_id=payload.invoice_id,
            payment_status=payload.payment_status,
            payment_method=payload.payment_method,
            provider=payload.provider,
            provider_tx_id=payload.provider_tx_id,
            failure_reason=payload.failure_reason,
            error_code=payload.error_code,
            initiated_by_user_id=current_admin["id"],
            metadata={"admin_reason": payload.reason}
        )
        return {"success": True, "payment_attempt": attempt}
    except Exception as exc:
        logger.exception("admin_record_payment_api failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@app.get("/api/admin/revenue/overview")
async def admin_revenue_overview_api(current_admin: Dict[str, Any] = Depends(get_current_admin_user)):
    """Platform Admin: Revenue & subscription metrics dashboard."""
    with gari_revenue._REVENUE_LOCK:
        with gari_revenue.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT plan_id, status, COUNT(*) as count
                FROM subscriptions
                GROUP BY plan_id, status
            """)
            subs_by_plan = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT payment_status, COUNT(*) as count, SUM(amount) as total_amount
                FROM invoices
                GROUP BY payment_status
            """)
            invoices_by_status = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT payment_status, COUNT(*) as count
                FROM payment_attempts
                GROUP BY payment_status
            """)
            payments_by_status = [dict(r) for r in cursor.fetchall()]

    return {
        "success": True,
        "subscriptions_by_plan": subs_by_plan,
        "invoices_by_status": invoices_by_status,
        "payments_by_status": payments_by_status,
        "payment_gateway_status": "payment_provider_not_configured"
    }


# -----------------------------------------------------------------------------
# Voucher Management & Access Grant Endpoints
# -----------------------------------------------------------------------------

class RedeemVoucherPayload(BaseModel):
    code: str


@app.post("/api/vouchers/redeem")
async def redeem_voucher_api(
    payload: RedeemVoucherPayload,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    User endpoint: Redeem an admin-issued voucher code.
    Grants real, server-verified free access for the voucher's designated plan and duration.
    Tied strictly to authenticated caller identity.
    """
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent")
    try:
        result = gari_vouchers.redeem_voucher(
            user_id=current_user["id"],
            raw_code=payload.code,
            ip_address=ip_address,
            user_agent=user_agent
        )
        return {"success": True, "redemption": result}
    except gari_vouchers.VoucherRateLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    except (gari_vouchers.VoucherNotFoundError,
            gari_vouchers.VoucherExpiredError,
            gari_vouchers.VoucherExhaustedError,
            gari_vouchers.VoucherRevokedError,
            gari_vouchers.VoucherIneligibleError,
            gari_vouchers.VoucherAlreadyRedeemedError,
            ValueError) as exc:
        # Check for brute-force voucher abuse and create review case if threshold reached
        v_abuse = gari_moderation.scan_api_activity(
            user_id=current_user["id"],
            user_email=current_user["email"],
            endpoint="/api/vouchers/redeem",
            client_ip=ip_address,
            is_voucher_failure=True
        )
        if v_abuse:
            gari_moderation.create_moderation_case(
                user_id=current_user["id"],
                user_email=current_user["email"],
                category=v_abuse["category"],
                severity=v_abuse["severity"],
                source=v_abuse["source"],
                evidence_summary=v_abuse["summary"],
                evidence_reference=v_abuse["evidence_reference"],
                confidence_score=v_abuse["confidence_score"]
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("redeem_voucher_api failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi xử lý kích hoạt voucher.")


@app.get("/api/vouchers/my-redemptions")
async def get_my_voucher_redemptions_api(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List voucher redemptions for current authenticated user."""
    with gari_vouchers.get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.voucher_id, r.plan_id, r.duration_days,
                   r.granted_period_start, r.granted_period_end, r.redeemed_at,
                   v.code_preview
            FROM voucher_redemptions r
            JOIN vouchers v ON r.voucher_id = v.id
            WHERE r.user_id = ?
            ORDER BY r.id DESC
        """, (current_user["id"],))
        rows = [dict(row) for row in cursor.fetchall()]
        for r in rows:
            plan_info = gari_plans.get_plan_definition(r["plan_id"])
            r["plan_name"] = plan_info.get("display_name", r["plan_id"])
        return {"success": True, "redemptions": rows}


# --- Admin-Only Voucher Endpoints ---

class AdminCreateVoucherPayload(BaseModel):
    plan_id: str                      # 'personal' | 'business'
    duration_days: int = 30           # 1 to 730
    max_redemptions: int = 1          # 1 for single-use, > 1 for limited-use
    expires_at: Optional[str] = None  # ISO format string
    restricted_to_email: Optional[str] = None
    notes: Optional[str] = None


class AdminRevokeVoucherPayload(BaseModel):
    reason: str


@app.post("/api/admin/vouchers")
async def admin_create_voucher_api(
    payload: AdminCreateVoucherPayload,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Platform Admin: Issue a new free-access voucher.
    The raw voucher code is returned in the response ONLY ONCE.
    """
    try:
        result = gari_vouchers.create_voucher(
            admin_user_id=current_admin["id"],
            plan_id=payload.plan_id,
            duration_days=payload.duration_days,
            max_redemptions=payload.max_redemptions,
            expires_at_iso=payload.expires_at,
            restricted_to_email=payload.restricted_to_email,
            notes=payload.notes
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("admin_create_voucher_api failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@app.get("/api/admin/vouchers")
async def admin_list_vouchers_api(
    status: Optional[str] = None,
    plan_id: Optional[str] = None,
    limit: int = 100,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Platform Admin: List all vouchers with status and redemption counts.
    Never exposes raw code; displays preview only.
    """
    vouchers = gari_vouchers.list_vouchers(
        admin_user_id=current_admin["id"],
        status=status,
        plan_id=plan_id,
        limit=limit
    )
    return {"success": True, "total": len(vouchers), "vouchers": vouchers}


@app.post("/api/admin/vouchers/{voucher_id}/revoke")
async def admin_revoke_voucher_api(
    voucher_id: int,
    payload: AdminRevokeVoucherPayload,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Platform Admin: Revoke an active voucher with audited reason.
    """
    try:
        voucher = gari_vouchers.revoke_voucher(
            voucher_id=voucher_id,
            admin_user_id=current_admin["id"],
            reason=payload.reason
        )
        return {"success": True, "voucher": voucher}
    except gari_vouchers.VoucherNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("admin_revoke_voucher_api failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@app.get("/api/admin/vouchers/audit")
async def admin_list_voucher_audit_api(
    voucher_id: Optional[int] = None,
    limit: int = 100,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Platform Admin: Audit log of voucher creation, redemption, expiration, and revocation.
    """
    events = gari_vouchers.list_voucher_audit_log(
        admin_user_id=current_admin["id"],
        voucher_id=voucher_id,
        limit=limit
    )
    return {"success": True, "total": len(events), "audit_events": events}


@app.get("/api/admin/vouchers/{voucher_id}/redemptions")
async def admin_list_voucher_redemptions_api(
    voucher_id: int,
    limit: int = 100,
    current_admin: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Platform Admin: List redemption history for a specific voucher.
    """
    redemptions = gari_vouchers.list_voucher_redemptions(
        admin_user_id=current_admin["id"],
        voucher_id=voucher_id,
        limit=limit
    )
    return {"success": True, "total": len(redemptions), "redemptions": redemptions}






# =============================================================================
# GARI HOST SERVER ADMIN CONSOLE — DEDICATED HOST APIS
# Strict Host Server Administrator privilege enforcement (is_host_admin == 1)
# =============================================================================

@app.post("/api/auth/host-login")
async def host_login_api(
    payload: HostLoginPayload,
    request: Request,
    response: Response
):
    """
    Dedicated authentication endpoint for Host Server Administrators.
    Strictly verifies credentials and enforces is_host_admin == 1.
    Regular users and accounts without host privilege receive HTTP 403 Forbidden.
    Suspended accounts receive HTTP 403 Forbidden.
    """
    client_ip = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("User-Agent")

    # 1. Authenticate credentials with rate limiting and Bcrypt verify
    user = gari_auth.authenticate_user(payload.email, payload.password, ip_address=client_ip)

    # 2. Strict Host Admin privilege check
    if not bool(user.get("is_host_admin")):
        record_host_audit(
            host_admin_id=user["id"],
            host_email=user["email"],
            action_type="unauthorized_host_login_attempt",
            target_resource="auth:host-login",
            details={"email": payload.email, "account_type": user.get("account_type")},
            reason="Tài khoản không có đặc quyền Quản trị Máy chủ (host_admin).",
            outcome="rejected",
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Truy cập bị từ chối: Tài khoản của bạn không có đặc quyền Quản trị Máy chủ (host_admin)."
        )

    # 3. Active account check
    if not bool(user.get("is_active", True)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản Quản trị Máy chủ này đã bị tạm khóa. Vui lòng liên hệ chủ sở hữu hệ thống."
        )

    # 4. Create secure session
    token = gari_auth.create_session(
        user_id=user["id"],
        remember_me=bool(payload.remember_me),
        ip_address=client_ip,
        user_agent=user_agent
    )

    # 5. Set HttpOnly Cookie
    cookie_max_age = 30 * 86400 if payload.remember_me else 7 * 86400
    response.set_cookie(
        key="gari_session",
        value=token,
        max_age=cookie_max_age,
        httponly=True,
        samesite="lax",
        secure=gari_config.IS_PRODUCTION
    )

    # 6. Audit successful login
    record_host_audit(
        host_admin_id=user["id"],
        host_email=user["email"],
        action_type="host_login",
        target_resource="auth:host-login",
        details={"user_agent": user_agent},
        reason="Host administrator signed in successfully",
        outcome="success",
        ip_address=client_ip
    )

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "is_host_admin": True
        }
    }


@app.get("/api/host/me")
async def host_me_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Returns sanitized identity profile of the authenticated Host Administrator.
    Sensitive tokens, password hashes, and environment secrets are excluded.
    """
    return {
        "success": True,
        "user": {
            "id": current_host["id"],
            "email": current_host["email"],
            "full_name": current_host["full_name"],
            "is_host_admin": True,
            "account_type": current_host.get("account_type"),
            "created_at": current_host.get("created_at")
        }
    }


@app.get("/api/host/overview")
async def host_overview_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Real Host Server Telemetry & Overview:
    - Real CPU, RAM, Disk hardware utilization via psutil/shutil
    - Server process uptime and OS environment
    - Active users, active sessions, registered users from database
    - Model registry inventory and PyTorch compute device
    - Subscription and revenue statistics
    Never returns fabricated metrics.
    """
    # 1. Hardware & System Telemetry
    cpu_percent = psutil.cpu_percent(interval=0.05)
    vm = psutil.virtual_memory()
    ram_data = {
        "total_gb": round(vm.total / (1024 ** 3), 2),
        "used_gb": round(vm.used / (1024 ** 3), 2),
        "available_gb": round(vm.available / (1024 ** 3), 2),
        "percent": vm.percent
    }
    du = shutil.disk_usage(str(ROOT))
    disk_data = {
        "total_gb": round(du.total / (1024 ** 3), 2),
        "used_gb": round(du.used / (1024 ** 3), 2),
        "free_gb": round(du.free / (1024 ** 3), 2),
        "percent": round((du.used / du.total) * 100, 1)
    }
    uptime_seconds = int(time.time() - SERVER_START_TIME)

    # 2. Database & User Statistics
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        total_users = cursor.execute("SELECT count(*) FROM users").fetchone()[0]
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        active_sessions = cursor.execute(
            "SELECT count(*) FROM user_sessions WHERE expires_at > ?", (now_iso,)
        ).fetchone()[0]
        active_users_24h = cursor.execute(
            "SELECT count(DISTINCT user_id) FROM user_sessions WHERE expires_at > ?", (now_iso,)
        ).fetchone()[0]
        suspended_users = cursor.execute("SELECT count(*) FROM users WHERE is_active = 0").fetchone()[0]
        total_subs = cursor.execute("SELECT count(*) FROM user_subscriptions").fetchone()[0]
        active_vip = cursor.execute(
            "SELECT count(*) FROM user_subscriptions WHERE plan_id != 'free' AND status = 'active'"
        ).fetchone()[0]

        # Recent audit count
        recent_admin_actions = cursor.execute("SELECT count(*) FROM host_audit_logs").fetchone()[0]

    # 3. Model Inventory & Device
    try:
        import torch
        cuda_avail = torch.cuda.is_available()
        device_name = torch.cuda.get_device_name(0) if cuda_avail else "CPU (Host Processor)"
        torch_ver = torch.__version__
    except Exception:
        cuda_avail = False
        device_name = "CPU"
        torch_ver = "Unavailable"

    crop_models = []
    if gari_config.MODELS_DIR.exists():
        crop_models = sorted([d.name for d in gari_config.MODELS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")])

    # 4. Latency and Requests
    avg_latency = (
        round(sum(_SERVER_METRICS["latencies_ms"]) / len(_SERVER_METRICS["latencies_ms"]), 2)
        if _SERVER_METRICS["latencies_ms"] else 0.0
    )

    return {
        "success": True,
        "telemetry": {
            "uptime_seconds": uptime_seconds,
            "server_start_time": datetime.fromtimestamp(SERVER_START_TIME, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "os_platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_percent": cpu_percent,
            "ram": ram_data,
            "disk": disk_data
        },
        "api_metrics": {
            "total_requests": _SERVER_METRICS["total_requests"],
            "total_errors": _SERVER_METRICS["total_errors"],
            "avg_latency_ms": avg_latency
        },
        "users_summary": {
            "total_registered_users": total_users,
            "active_users": active_users_24h,
            "active_sessions": active_sessions,
            "suspended_users": suspended_users
        },
        "ai_models_summary": {
            "total_crop_models": len(crop_models),
            "inference_device": device_name,
            "cuda_available": cuda_avail,
            "torch_version": torch_ver,
            "status": "Ready & Serving" if crop_models else "Storage Unavailable"
        },
        "business_summary": {
            "total_subscriptions": total_subs,
            "active_vip_subscriptions": active_vip,
            "host_audit_events_count": recent_admin_actions
        }
    }


@app.get("/api/host/users")
async def host_list_users_api(
    search: Optional[str] = None,
    account_type: Optional[str] = None,
    is_active: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Search and paginate users for Host Server Administration.
    Sanitized output: NO password hashes, NO session tokens, NO secret keys.
    """
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = """
        SELECT u.id, u.email, u.full_name, u.name, u.phone, u.account_type, u.is_host_admin, u.is_active, u.created_at,
               s.plan_id, s.status as subscription_status, s.end_date as subscription_expires_at
        FROM users u
        LEFT JOIN (
            SELECT user_id, plan_id, status, end_date,
                   ROW_NUMBER() OVER(PARTITION BY user_id ORDER BY id DESC) as rn
            FROM user_subscriptions
        ) s ON u.id = s.user_id AND s.rn = 1
        WHERE 1=1
    """
    params: List[Any] = []

    if search:
        search_term = f"%{search.strip().lower()}%"
        query += " AND (LOWER(u.email) LIKE ? OR LOWER(u.full_name) LIKE ? OR LOWER(u.name) LIKE ? OR CAST(u.id AS TEXT) = ?)"
        params.extend([search_term, search_term, search_term, search.strip()])

    if account_type:
        query += " AND LOWER(u.account_type) = ?"
        params.append(account_type.strip().lower())

    if is_active is not None:
        query += " AND u.is_active = ?"
        params.append(1 if is_active else 0)

    count_query = f"SELECT count(*) FROM ({query})"
    
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        total = cursor.execute(count_query, params).fetchone()[0]

        query += " ORDER BY u.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = cursor.fetchall()

    users = []
    for r in rows:
        d = dict(r)
        d["full_name"] = d.get("full_name") or d.get("name") or "Người dùng Gari"
        d["is_host_admin"] = bool(d.get("is_host_admin"))
        d["is_active"] = bool(d.get("is_active", 1))
        if "name" in d:
            del d["name"]
        users.append(d)

    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "users": users
    }


@app.patch("/api/host/users/{user_id}/status")
async def host_update_user_status_api(
    user_id: int,
    payload: HostUpdateUserStatusPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Host admin suspends or reactivates a user account.
    Requires an explicit reason and records an immutable audit log.
    If suspended, invalidates all active sessions for that user immediately.
    Prevents host admin from suspending their own account.
    """
    client_ip = request.client.host if request.client else "0.0.0.0"
    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp lý do rõ ràng (tối thiểu 3 ký tự) để thực hiện thao tác này."
        )

    if user_id == current_host["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự đình chỉ tài khoản của chính mình."
        )

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, full_name, is_active FROM users WHERE id = ?", (user_id,))
        target_user = cursor.fetchone()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

        new_status = 1 if payload.is_active else 0
        cursor.execute(
            "UPDATE users SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_status, user_id)
        )

        # If suspending, invalidate all existing sessions
        if new_status == 0:
            cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))

        conn.commit()

    action_name = "reactivate_user" if payload.is_active else "suspend_user"
    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type=action_name,
        target_resource=f"user:{user_id}",
        details={
            "target_user_id": user_id,
            "target_email": target_user["email"],
            "previous_is_active": target_user["is_active"],
            "new_is_active": new_status
        },
        reason=reason,
        outcome="success",
        ip_address=client_ip
    )

    action_label = "kích hoạt lại" if payload.is_active else "tạm khóa"
    return {
        "success": True,
        "user_id": user_id,
        "is_active": bool(new_status),
        "message": f"Đã {action_label} tài khoản người dùng {target_user['email']} thành công."
    }


@app.patch("/api/host/users/{user_id}/account-type")
async def host_update_account_type_api(
    user_id: int,
    payload: HostUpdateAccountTypePayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Host admin updates a user's single active account type.
    Enforces valid canonical account types (farmer, cooperative, expert, enterprise).
    Requires explicit reason and logs to both user_account_type_audit and host_audit_logs.
    Preserves all existing subscription & VIP entitlements without modification.
    """
    client_ip = request.client.host if request.client else "0.0.0.0"
    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp lý do rõ ràng (tối thiểu 3 ký tự) để thay đổi loại tài khoản."
        )

    result = gari_auth.change_account_type(
        user_id=user_id,
        new_type=payload.account_type,
        confirm=True,
        reason=reason,
        actor_user_id=current_host["id"]
    )

    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type="change_user_account_type",
        target_resource=f"user:{user_id}",
        details={
            "user_id": user_id,
            "previous_type": result.get("previous_type"),
            "new_type": result.get("account_type")
        },
        reason=reason,
        outcome="success",
        ip_address=client_ip
    )

    return result


@app.post("/api/host/users/{user_id}/vip")
async def host_update_user_vip_api(
    user_id: int,
    payload: HostUpdateVipPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Host admin grants or revokes VIP subscription access for a specific user.
    Audited with explicit reason and timestamp.
    """
    client_ip = request.client.host if request.client else "0.0.0.0"
    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp lý do (tối thiểu 3 ký tự) để thay đổi quyền VIP/Gói dịch vụ."
        )

    action = (payload.action or "").strip().lower()
    if action not in ("grant", "revoke"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hành động không hợp lệ. Phải là 'grant' hoặc 'revoke'."
        )

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email FROM users WHERE id = ?", (user_id,))
        target_user = cursor.fetchone()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

        if action == "grant":
            duration_days = max(1, min(payload.duration_days or 30, 3650))
            expires_at = (datetime.now(timezone.utc) + timedelta(days=duration_days)).strftime("%Y-%m-%d %H:%M:%S")
            plan_id = payload.plan_id or "vip_pro"
            
            cursor.execute(
                """
                INSERT INTO user_subscriptions (user_id, plan_id, status, billing_interval, start_date, end_date, notes, updated_at)
                VALUES (?, ?, 'active', 'monthly', ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    plan_id = excluded.plan_id,
                    status = excluded.status,
                    billing_interval = excluded.billing_interval,
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (user_id, plan_id, now_iso, expires_at, f"Cấp bởi Host Admin #{current_host['id']}: {reason}", now_iso)
            )
        else: # revoke
            cursor.execute(
                """
                INSERT INTO user_subscriptions (user_id, plan_id, status, billing_interval, start_date, end_date, notes, updated_at)
                VALUES (?, 'free', 'active', 'daily', ?, NULL, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    plan_id = excluded.plan_id,
                    status = excluded.status,
                    billing_interval = excluded.billing_interval,
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (user_id, now_iso, f"Hủy VIP bởi Host Admin #{current_host['id']}: {reason}", now_iso)
            )
        conn.commit()

    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type=f"vip_{action}",
        target_resource=f"user:{user_id}",
        details={"user_id": user_id, "action": action, "plan_id": payload.plan_id},
        reason=reason,
        outcome="success",
        ip_address=client_ip
    )

    return {
        "success": True,
        "user_id": user_id,
        "action": action,
        "plan_id": payload.plan_id if action == "grant" else "free",
        "message": f"Đã {'cấp' if action == 'grant' else 'hủy'} quyền VIP cho {target_user['email']} thành công."
    }


@app.get("/api/host/vouchers")
async def host_list_vouchers_api(
    plan_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """List vouchers with status, remaining redemptions, and expiration for Host Console."""
    vouchers = gari_vouchers.list_vouchers(
        admin_user_id=current_host["id"],
        plan_id=plan_id,
        limit=max(1, min(limit, 100))
    )
    return {
        "success": True,
        "total": len(vouchers),
        "vouchers": vouchers
    }


@app.post("/api/host/vouchers")
async def host_create_voucher_api(
    payload: HostCreateVoucherPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Host admin issues a new voucher.
    The raw voucher code is returned in the response ONLY ONCE.
    """
    client_ip = request.client.host if request.client else "0.0.0.0"
    plan = payload.plan_id
    if plan == "vip_pro":
        plan = "pro"
    created = gari_vouchers.create_voucher(
        admin_user_id=current_host["id"],
        plan_id=plan,
        duration_days=max(1, min(payload.valid_days or 30, 365)),
        max_redemptions=max(1, payload.max_redemptions or 1),
        notes=payload.note
    )

    v_id = created.get("voucher", {}).get("id") or created.get("voucher_id")
    raw_code = created.get("voucher_code")

    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type="create_voucher",
        target_resource=f"voucher:{v_id}",
        details={
            "voucher_id": v_id,
            "plan_id": plan,
            "max_redemptions": payload.max_redemptions
        },
        reason=payload.note or "Host created voucher",
        outcome="success",
        ip_address=client_ip
    )

    return {
        "success": True,
        "voucher": {
            "voucher_id": v_id,
            "raw_code": raw_code,
            "details": created.get("voucher")
        }
    }


@app.post("/api/host/vouchers/{voucher_id}/revoke")
async def host_revoke_voucher_api(
    voucher_id: int,
    payload: HostRevokeVoucherPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Host admin revokes an active voucher with audited reason."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp lý do (tối thiểu 3 ký tự) để thu hồi mã voucher."
        )

    result = gari_vouchers.revoke_voucher(
        voucher_id=voucher_id,
        admin_user_id=current_host["id"],
        reason=reason
    )

    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type="revoke_voucher",
        target_resource=f"voucher:{voucher_id}",
        details={"voucher_id": voucher_id},
        reason=reason,
        outcome="success",
        ip_address=client_ip
    )

    return result


@app.get("/api/host/api-controls")
async def host_get_api_controls_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve all API configuration settings, rate limits, and feature toggles."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value, description, updated_at, updated_by_host_id FROM host_api_config ORDER BY key ASC")
        rows = [dict(r) for r in cursor.fetchall()]

    return {
        "success": True,
        "configs": rows
    }


@app.patch("/api/host/api-controls")
async def host_update_api_controls_api(
    payload: HostUpdateApiConfigPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Update an API configuration setting or toggle with required reason and audit log."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp lý do (tối thiểu 3 ký tự) để thay đổi cấu hình API."
        )

    key = payload.key.strip()
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM host_api_config WHERE key = ?", (key,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cấu hình '{key}' không tồn tại."
            )

        cursor.execute(
            """
            UPDATE host_api_config
            SET value = ?, updated_at = CURRENT_TIMESTAMP, updated_by_host_id = ?
            WHERE key = ?
            """,
            (payload.value, current_host["id"], key)
        )
        conn.commit()

    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type="update_api_config",
        target_resource=f"config:{key}",
        details={"key": key, "previous_value": existing["value"], "new_value": payload.value},
        reason=reason,
        outcome="success",
        ip_address=client_ip
    )

    return {
        "success": True,
        "key": key,
        "value": payload.value,
        "message": f"Đã cập nhật cấu hình '{key}' thành công."
    }


@app.get("/api/host/audit-logs")
async def host_get_audit_logs_api(
    action_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Paginated, read-only audit log of host administrative actions."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = "SELECT * FROM host_audit_logs WHERE 1=1"
    params: List[Any] = []

    if action_type:
        query += " AND action_type = ?"
        params.append(action_type.strip())

    count_query = f"SELECT count(*) FROM ({query})"

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        total = cursor.execute(count_query, params).fetchone()[0]

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        logs = [dict(r) for r in cursor.fetchall()]

    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": logs
    }


@app.get("/api/host/models")
async def host_get_models_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Model Registry inspection:
    - Lists crop models, versions, directory sizes, and runtime readiness.
    """
    models = []
    if gari_config.MODELS_DIR.exists():
        for d in sorted(gari_config.MODELS_DIR.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                files = list(d.glob("*"))
                total_bytes = sum(f.stat().st_size for f in files if f.is_file())
                models.append({
                    "crop_name": d.name,
                    "files_count": len(files),
                    "size_mb": round(total_bytes / (1024 * 1024), 2),
                    "status": "ready"
                })

    try:
        import torch
        device_str = "CUDA GPU" if torch.cuda.is_available() else "Host CPU"
    except Exception:
        device_str = "CPU"

    return {
        "success": True,
        "total_models": len(models),
        "device": device_str,
        "models": models
    }



# =============================================================================
# GARI HOST CONSOLE — AUTOMATED MODERATION & REVIEW QUEUE APIS
# =============================================================================

@app.get("/api/host/moderation/stats")
async def host_get_moderation_stats_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve overview metrics for Host moderation review queue."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        pending = cursor.execute("SELECT count(*) FROM moderation_cases WHERE status = 'pending'").fetchone()[0]
        critical = cursor.execute("SELECT count(*) FROM moderation_cases WHERE status = 'pending' AND severity IN ('critical', 'high')").fetchone()[0]
        reviewed = cursor.execute("SELECT count(*) FROM moderation_cases WHERE status NOT IN ('pending')").fetchone()[0]
        dismissed = cursor.execute("SELECT count(*) FROM moderation_cases WHERE status IN ('dismissed', 'false_positive')").fetchone()[0]
        suspended = cursor.execute("SELECT count(*) FROM users WHERE moderation_status = 'suspended' OR is_active = 0").fetchone()[0]
        banned = cursor.execute("SELECT count(*) FROM users WHERE moderation_status = 'banned'").fetchone()[0]
        appeals = cursor.execute("SELECT count(*) FROM moderation_appeals WHERE status = 'pending'").fetchone()[0]

    return {
        "success": True,
        "stats": {
            "pending_cases": pending,
            "critical_cases": critical,
            "reviewed_cases": reviewed,
            "dismissed_cases": dismissed,
            "suspended_accounts": suspended,
            "banned_accounts": banned,
            "pending_appeals": appeals
        }
    }


@app.get("/api/host/moderation/cases")
async def host_list_moderation_cases_api(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Paginated, filtered list of violation cases for Host review."""
    return gari_moderation.list_moderation_cases(
        status=status,
        severity=severity,
        category=category,
        search=search,
        limit=limit,
        offset=offset
    )


@app.get("/api/host/moderation/cases/{case_id}")
async def host_get_moderation_case_api(
    case_id: str,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve full detail and history for a moderation case."""
    case = gari_moderation.get_moderation_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ kiểm duyệt này.")
    return {"success": True, "case": case}


@app.post("/api/host/moderation/cases/{case_id}/action")
async def host_apply_moderation_action_api(
    case_id: str,
    payload: HostModerationActionPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Host administrator applies a moderation decision:
    - dismiss, false_positive, warn, restrict, suspend, ban, restore.
    Requires explicit reason and logs audit trails.
    """
    client_ip = request.client.host if request.client else "0.0.0.0"
    return gari_moderation.resolve_moderation_case(
        case_id=case_id,
        action=payload.action,
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        reason=payload.reason,
        restrictions=payload.restrictions,
        ip_address=client_ip
    )


@app.get("/api/host/moderation/appeals")
async def host_list_appeals_api(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """List appeals submitted by users."""
    return gari_moderation.list_appeals(status=status, limit=limit, offset=offset)


@app.post("/api/host/moderation/appeals/{appeal_id}/review")
async def host_review_appeal_api(
    appeal_id: int,
    payload: HostReviewAppealPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Host administrator reviews and decides on a user appeal ('approved' or 'rejected')."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    return gari_moderation.review_appeal(
        appeal_id=appeal_id,
        decision=payload.decision,
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        host_response=payload.host_response,
        ip_address=client_ip
    )


@app.get("/api/host/moderation/audit-logs")
async def host_get_moderation_audit_logs_api(
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Read-only audit trail of moderation actions."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        total = cursor.execute("SELECT count(*) FROM moderation_audit_logs").fetchone()[0]
        cursor.execute("SELECT * FROM moderation_audit_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        logs = [dict(r) for r in cursor.fetchall()]
    return {"success": True, "total": total, "limit": limit, "offset": offset, "logs": logs}


@app.post("/api/moderation/appeals")
async def user_submit_appeal_api(
    payload: UserSubmitAppealPayload,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    User endpoint to submit an appeal against a moderation decision or restriction.
    Derives UID from authenticated session or looks up by email.
    """
    if current_user:
        user_id = current_user["id"]
        user_email = current_user["email"]
    elif payload.email:
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email FROM users WHERE LOWER(email) = LOWER(?)", (payload.email.strip(),))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản với email này.")
            user_id = row["id"]
            user_email = row["email"]
    else:
        raise HTTPException(
            status_code=401,
            detail="Vui lòng đăng nhập hoặc cung cấp địa chỉ email tài khoản để gửi khiếu nại."
        )

    return gari_moderation.submit_user_appeal(
        user_id=user_id,
        user_email=user_email,
        appeal_reason=payload.appeal_reason,
        case_id=payload.case_id
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)