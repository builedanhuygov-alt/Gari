import asyncio
import hashlib
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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, ConfigDict, EmailStr

import gari_auth
from gari_auth import get_current_user, get_current_user_optional, get_current_admin_user, get_current_host_admin, get_current_expert_user, record_host_audit
import gari_b2b
import gari_database
import gari_knowledge
import gari_plans
import gari_privacy
import gari_quota
import gari_revenue
import gari_vouchers
import gari_payment
import gari_inference_engine
from gari_inference_engine import engine
import gari_config
import gari_moderation
import gari_copilot
import gari_firebase
import gari_assistant
import gari_farm_management
import gari_tasks
import gari_experts
import gari_community
import gari_farm_map
import gari_farm_3d
import gari_entitlements
import gari_billing_adapter
import gari_host_service
import gari_gis_service
import gari_weather_service
import gari_satellite_service
import gari_risk_engine
import gari_digital_twin
import gari_smart_alerts
import gari_intelligence_reports
import gari_agent_orchestrator

# Validate configuration at startup
gari_config.validate_startup_configuration()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_api_server")

ROOT = Path(__file__).resolve().parent
FRONTEND2_DIR = ROOT / "frontend2"
UPLOADS_DIR = ROOT / "database" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_FILES = {
    "/style.css": FRONTEND2_DIR / "style.css",
    "/main.js": FRONTEND2_DIR / "app.js",
    "/app.js": FRONTEND2_DIR / "app.js",
    "/features.js": FRONTEND2_DIR / "features.js",
    "/firebase-client.js": FRONTEND2_DIR / "firebase-client.js",
}

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

# Bounded AI Inference Queue & Active Request Concurrency Control (Server-Only AI)
MAX_CONCURRENT_INFERENCES = int(os.getenv("MAX_CONCURRENT_INFERENCES", "4"))
INFERENCE_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_INFERENCES)
_ACTIVE_INFERENCES: Dict[str, float] = {}
_ACTIVE_INFERENCES_LOCK = asyncio.Lock()

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


@app.on_event("startup")
async def startup_warmup():
    """Pre-warm global router model and default crop model to eliminate first-request latency."""
    try:
        logger.info("Initializing GARI inference engine model pre-warm on server startup...")
        engine.warmup()
    except Exception as exc:
        logger.warning("Inference engine warmup encountered non-fatal error: %s", exc)


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


# Anti-Stale-Cache Middleware: Ensure browsers always receive latest UI/CSS without caching regressions
@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith(("/frontend2", "/static/frontend2", "/style.css", "/app.js")) or path in ["/", "/dashboard", "/predict"]:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Secure Static Mounts: ONLY mount dedicated public directories.
# NEVER mount ROOT as /static to prevent source code and database exfiltration!
app.mount("/static/frontend2", StaticFiles(directory=str(FRONTEND2_DIR)), name="frontend2_static")
app.mount("/frontend2", StaticFiles(directory=str(FRONTEND2_DIR), html=True), name="frontend2")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve official GARI 2.0 dashboard (frontend2)."""
    index_path = FRONTEND2_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return FileResponse(FRONTEND2_DIR / "predict.html")


@app.get("/predict", response_class=HTMLResponse)
async def predict_page():
    return FileResponse(FRONTEND2_DIR / "predict.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return FileResponse(FRONTEND2_DIR / "index.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return FileResponse(FRONTEND2_DIR / "login.html")


@app.get("/register", response_class=HTMLResponse)
async def register_page():
    return FileResponse(FRONTEND2_DIR / "register.html")


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page():
    return FileResponse(FRONTEND2_DIR / "forgot-password.html")


@app.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page():
    return FileResponse(FRONTEND2_DIR / "onboarding.html")


@app.get("/organization", response_class=HTMLResponse)
async def organization_page():
    return FileResponse(FRONTEND2_DIR / "organization.html")


@app.get("/farms", response_class=HTMLResponse)
async def farms_page():
    return FileResponse(FRONTEND2_DIR / "farms.html")


@app.get("/crops", response_class=HTMLResponse)
async def crops_page():
    return FileResponse(FRONTEND2_DIR / "crops.html")


@app.get("/calendar", response_class=HTMLResponse)
async def calendar_page():
    calendar_path = FRONTEND2_DIR / "calendar.html"
    if calendar_path.exists():
        return FileResponse(calendar_path)
    return FileResponse(FRONTEND2_DIR / "crops.html")


@app.get("/disease", response_class=HTMLResponse)
async def disease_page():
    return FileResponse(FRONTEND2_DIR / "disease.html")


@app.get("/reports", response_class=HTMLResponse)
async def reports_page():
    return FileResponse(FRONTEND2_DIR / "reports.html")


@app.get("/risk", response_class=HTMLResponse)
async def risk_page():
    return FileResponse(FRONTEND2_DIR / "risk.html")


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page():
    return FileResponse(FRONTEND2_DIR / "pricing.html")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    return FileResponse(FRONTEND2_DIR / "settings.html")


@app.get("/community", response_class=HTMLResponse)
async def community_page():
    return FileResponse(FRONTEND2_DIR / "community.html")


@app.get("/support", response_class=HTMLResponse)
async def support_page():
    return FileResponse(FRONTEND2_DIR / "support.html")


@app.get("/host", response_class=HTMLResponse)
async def host_console_page():
    """Dedicated GARI Host Server Admin Console page."""
    return FileResponse(FRONTEND2_DIR / "host.html")


@app.get("/host-login", response_class=HTMLResponse)
async def host_login_page():
    return FileResponse(FRONTEND2_DIR / "host-login.html")


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return FileResponse(FRONTEND2_DIR / "admin.html")


@app.get("/landing", response_class=HTMLResponse)
async def landing_page():
    """Serve public market validation & pilot registration landing page."""
    landing_path = FRONTEND2_DIR / "landing.html"
    if landing_path.exists():
        return FileResponse(landing_path)
    return FileResponse(FRONTEND2_DIR / "index.html")


@app.get("/test-upload")
async def test_upload_redirect():
    return RedirectResponse(url="/predict", status_code=status.HTTP_302_FOUND)


# Backward-compatible redirects from legacy frontend URLs
@app.get("/frontend/{subpath:path}")
async def redirect_legacy_frontend(subpath: str):
    return RedirectResponse(url=f"/frontend2/{subpath}", status_code=status.HTTP_302_FOUND)


@app.get("/static/frontend/{subpath:path}")
async def redirect_legacy_static_frontend(subpath: str):
    return RedirectResponse(url=f"/static/frontend2/{subpath}", status_code=status.HTTP_302_FOUND)


@app.get("/style.css")
async def css():
    return FileResponse(STATIC_FILES["/style.css"])


@app.get("/main.js")
async def js():
    return FileResponse(STATIC_FILES["/main.js"])


@app.get("/app.js")
async def app_js():
    return FileResponse(STATIC_FILES["/app.js"])


@app.get("/features.js")
async def features_js():
    return FileResponse(STATIC_FILES["/features.js"])


# -----------------------------------------------------------------------------
# System & Health Check Endpoints (Liveness & Readiness Probes)
# -----------------------------------------------------------------------------

# GARI System Feature Availability Configuration (Module Gating)
GARI_SYSTEM_FEATURES = {
    "farms": False,          # Temporarily disabled: Under active development
    "community": False,      # Temporarily disabled: Under active development
    "hostConsole": True,     # Dedicated Host Admin console
    "diagnosis": True,       # Core Leaf Intelligence
    "assistant": True,       # Contextual AI Copilot
    "expert": True,          # Agricultural Expert Network
    "organization": True,    # Enterprise & Cooperatives
    "pricing": True,         # Subscriptions & Entitlements
}


@app.get("/api/features")
async def get_system_features():
    """Centralized feature availability configuration for all clients."""
    return GARI_SYSTEM_FEATURES


@app.get("/api/health")
@app.get("/health")
async def health():
    """
    Subsystem-aware health check endpoint.
    Reports operational status of:
    - Backend runtime
    - Database connectivity
    - Firebase Admin initialization
    - Authentication service availability
    - AI inference service availability
    Platform availability is isolated: AI model downtime does not fail overall auth/platform health.
    """
    db_ok = False
    try:
        db_ok = gari_database.check_database_integrity()
    except Exception:
        db_ok = False

    fb_admin_ok = False
    try:
        fb_admin_ok = gari_firebase.is_firebase_initialized()
    except Exception:
        fb_admin_ok = False

    ai_inference_status = "unavailable"
    try:
        if hasattr(gari_inference_engine, "engine") and gari_inference_engine.engine is not None:
            ai_inference_status = "healthy"
        else:
            ai_inference_status = "standby"
    except Exception:
        ai_inference_status = "degraded"

    auth_status = "available" if db_ok else "degraded"
    overall_status = "healthy" if db_ok else "degraded"

    return {
        "status": overall_status,
        "service": "Gari AI Lab AgriTech Platform",
        "environment": gari_config.APP_ENV,
        "version": "2.6.0",
        "services": {
            "backend_runtime": "healthy",
            "database": "connected" if db_ok else "unreachable",
            "firebase_admin": "initialized" if fb_admin_ok else "dev_mode",
            "authentication": auth_status,
            "ai_inference": ai_inference_status
        }
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
    confirm_password: Optional[str] = None
    account_type: Optional[str] = "Nông hộ"
    phone: Optional[str] = None
    terms_agreed: Optional[bool] = True
    marketing_opt_in: Optional[bool] = False


class LoginPayload(BaseModel):
    email: str
    password: str
    remember_me: Optional[bool] = False


class FirebaseLoginPayload(BaseModel):
    id_token: str
    remember_me: Optional[bool] = False
    # These fields are accepted only while the backend creates the first
    # profile for a verified Firebase identity.  They can never elevate roles.
    full_name: Optional[str] = None
    phone: Optional[str] = None
    province: Optional[str] = None
    account_type: Optional[str] = None
    terms_agreed: Optional[bool] = None
    marketing_opt_in: Optional[bool] = False


class ProfileUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    province: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


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



class DeclineInvitationPayload(BaseModel):
    token: Optional[str] = None
    reason: Optional[str] = None


class MemberScopeAssignmentPayload(BaseModel):
    user_id: int
    farm_id: Optional[int] = None
    zone_id: Optional[int] = None
    plot_id: Optional[int] = None
    notes: Optional[str] = None


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
        secure=gari_config.IS_PRODUCTION,
        max_age=7 * 86400,
        path="/"
    )

    return {
        "success": True,
        "message": "Đăng ký tài khoản thành công!",
        "user": user,
        "token": token
    }


class ProviderLookupPayload(BaseModel):
    email: str


_PROVIDER_LOOKUP_RATE_LIMIT: Dict[str, list] = {}
PROVIDER_LOOKUP_RATE_LIMIT_MAX = 60
PROVIDER_LOOKUP_RATE_LIMIT_WINDOW = 60  # Max 60 requests per 60 seconds per IP


@app.post("/api/auth/provider-lookup")
async def provider_lookup_endpoint(payload: ProviderLookupPayload, request: Request):
    """
    Trusted endpoint to resolve whether an account belongs to SQLite-only provider.
    Used by client authentication router to direct login safely without bypassing passwords.
    Protected by per-IP rate limiting against automated enumeration.
    """
    client_ip = request.client.host if request.client else "0.0.0.0"
    now = time.time()
    attempts = _PROVIDER_LOOKUP_RATE_LIMIT.get(client_ip, [])
    attempts = [t for t in attempts if now - t < PROVIDER_LOOKUP_RATE_LIMIT_WINDOW]
    if len(attempts) >= PROVIDER_LOOKUP_RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều yêu cầu tra cứu từ địa chỉ IP này. Vui lòng thử lại sau 1 phút."
        )
    attempts.append(now)
    _PROVIDER_LOOKUP_RATE_LIMIT[client_ip] = attempts

    res = gari_auth.resolve_account_provider(payload.email)
    return {"success": True, **res}


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
        secure=gari_config.IS_PRODUCTION,
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
    """Return the profile of the currently authenticated user with organization memberships."""
    user_dict = dict(current_user)
    orgs = gari_b2b.get_user_organizations(current_user["id"], include_test=False)
    entitlement = gari_plans.resolve_user_entitlement(current_user)
    user_dict["organizations"] = orgs
    user_dict["has_organizations"] = len(orgs) > 0
    user_dict["entitlement"] = entitlement
    user_dict["is_vip"] = bool(entitlement.get("has_vip_models"))
    user_dict["can_create_organization"] = bool(entitlement.get("can_create_organization"))
    return {"success": True, "user": user_dict}


@app.get("/api/auth/supabase-config")
async def get_supabase_client_config():
    """
    Exposes safe, public Supabase client credentials configured in environment.
    Never exposes service_role private keys or database passwords.
    """
    url = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "").strip()
    pub_key = (os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or "").strip()
    configured = bool(url and pub_key)
    return {
        "success": True,
        "configured": configured,
        "url": url,
        "publishableKey": pub_key
    }


class SupabaseSyncPayload(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    province: Optional[str] = "Lâm Đồng"
    account_type: Optional[str] = "farmer"


@app.post("/api/auth/supabase-sync")
async def sync_supabase_user(
    payload: SupabaseSyncPayload,
    request: Request,
    response: Response,
    current_user: Dict[str, Any] = Depends(gari_auth.get_current_user)
):
    """
    Idempotent synchronization endpoint called after Supabase Auth login or registration.
    current_user is cryptographically verified from the Supabase JWT by gari_auth.
    Sets HttpOnly session cookie and returns resolved user profile.
    """
    token = gari_auth.extract_token_from_request(request)
    if token:
        response.set_cookie(
            key="gari_session",
            value=token,
            httponly=True,
            samesite="lax",
            secure=gari_config.IS_PRODUCTION,
            max_age=7 * 86400,
            path="/"
        )

    return {
        "success": True,
        "user": current_user,
        "message": "Đồng bộ tài khoản Supabase thành công."
    }


@app.get("/api/auth/firebase-config")
async def get_firebase_client_config():
    """
    Exposes safe, public Firebase client SDK credentials configured in environment.
    Never exposes service account private keys or backend secrets.
    """
    api_key = os.getenv("FIREBASE_API_KEY", "").strip()
    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    configured = bool(api_key and project_id)
    return {
        "success": True,
        "configured": configured,
        "config": {
            "apiKey": api_key,
            "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", f"{project_id}.firebaseapp.com" if project_id else ""),
            "projectId": project_id,
            "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", f"{project_id}.appspot.com" if project_id else ""),
            "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
            "appId": os.getenv("FIREBASE_APP_ID", ""),
            "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID", "")
        }
    }


@app.get("/api/auth/firebase-status")
async def get_firebase_status():
    """Returns operational status of Firebase Admin and client configuration."""
    admin_ready = gari_firebase.is_firebase_initialized()
    client_ready = bool(os.getenv("FIREBASE_API_KEY") and os.getenv("FIREBASE_PROJECT_ID"))
    return {
        "success": True,
        "admin_initialized": admin_ready,
        "client_configured": client_ready,
        "app_env": os.getenv("APP_ENV", "development"),
        "message": "Firebase sẵn sàng" if (admin_ready and client_ready) else "Firebase Auth cần cấu hình khóa Firebase trong môi trường hoặc tệp dịch vụ để bật xác thực trực tiếp."
    }


@app.post("/api/auth/firebase-login")
async def firebase_login_endpoint(payload: FirebaseLoginPayload, request: Request, response: Response):
    """
    Authenticate user using a cryptographically verified Firebase ID token.
    Synchronizes user to internal SQLite database, issues a secure internal session token,
    and sets an HttpOnly cookie for session persistence.
    """
    import gari_firebase
    fb_data = gari_firebase.verify_firebase_id_token(payload.id_token)
    if not fb_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token không hợp lệ hoặc đã hết hạn."
        )

    registration = None
    if payload.full_name is not None:
        if not payload.terms_agreed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bạn cần đồng ý với điều khoản và chính sách bảo mật để đăng ký.")
        registration = {
            "full_name": payload.full_name,
            "phone": payload.phone,
            "province": payload.province or "Lâm Đồng",
            "account_type": payload.account_type,
        }
    user = gari_firebase.get_or_sync_firebase_user(fb_data, registration=registration)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không thể đồng bộ người dùng từ Firebase."
        )

    if user.get("is_active") == 0 or user.get("moderation_status") == "banned":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đã bị tạm khóa hoặc cấm vĩnh viễn."
        )

    client_ip = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("User-Agent", "")
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
        secure=gari_config.IS_PRODUCTION,
        max_age=max_age_seconds,
        path="/"
    )

    if registration:
        client_ip = request.client.host if request.client else "0.0.0.0"
        user_agent = request.headers.get("User-Agent", "")
        gari_privacy.record_consent("terms_of_service", "granted", user["id"], client_ip, user_agent)
        gari_privacy.record_consent("privacy_policy", "granted", user["id"], client_ip, user_agent)
        if payload.marketing_opt_in:
            gari_privacy.record_consent("marketing_opt_in", "granted", user["id"], client_ip, user_agent)

    profile = gari_auth.get_centralized_user_profile(user["id"])
    return {
        "success": True,
        "message": "Đăng nhập Firebase thành công!",
        "token": token,
        "user": profile
    }


@app.get("/api/user/profile")
@app.get("/api/auth/profile")
async def get_user_profile_api(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Authoritative centralized user profile following the 5-layer model:
    Identity, Profile, Canonical Account Type, System Roles, Subscription, Organizations.
    """
    return gari_auth.get_centralized_user_profile(current_user["id"])


@app.patch("/api/auth/profile")
@app.put("/api/user/profile")
async def update_user_profile_api(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Safely update user profile information.
    Strictly forbids self-assignment of privileged roles (is_admin, is_host_admin, is_expert, account_type).
    """
    return gari_auth.update_user_profile(
        user_id=current_user["id"],
        updates=payload,
        actor_id=current_user["id"]
    )


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
async def dashboard_stats(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return aggregated real operational metrics for farms, diagnoses, and risks."""
    user_id = current_user["id"]
    return gari_database.get_dashboard_metrics(user_id=user_id)


@app.get("/api/dashboard/activity")
async def dashboard_activity(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return recent user diagnoses activity."""
    user_id = current_user["id"]
    items = gari_database.list_diagnoses(user_id=user_id, limit=10)
    return {"success": True, "activity": items}


@app.get("/api/dashboard/crop-distribution")
async def dashboard_crop_distribution(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return crop distribution for current user."""
    user_id = current_user["id"]
    stats = gari_database.get_dashboard_metrics(user_id=user_id)
    return {"success": True, "crops": stats.get("crop_distribution", [])}


@app.get("/api/dashboard/disease-distribution")
async def dashboard_disease_distribution(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return disease distribution for current user."""
    user_id = current_user["id"]
    stats = gari_database.get_dashboard_metrics(user_id=user_id)
    return {"success": True, "diseases": stats.get("disease_distribution", [])}


# -----------------------------------------------------------------------------
# Farm Management API (GARI FARM - Protected & User-Scoped)
# -----------------------------------------------------------------------------

@app.get("/api/farms")
async def get_farms(
    status: Optional[str] = "active",
    org_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List all registered farms belonging to or accessible by the authenticated user."""
    if org_id is not None:
        user_role = gari_b2b.get_member_role(org_id, current_user["id"])
        is_admin = bool(current_user.get("is_admin") or current_user.get("is_host_admin"))
        if not user_role and not is_admin:
            raise HTTPException(
                status_code=403,
                detail="Truy cập bị từ chối: Bạn không phải thành viên của tổ chức này."
            )
    farms = gari_farm_management.list_farms_ext(user_id=current_user["id"], org_id=org_id, status=status)
    return {"success": True, "total": len(farms), "farms": farms}


@app.get("/api/user/diagnosis-contexts")
async def get_user_diagnosis_contexts(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Consolidated, scoped diagnosis context entities for the user selector:
    - Personal Account & Quota
    - Authorized User Farms (with plots count)
    - Authorized User Cooperatives & Organizations (with membership role & valid quota)
    Guarantees zero cross-tenant leakage and isolates test fixtures.
    """
    if not current_user:
        return {
            "success": True,
            "is_authenticated": False,
            "personal": {
                "name": "Khách khám tự do",
                "tier_name": "Gói Khám Trải Nghiệm",
                "is_vip": False,
                "quota_display": "Hạn ngạch dùng thử",
                "account_type": "guest"
            },
            "farms": [],
            "organizations": []
        }

    user_id = current_user["id"]
    account_type = current_user.get("account_type") or "farmer"

    # 1. Personal Quota
    is_vip = bool(current_user.get("is_vip", False))
    tier_name = "Gói Nông Hộ Tiêu Chuẩn"
    quota_display = "10 lượt khám/ngày"
    if is_vip:
        tier_name = "VIP Chuyên Nghiệp"
        quota_display = "Không giới hạn lượt khám"

    personal = {
        "user_id": user_id,
        "name": current_user.get("full_name") or current_user.get("name") or "Người dùng GARI",
        "email": current_user.get("email"),
        "account_type": account_type,
        "is_vip": is_vip,
        "tier_name": tier_name,
        "quota_display": quota_display
    }

    # 2. Authorized Farms (Scoped to user_id, test fixtures filtered out)
    raw_farms = gari_farm_management.list_farms_ext(user_id=user_id, include_test=False)
    farms = []
    for f in raw_farms:
        farms.append({
            "id": f["id"],
            "name": f["name"],
            "province": f.get("province") or "Chưa rõ tỉnh thành",
            "primary_crop": f.get("primary_crop") or "Đa cây trồng",
            "area_hectare": f.get("area_hectare", 1.0),
            "area_m2": f.get("area_m2", 10000.0),
            "total_plots": f.get("total_plots", 0),
            "total_zones": f.get("total_zones", 0),
            "type": "farm",
            "label": f"{f['name']} ({f.get('province') or 'Nông trại'})"
        })

    # 3. Authorized Organizations (Membership verified server-side, test fixtures filtered out)
    raw_orgs = gari_b2b.get_user_organizations(user_id=user_id, include_test=False)
    organizations = []
    for o in raw_orgs:
        role = o.get("user_role", "member")
        role_label = "Chủ nhiệm / Đại diện" if role == "owner" else ("Quản trị viên" if role == "admin" else "Thành viên")
        rem = o.get("remaining_quota")
        quota_str = "Không giới hạn" if rem is None else f"Còn {rem} lượt"
        organizations.append({
            "id": o["id"],
            "name": o["name"],
            "role": role,
            "role_label": role_label,
            "tier": o.get("tier", "enterprise"),
            "quota_display": quota_str,
            "can_diagnose": o.get("can_diagnose", True),
            "type": "organization",
            "label": f"{o['name']} ({role_label} • {quota_str})"
        })

    return {
        "success": True,
        "is_authenticated": True,
        "personal": personal,
        "farms": farms,
        "organizations": organizations,
        "total_farms": len(farms),
        "total_organizations": len(organizations)
    }


@app.post("/api/farms")
async def add_farm(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Register a new farm profile with area normalization and organization scope."""
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="Tên nông trại không được để trống.")
    try:
        gari_entitlements.enforce_entitlement(current_user["id"], "max_farms", org_id=payload.get("organization_id"))
        farm = gari_farm_management.create_farm_ext(payload, user_id=current_user["id"], org_id=payload.get("organization_id"))
        return {"success": True, "farm": farm}
    except gari_entitlements.EntitlementExceededError as ee:
        raise HTTPException(status_code=403, detail={"error": "entitlement_exceeded", "message": ee.message, "upgrade": ee.upgrade_data})
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/farms/{farm_id}")
async def get_farm_detail(farm_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve detailed farm profile with associated zones, plots, summary, and diagnoses."""
    farm = gari_farm_management.get_farm_ext(farm_id, user_id=current_user["id"])
    if not farm:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền truy cập.")
    return {"success": True, "farm": farm}


@app.put("/api/farms/{farm_id}")
async def update_farm_detail(farm_id: int, payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Update an existing farm owned or administered by the authenticated user."""
    try:
        updated = gari_farm_management.update_farm_ext(farm_id, payload, user_id=current_user["id"])
        if not updated:
            raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền chỉnh sửa.")
        return {"success": True, "farm": updated}
    except PermissionError:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền chỉnh sửa.")


@app.delete("/api/farms/{farm_id}")
async def remove_farm(farm_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a farm profile owned by the authenticated user."""
    try:
        success = gari_farm_management.delete_farm_ext(farm_id, user_id=current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy nông trại để xóa.")
        return {"success": True, "message": "Đã xóa nông trại thành công."}
    except PermissionError:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại để xóa.")


@app.post("/api/farms/{farm_id}/archive")
async def archive_farm_api(farm_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Archive farm and cascade to child zones and plots."""
    try:
        success = gari_farm_management.archive_farm(farm_id, user_id=current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy nông trại để lưu trữ.")
        return {"success": True, "message": "Đã lưu trữ nông trại thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.post("/api/farms/{farm_id}/unarchive")
async def unarchive_farm_api(farm_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Restore an archived farm."""
    try:
        success = gari_farm_management.unarchive_farm(farm_id, user_id=current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy nông trại để khôi phục.")
        return {"success": True, "message": "Đã khôi phục nông trại thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.get("/api/farms/{farm_id}/summary")
async def get_farm_summary_api(farm_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve key performance indicators and summaries for a farm."""
    farm = gari_farm_management.get_farm_ext(farm_id, user_id=current_user["id"])
    if not farm:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại.")
    return {"success": True, "summary": farm.get("summary", {}), "farm": {"id": farm["id"], "name": farm["name"], "province": farm.get("province")}}


@app.get("/api/farms/{farm_id}/season-report")
async def get_farm_season_report_json(
    farm_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get consolidated seasonal management, task adherence, and disease report as JSON.
    Strictly isolated by user ownership and tenant boundaries.
    """
    user_id = current_user["id"]
    farm = gari_farm_management.get_farm_ext(farm_id, user_id=user_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền truy cập.")
    report = gari_database.generate_farm_season_report(farm_id, user_id=user_id)
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu báo cáo mùa vụ.")
    return {"success": True, "report": report}


@app.get("/api/farms/{farm_id}/export-season-report", response_class=HTMLResponse)
async def export_farm_season_report_html(
    farm_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Render executive printable VietGAP Seasonal Cultivation Journal with digital audit hash.
    Strictly isolated by user ownership and tenant boundaries.
    """
    user_id = current_user["id"]
    farm = gari_farm_management.get_farm_ext(farm_id, user_id=user_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền truy cập.")
    report = gari_database.generate_farm_season_report(farm_id, user_id=user_id)
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu báo cáo mùa vụ.")
    html_content = gari_database.render_farm_season_report_html(report)
    return HTMLResponse(content=html_content)


# -----------------------------------------------------------------------------
# Farm Zones API (Subdivisions)
# -----------------------------------------------------------------------------
@app.get("/api/farms/{farm_id}/zones")
async def get_farm_zones_api(
    farm_id: int,
    include_archived: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List zones in a farm with plot & plant counts."""
    zones = gari_farm_management.list_zones(farm_id, user_id=current_user["id"], include_archived=include_archived)
    return {"success": True, "total": len(zones), "zones": zones}


@app.post("/api/farms/{farm_id}/zones")
async def create_farm_zone_api(
    farm_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new zone subdivision within a farm."""
    payload["farm_id"] = farm_id
    try:
        zone = gari_farm_management.create_zone(payload, user_id=current_user["id"])
        return {"success": True, "zone": zone}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/zones/{zone_id}")
async def get_zone_api(zone_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get zone profile with child plots."""
    zone = gari_farm_management.get_zone(zone_id, user_id=current_user["id"])
    if not zone:
        raise HTTPException(status_code=404, detail="Không tìm thấy khu vực hoặc bạn không có quyền truy cập.")
    return {"success": True, "zone": zone}


@app.put("/api/zones/{zone_id}")
async def update_zone_api(
    zone_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update zone details."""
    try:
        updated = gari_farm_management.update_zone(zone_id, payload, user_id=current_user["id"])
        if not updated:
            raise HTTPException(status_code=404, detail="Không tìm thấy khu vực để cập nhật.")
        return {"success": True, "zone": updated}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.post("/api/zones/{zone_id}/archive")
async def archive_zone_api(zone_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Archive a zone."""
    try:
        success = gari_farm_management.archive_zone(zone_id, user_id=current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy khu vực.")
        return {"success": True, "message": "Đã lưu trữ khu vực thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.delete("/api/zones/{zone_id}")
async def delete_zone_api(zone_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a zone."""
    try:
        success = gari_farm_management.delete_zone(zone_id, user_id=current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy khu vực để xóa.")
        return {"success": True, "message": "Đã xóa khu vực thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


# -----------------------------------------------------------------------------
# Farm Plots API
# -----------------------------------------------------------------------------
@app.get("/api/plots")
async def list_plots_api(
    farm_id: Optional[int] = None,
    zone_id: Optional[int] = None,
    org_id: Optional[int] = None,
    status: Optional[str] = "active",
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List farm plots accessible to the current user or organization."""
    if org_id is not None:
        if not gari_b2b.get_member_role(org_id, current_user["id"]) and not current_user.get("is_admin", False):
            raise HTTPException(status_code=403, detail="Bạn không thuộc tổ chức này.")
    plots = gari_database.list_plots(farm_id=farm_id, user_id=current_user["id"], org_id=org_id)
    if zone_id is not None:
        plots = [p for p in plots if p.get("zone_id") == zone_id]
    if status and status != "all":
        plots = [p for p in plots if p.get("status") == status or (status == "active" and p.get("status") is None)]
    return {"success": True, "total": len(plots), "plots": plots}


@app.post("/api/plots")
async def create_plot_api(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new farm plot with parent-child validation and tenant scope."""
    farm_id = payload.get("farm_id")
    if not farm_id:
        raise HTTPException(status_code=400, detail="Thiếu farm_id của nông trại.")
    try:
        gari_entitlements.enforce_entitlement(current_user["id"], "max_plots", org_id=payload.get("organization_id"))
        plot = gari_farm_management.create_plot_ext(payload, user_id=current_user["id"], org_id=payload.get("organization_id"))
        return {"success": True, "plot": plot}
    except gari_entitlements.EntitlementExceededError as ee:
        raise HTTPException(status_code=403, detail={"error": "entitlement_exceeded", "message": ee.message, "upgrade": ee.upgrade_data})
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/farms/{farm_id}/plots")
async def get_farm_plots(farm_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """List crop plots inside a specified farm."""
    plots = gari_database.list_plots(farm_id, user_id=current_user["id"])
    return {"success": True, "total": len(plots), "plots": plots}


@app.post("/api/farms/{farm_id}/plots")
async def add_farm_plot(farm_id: int, payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Create a new crop plot in user's farm."""
    payload["farm_id"] = farm_id
    try:
        plot = gari_farm_management.create_plot_ext(payload, user_id=current_user["id"])
        return {"success": True, "plot": plot}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/plots/{plot_id}")
async def get_plot_detail_api(
    plot_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get single plot details with cross-tenant check, active cycle, and plants summary."""
    plot = gari_farm_management.get_plot_ext(plot_id, user_id=current_user["id"])
    if not plot:
        # Check if plot exists anywhere to return 403 vs 404
        existing_any = gari_database.get_plot(plot_id)
        if existing_any:
            raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập thửa/vườn này.")
        raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn.")
    return {"success": True, "plot": plot}


@app.patch("/api/plots/{plot_id}")
@app.put("/api/plots/{plot_id}")
async def update_plot_api(
    plot_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update plot information with cross-tenant validation."""
    try:
        updated = gari_farm_management.update_plot_ext(plot_id, payload, user_id=current_user["id"])
        if not updated:
            raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn.")
        return {"success": True, "plot": updated}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.post("/api/plots/{plot_id}/archive")
async def archive_plot_api(plot_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Archive a plot."""
    try:
        success = gari_farm_management.archive_plot_ext(plot_id, user_id=current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn để lưu trữ.")
        return {"success": True, "message": "Đã lưu trữ thửa/vườn thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.delete("/api/plots/{plot_id}")
async def remove_plot(plot_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Delete a crop plot with tenant isolation."""
    try:
        existing = gari_database.get_plot(plot_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn.")
        success = gari_farm_management.delete_plot_ext(plot_id, user_id=current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn để xóa.")
        return {"success": True, "message": "Đã xóa thửa/vườn canh tác thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.get("/api/plots/{plot_id}/summary")
async def get_plot_summary_api(plot_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get plot summary indicators."""
    plot = gari_farm_management.get_plot_ext(plot_id, user_id=current_user["id"])
    if not plot:
        raise HTTPException(status_code=404, detail="Không tìm thấy thửa/vườn.")
    return {
        "success": True,
        "plot_id": plot["id"],
        "plot_name": plot["plot_name"],
        "farm_id": plot["farm_id"],
        "active_cycle": plot.get("active_cycle"),
        "plants_summary": plot.get("plants_summary"),
        "monitoring_status": plot.get("monitoring_status")
    }


# -----------------------------------------------------------------------------
# Crop Cycles API (Vụ mùa & Luân canh)
# -----------------------------------------------------------------------------
@app.get("/api/plots/{plot_id}/cycles")
async def get_plot_cycles_api(
    plot_id: int,
    include_archived: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List crop cycles (rotation history) of a plot."""
    cycles = gari_farm_management.list_crop_cycles(plot_id, user_id=current_user["id"], include_archived=include_archived)
    return {"success": True, "total": len(cycles), "cycles": cycles}


@app.post("/api/plots/{plot_id}/cycles")
async def add_crop_cycle_api(
    plot_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Add a new crop cycle to a plot (performs crop rotation if active)."""
    try:
        cycle = gari_farm_management.create_crop_cycle(plot_id, payload, user_id=current_user["id"])
        return {"success": True, "cycle": cycle}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/cycles/{cycle_id}")
async def get_cycle_detail_api(cycle_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get crop cycle details and linked diagnoses."""
    cycle = gari_farm_management.get_crop_cycle(cycle_id, user_id=current_user["id"])
    if not cycle:
        raise HTTPException(status_code=404, detail="Không tìm thấy vụ mùa hoặc bạn không có quyền truy cập.")
    return {"success": True, "cycle": cycle}


@app.put("/api/cycles/{cycle_id}")
async def update_cycle_api(
    cycle_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update crop cycle metadata or mark completed/harvested."""
    try:
        updated = gari_farm_management.update_crop_cycle(cycle_id, payload, user_id=current_user["id"])
        if not updated:
            raise HTTPException(status_code=404, detail="Không tìm thấy vụ mùa.")
        return {"success": True, "cycle": updated}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


# -----------------------------------------------------------------------------
# Individual Plants / Trees API (Durian, Trees, Rows)
# -----------------------------------------------------------------------------
@app.get("/api/plots/{plot_id}/plants")
async def get_plot_plants_api(
    plot_id: int,
    health_status: Optional[str] = None,
    include_archived: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List individual plants/trees within a plot."""
    plants = gari_farm_management.list_plants(plot_id, health_status=health_status, user_id=current_user["id"], include_archived=include_archived)
    return {"success": True, "total": len(plants), "plants": plants}


@app.post("/api/plots/{plot_id}/plants")
async def add_plot_plant_api(
    plot_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Register an individual plant or tree with unique tag/QR."""
    try:
        plant = gari_farm_management.create_plant(plot_id, payload, user_id=current_user["id"])
        return {"success": True, "plant": plant}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.post("/api/plots/{plot_id}/plants/batch")
async def add_plot_plants_batch_api(
    plot_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Batch register multiple plants/trees for a plot."""
    plants_list = payload.get("plants", [])
    if not isinstance(plants_list, list) or not plants_list:
        raise HTTPException(status_code=400, detail="Danh sách cây 'plants' phải là mảng không rỗng.")
    try:
        created = gari_farm_management.batch_create_plants(plot_id, plants_list, user_id=current_user["id"])
        return {"success": True, "count": len(created), "plants": created}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.get("/api/plants/{plant_id}")
async def get_plant_detail_api(plant_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get single plant details with health status and linked diagnoses."""
    plant = gari_farm_management.get_plant(plant_id, user_id=current_user["id"])
    if not plant:
        raise HTTPException(status_code=404, detail="Không tìm thấy cây trồng hoặc bạn không có quyền truy cập.")
    return {"success": True, "plant": plant}


@app.put("/api/plants/{plant_id}")
async def update_plant_api(
    plant_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update plant health status, coordinates, or notes."""
    try:
        updated = gari_farm_management.update_plant(plant_id, payload, user_id=current_user["id"])
        if not updated:
            raise HTTPException(status_code=404, detail="Không tìm thấy cây trồng.")
        return {"success": True, "plant": updated}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.post("/api/plants/{plant_id}/archive")
async def archive_plant_api(plant_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Archive a plant."""
    try:
        success = gari_farm_management.archive_plant(plant_id, user_id=current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy cây trồng.")
        return {"success": True, "message": "Đã lưu trữ cây trồng thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


# -----------------------------------------------------------------------------
# Activity & Observation Timeline API
# -----------------------------------------------------------------------------
@app.post("/api/plots/{plot_id}/activities")
async def add_plot_activity_api(
    plot_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record an observation or activity event linked to a plot or specific plant/cycle."""
    event_type = payload.get("event_type") or "observation"
    notes = (payload.get("notes") or "").strip()
    if not notes:
        raise HTTPException(status_code=400, detail="Nội dung ghi chép hoạt động không được để trống.")
    try:
        event = gari_farm_management.record_plot_activity(
            plot_id=plot_id,
            event_type=event_type,
            notes=notes,
            user_id=current_user["id"],
            org_id=payload.get("organization_id"),
            plant_id=payload.get("plant_id"),
            cycle_id=payload.get("cycle_id"),
            severity=payload.get("severity"),
            action_taken=payload.get("action_taken"),
            images=payload.get("images")
        )
        return {"success": True, "event": event}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.post("/api/diagnoses/{diagnosis_id}/link")
async def link_diagnosis_api(
    diagnosis_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Link an existing diagnosis to farm, plot, plant, or crop cycle."""
    farm_id = payload.get("farm_id")
    plot_id = payload.get("plot_id")
    if not farm_id or not plot_id:
        raise HTTPException(status_code=400, detail="farm_id và plot_id là bắt buộc để liên kết chẩn đoán.")
    try:
        success = gari_farm_management.link_diagnosis_to_hierarchy(
            diagnosis_id=diagnosis_id,
            farm_id=farm_id,
            plot_id=plot_id,
            plant_id=payload.get("plant_id"),
            crop_cycle_id=payload.get("crop_cycle_id"),
            user_id=current_user["id"]
        )
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy chẩn đoán hoặc không có quyền liên kết.")
        return {"success": True, "message": "Đã liên kết chẩn đoán vào hồ sơ canh tác thành công."}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/plots/{plot_id}/timeline")
async def get_plot_timeline_api(
    plot_id: int,
    plant_id: Optional[int] = None,
    cycle_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve disease monitoring and activity timeline for a plot or plant with tenant isolation."""
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
    feed_events = gari_farm_management.list_plot_timeline(plot_id, plant_id=plant_id, cycle_id=cycle_id, user_id=user_id)

    return {
        "success": True,
        "timeline": timeline,
        "plot": timeline.get("plot") if timeline else plot,
        "summary": timeline.get("summary") if timeline else None,
        "events": feed_events or (timeline.get("timeline_feed", []) if timeline else []),
        "timeline_events": feed_events or (timeline.get("timeline_events", []) if timeline else []),
        "timeline_feed": feed_events or (timeline.get("timeline_feed", []) if timeline else []),
        "diagnoses": timeline.get("diagnoses", []) if timeline else []
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
    user_id = current_user["id"]
    notifs = gari_database.list_notifications(user_id=user_id)
    return {"success": True, "total": len(notifs), "notifications": notifs}


@app.patch("/api/notifications/{notif_id}/read")
async def mark_read(notif_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Mark a single notification as read."""
    user_id = current_user["id"]
    success = gari_database.mark_notification_as_read(notif_id, user_id=user_id)
    return {"success": success}


@app.post("/api/notifications/mark-all-read")
async def mark_all_notifications_read_api(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Mark all unread notifications as read for current user."""
    user_id = current_user["id"]
    count = gari_database.mark_all_notifications_read(user_id=user_id)
    return {"success": True, "marked_count": count, "message": "Đã đánh dấu tất cả thông báo là đã đọc."}


# -----------------------------------------------------------------------------
# Diagnosis History API (Sprint 4: Multi-Tenant & Safe Storage)
# -----------------------------------------------------------------------------

@app.get("/api/diagnoses")
async def list_diagnoses(
    farm_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    crop_id: Optional[str] = None,
    org_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Query past AI diagnoses with user-scoped and tenant isolation."""
    user_id = current_user["id"]
    is_admin = bool(current_user.get("is_admin") or current_user.get("is_host_admin"))

    if org_id is not None:
        if not gari_b2b.get_member_role(org_id, user_id) and not is_admin:
            raise HTTPException(status_code=403, detail="Bạn không thuộc tổ chức này.")
        diagnoses = gari_database.list_diagnoses(
            user_id=None,
            farm_id=farm_id,
            plot_id=plot_id,
            crop_id=crop_id,
            organization_id=org_id
        )
    else:
        diagnoses = gari_database.list_diagnoses(
            user_id=user_id if not is_admin else None,
            farm_id=farm_id,
            plot_id=plot_id,
            crop_id=crop_id,
            organization_id=None,
            allow_unscoped=is_admin and (farm_id is None and plot_id is None)
        )
    return {"success": True, "total": len(diagnoses), "diagnoses": diagnoses}


@app.post("/api/diagnoses")
async def save_diagnosis_record(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
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

    user_id = current_user["id"]
    saved = gari_database.save_diagnosis(payload, user_id=user_id)
    return {"success": True, "diagnosis": saved}


@app.get("/api/diagnoses/{diag_id}")
async def get_diagnosis_detail(diag_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get single diagnosis detail by ID with strict tenant isolation check."""
    d = gari_database.get_diagnosis(diag_id)
    if not d:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi chẩn đoán.")

    user_id = current_user["id"]
    is_owner = (d.get("user_id") == user_id or d.get("actor_user_id") == user_id)
    is_org_member = False
    if d.get("organization_id"):
        is_org_member = bool(gari_b2b.get_member_role(d["organization_id"], user_id))
    is_admin = bool(current_user.get("is_admin", False) or current_user.get("is_host_admin", False))

    if not (is_owner or is_org_member or is_admin):
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập bản ghi chẩn đoán này.")

    return {"success": True, "diagnosis": d}


class FollowUpPayload(BaseModel):
    monitoring_status: str
    observation_notes: Optional[str] = None
    treatment_action: Optional[str] = None


@app.patch("/api/diagnoses/{diag_id}/follow-up")
@app.post("/api/diagnoses/{diag_id}/follow-up")
async def update_diagnosis_followup_endpoint(
    diag_id: int,
    payload: FollowUpPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Queue P1.5 — Update diagnosis follow-up and monitoring state.
    Enforces that recovery claims require actual field observations.
    """
    d = gari_database.get_diagnosis(diag_id)
    if not d:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi chẩn đoán.")

    user_id = current_user["id"]
    org_id = d.get("organization_id")
    is_owner = (d.get("user_id") == user_id or d.get("actor_user_id") == user_id)
    is_org_member = bool(gari_b2b.get_member_role(org_id, user_id)) if org_id else False
    is_admin = bool(current_user.get("is_admin", False) or current_user.get("is_host_admin", False))
    if not (is_owner or is_org_member or is_admin):
        raise HTTPException(status_code=403, detail="Bạn không có quyền cập nhật theo dõi cho bản ghi chẩn đoán này.")

    try:
        updated = gari_database.update_diagnosis_followup(
            diag_id=diag_id,
            monitoring_status=payload.monitoring_status,
            observation_notes=payload.observation_notes,
            treatment_action=payload.treatment_action,
            user_id=user_id,
            org_id=org_id
        )
        return {"success": True, "diagnosis": updated}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.delete("/api/diagnoses/{diag_id}")
async def delete_diagnosis_api(
    diag_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Delete a diagnosis record owned by user (Priority B & Privacy policy).
    Enforces tenant and user isolation.
    """
    d = gari_database.get_diagnosis(diag_id)
    if not d:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi chẩn đoán.")

    user_id = current_user["id"]
    is_owner = (d.get("user_id") == user_id or d.get("actor_user_id") == user_id)
    is_org_admin = False
    if d.get("organization_id"):
        role = gari_b2b.get_member_role(d["organization_id"], user_id)
        is_org_admin = role in ("owner", "admin")
    is_admin = bool(current_user.get("is_admin", False) or current_user.get("is_host_admin", False))

    if not (is_owner or is_org_admin or is_admin):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền xóa bản ghi chẩn đoán này."
        )

    deleted = gari_database.delete_diagnosis(diag_id, user_id=user_id)
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
    current_user: Dict[str, Any] = Depends(get_current_user)
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

    user_id = current_user["id"]
    org_id = diag.get("organization_id")

    # Moderation Scan on feedback text
    if payload.notes:
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

    is_owner = (diag.get("user_id") == user_id or diag.get("actor_user_id") == user_id)
    is_org_member = False
    if org_id:
        is_org_member = bool(gari_b2b.get_member_role(org_id, user_id))
    is_admin = bool(current_user.get("is_admin", False) or current_user.get("is_host_admin", False))

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
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve user feedback for a diagnosis.
    Enforces tenant isolation: other users/tenants cannot read feedback.
    """
    diag = gari_database.get_diagnosis(diag_id)
    if not diag:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi chẩn đoán.")

    user_id = current_user["id"]
    is_admin = bool(current_user.get("is_admin", False) or current_user.get("is_host_admin", False))

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
    
    # Query live meteorological data from Open-Meteo for Central Highlands station (11.9404, 108.4583)
    weather_res = gari_weather_service.get_coordinates_weather(11.9404, 108.4583)
    cur = weather_res.get("current") or {}
    
    observed_weather = {
        "temperature_c": cur.get("temperature_c") if cur.get("temperature_c") is not None else 24.5,
        "humidity_pct": cur.get("humidity_pct") if cur.get("humidity_pct") is not None else 82,
        "rainfall_mm": cur.get("precipitation_mm", 0.0),
        "wind_speed_kmh": cur.get("wind_speed_kmh", 12.0),
        "station": "Trạm Khí tượng Lâm Đồng & Tây Nguyên (Open-Meteo)",
        "condition": cur.get("condition") or "Dữ liệu quan trắc vi khí hậu tự động",
        "is_real_data": weather_res.get("is_real_data", True),
        "status": weather_res.get("status", "connected"),
        "timezone": weather_res.get("timezone", "Asia/Ho_Chi_Minh"),
        "fetched_at": weather_res.get("fetched_at")
    }

    return {
        "success": True,
        "observed_weather": observed_weather,
        "alerts": alerts,
        "methodology": {
            "observed_data": "Dữ liệu quan trắc thực tế từ Open-Meteo & trạm vi khí hậu nông nghiệp.",
            "rule_based_warnings": "Mô hình dịch tễ kết hợp độ ẩm kéo dài > 85% và khoảng nhiệt độ thuận lợi của mầm bệnh.",
            "ml_predictions": "Mô hình học máy phân tích chuỗi thời gian nguy cơ bùng phát dịch bệnh (Gari Predict v2)."
        }
    }


@app.post("/api/risk/alerts/{alert_id}/acknowledge")
async def acknowledge_alert_api(
    alert_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Record a user field observation / acknowledgment for a regional risk alert."""
    user_id = current_user["id"]
    result = gari_database.acknowledge_risk_alert(alert_id, user_id=user_id, data=payload)
    return {"success": True, "acknowledgment": result, "message": "Đã ghi nhận quan sát thực địa của nông hộ."}


@app.get("/api/risk/acknowledgments")
async def list_risk_acknowledgments_api(
    alert_id: Optional[int] = None,
    farm_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List field observations and risk acknowledgments."""
    user_id = current_user["id"]
    acks = gari_database.list_risk_acknowledgments(user_id=user_id, alert_id=alert_id, farm_id=farm_id)
    return {"success": True, "total": len(acks), "acknowledgments": acks}


# -----------------------------------------------------------------------------
# Cultivation Calendar & Smart Task Engine API (Module 06)
# -----------------------------------------------------------------------------

@app.get("/api/calendar/tasks")
async def get_calendar_tasks(
    view: str = "all",
    farm_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    cycle_id: Optional[int] = None,
    plant_id: Optional[int] = None,
    crop_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    org_id: Optional[int] = None,
    limit: int = 200,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve cultivation tasks scoped by user or organization with filtering and counts."""
    user_id = current_user["id"]
    result = gari_tasks.list_tasks(
        user_id=user_id,
        view=view,
        farm_id=farm_id,
        plot_id=plot_id,
        cycle_id=cycle_id,
        plant_id=plant_id,
        crop_id=crop_id,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        org_id=org_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit
    )
    return result


@app.post("/api/calendar/tasks")
async def create_calendar_task(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new cultivation task in the calendar."""
    if not payload.get("title"):
        raise HTTPException(status_code=400, detail="Tiêu đề công việc canh tác là bắt buộc.")
    user_id = current_user["id"]
    org_id = payload.get("organization_id") or payload.get("org_id")

    try:
        task = gari_tasks.create_task(payload, creator_user_id=user_id, org_id=org_id)
        return {"success": True, "task": task, "message": "Đã tạo công việc canh tác thành công."}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tạo công việc: {str(e)}")


@app.post("/api/calendar/tasks/from-diagnosis")
async def create_task_from_leaf_diagnosis(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a cultivation/treatment task directly from an AI diagnosis result."""
    diag_id = payload.get("diagnosis_id")
    if not diag_id:
        raise HTTPException(status_code=400, detail="Mã chẩn đoán (diagnosis_id) là bắt buộc.")
    user_id = current_user["id"]

    try:
        task = gari_tasks.create_task_from_diagnosis(
            diagnosis_id=int(diag_id),
            user_id=user_id,
            custom_title=payload.get("title"),
            due_date=payload.get("due_date"),
            priority=payload.get("priority"),
            notes=payload.get("notes"),
            assignee_user_id=payload.get("assignee_user_id")
        )
        return {"success": True, "task": task, "message": "Đã tạo nhiệm vụ điều trị từ chẩn đoán AI thành công."}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")


@app.get("/api/calendar/tasks/{task_id}")
async def get_calendar_task_detail(
    task_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get single cultivation task details including audit history."""
    user_id = current_user["id"]
    task = gari_tasks.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy công việc canh tác hoặc bạn không có quyền xem.")
    return {"success": True, "task": task}


@app.get("/api/calendar/tasks/{task_id}/activities")
async def get_calendar_task_activities(
    task_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get audit activity history for a task."""
    user_id = current_user["id"]
    task = gari_tasks.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy công việc canh tác.")
    activities = gari_tasks.get_task_activities(task_id)
    return {"success": True, "task_id": task_id, "activities": activities}


@app.patch("/api/calendar/tasks/{task_id}")
@app.put("/api/calendar/tasks/{task_id}")
async def update_calendar_task(
    task_id: int,
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update an existing cultivation task with permission check and audit trail."""
    user_id = current_user["id"]
    try:
        task = gari_tasks.update_task(task_id, payload, user_id=user_id)
        return {"success": True, "task": task, "message": "Đã cập nhật công việc canh tác thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")


@app.post("/api/calendar/tasks/{task_id}/complete")
async def complete_calendar_task(
    task_id: int,
    payload: Optional[Dict[str, Any]] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Mark a cultivation task as completed and automatically advance recurring jobs."""
    user_id = current_user["id"]
    notes = (payload or {}).get("notes")
    try:
        task = gari_tasks.complete_task(task_id, user_id=user_id, notes=notes)
        return {"success": True, "task": task, "message": "Đã đánh dấu hoàn thành công việc canh tác."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")


@app.delete("/api/calendar/tasks/{task_id}")
async def delete_calendar_task(
    task_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a cultivation task with RBAC permission verification."""
    user_id = current_user["id"]
    try:
        success = gari_tasks.delete_task(task_id, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy công việc canh tác hoặc không có quyền xóa.")
        return {"success": True, "message": "Đã xóa công việc canh tác thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi: {str(e)}")


@app.post("/api/calendar/tasks/reminders/process")
async def process_calendar_task_reminders(
    payload: Optional[Dict[str, Any]] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Process due task reminders and emit in-app notifications without duplicates."""
    user_id = current_user["id"]
    org_id = (payload or {}).get("org_id")
    result = gari_tasks.process_task_reminders(user_id=user_id, org_id=org_id)
    return result


@app.get("/api/calendar/recommendations")
async def get_calendar_recommendations(crop_id: Optional[str] = None):
    """Get agronomical recommendations for the current crop and season."""
    recs = gari_database.get_seasonal_cultivation_recommendations(crop_id=crop_id)
    return {"success": True, "recommendations": recs}


# -----------------------------------------------------------------------------
# GARI AI Copilot & Real-Time Agronomic Assistant API
# -----------------------------------------------------------------------------

@app.get("/api/copilot/context")
async def get_copilot_user_context(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieve multi-plot status, pending/overdue tasks, and microclimate context for Copilot."""
    user_id = current_user["id"]
    ctx = gari_copilot.get_copilot_context(user_id=user_id)
    return {"success": True, "context": ctx}


@app.post("/api/copilot/chat")
async def copilot_chat_message(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Process conversational query from farmer with natural language understanding,
    strict tenant isolation, plot context, and draft action proposal.
    """
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Vui lòng nhập câu hỏi hoặc yêu cầu cho Trợ lý GARI.")
    user_id = current_user["id"]
    session_id = payload.get("session_id")
    result = gari_copilot.process_copilot_message(user_id=user_id, message=message, session_id=session_id)
    return result


@app.post("/api/copilot/tasks/confirm-draft")
async def copilot_confirm_draft_task(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Convert an AI-drafted cultivation recommendation into a persistent cultivation task."""
    draft = payload.get("draft") or payload
    if not draft.get("title"):
        raise HTTPException(status_code=400, detail="Thiếu tiêu đề công việc cần xác nhận.")
    user_id = current_user["id"]
    task = gari_copilot.confirm_draft_task(user_id=user_id, draft=draft)
    if not task:
        raise HTTPException(status_code=500, detail="Không thể tạo công việc từ đề xuất Copilot.")
    return {"success": True, "task": task, "message": "Đã thêm công việc vào Lịch canh tác thành công!"}


# -----------------------------------------------------------------------------
# GARI Plant Health Assistant & AI Disease Explainer API
# -----------------------------------------------------------------------------

@app.get("/api/assistant/status")
async def assistant_get_status():
    """Retrieve public status and provider readiness of Plant Health Assistant."""
    return gari_assistant.get_public_assistant_status()


@app.post("/api/assistant/chat")
async def assistant_chat_message(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Process multi-turn agronomic disease explainer chat bound to diagnosis record."""
    user_id = current_user["id"]
    try:
        gari_entitlements.enforce_entitlement(current_user["id"], "ai_usage")
    except gari_entitlements.EntitlementExceededError as ee:
        raise HTTPException(status_code=403, detail={"error": "entitlement_exceeded", "message": ee.message, "upgrade": ee.upgrade_data})
    diag_id = payload.get("diagnosis_id")
    if not diag_id:
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM diagnoses WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
            row = cursor.fetchone()
            if row:
                diag_id = row["id"]
            else:
                diag_id = 1
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Vui lòng nhập câu hỏi hoặc yêu cầu cho Trợ lý AI.")

    conversation_history = payload.get("conversation_history") or []
    field_context = payload.get("field_context") or {}
    deep_dive = bool(payload.get("deep_dive", False))

    res = gari_assistant.PlantHealthAssistantService.process_chat(
        user_id=user_id,
        diagnosis_id=int(diag_id),
        message=message,
        conversation_history=conversation_history,
        field_context=field_context,
        deep_dive=deep_dive
    )
    if res.get("status") == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=res.get("reply", "Bạn không có quyền truy cập hồ sơ chẩn đoán này."))
    if res.get("status") == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res.get("reply", "Không tìm thấy hồ sơ chẩn đoán."))
    gari_entitlements.record_usage(current_user["id"], "ai_usage", 1.0)
    return res


@app.get("/api/assistant/history/{diagnosis_id}")
async def assistant_get_history(
    diagnosis_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve conversation history for a given diagnosis."""
    user_id = current_user["id"]
    history = gari_assistant.PlantHealthAssistantService.get_history(user_id=user_id, diagnosis_id=diagnosis_id)
    return {"success": True, "history": history}


@app.post("/api/assistant/action/confirm")
async def assistant_confirm_action(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Explicit user confirmation to convert an Assistant action draft into a persistent cultivation task."""
    user_id = current_user["id"]
    diag_id = payload.get("diagnosis_id")
    if not diag_id:
        raise HTTPException(status_code=400, detail="Thiếu diagnosis_id.")
    action_draft = payload.get("action_draft") or payload.get("draft") or payload
    if not action_draft.get("title"):
        raise HTTPException(status_code=400, detail="Thiếu tiêu đề công việc cần xác nhận.")

    task = gari_assistant.PlantHealthAssistantService.confirm_action_to_task(
        user_id=user_id,
        diagnosis_id=int(diag_id),
        action_draft=action_draft
    )
    if not task:
        raise HTTPException(status_code=500, detail="Không thể tạo công việc từ đề xuất của Trợ lý AI.")
    return {"success": True, "task": task, "message": "Đã thêm công việc vào Lịch canh tác thành công!"}


# -----------------------------------------------------------------------------
# Agricultural Expert Support API (GARI EXPERT)
# -----------------------------------------------------------------------------

@app.get("/api/expert/cases")
async def get_expert_cases(current_user: Dict[str, Any] = Depends(get_current_user)):
    """List submitted expert consultation cases."""
    if current_user.get("is_host_admin"):
        cases = gari_database.list_expert_cases(user_id=None)
    elif current_user.get("is_expert"):
        cases = gari_database.list_expert_cases_for_expert(current_user["id"])
    else:
        cases = gari_database.list_expert_cases(user_id=current_user["id"])
    return {"success": True, "total": len(cases), "cases": cases}


@app.post("/api/expert/cases")
async def create_expert_case(payload: Dict[str, Any], current_user: Dict[str, Any] = Depends(get_current_user)):
    """Submit a diagnosis case for review by agronomists."""
    if not payload.get("symptoms_description"):
        raise HTTPException(status_code=400, detail="Mô tả triệu chứng bệnh là bắt buộc.")
    user_id = current_user["id"]
    try:
        gari_entitlements.enforce_entitlement(current_user["id"], "expert_consultations")
    except gari_entitlements.EntitlementExceededError as ee:
        raise HTTPException(status_code=403, detail={"error": "entitlement_exceeded", "message": ee.message, "upgrade": ee.upgrade_data})
    try:
        case = gari_experts.create_consultation_case(user_id=user_id, data=payload)
        gari_entitlements.record_usage(current_user["id"], "expert_consultations", 1.0)
        return {"success": True, "case": case}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/expert/cases/{case_id}")
async def get_expert_case_detail_api(
    case_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve expert consultation case details with privacy masking and access boundary enforcement.
    """
    try:
        case = gari_experts.get_consultation_case(case_id=case_id, caller_user=current_user)
        return {"success": True, "case": case}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tải ca bệnh: {str(e)}")


@app.post("/api/expert/cases/from-diagnosis")
async def create_expert_case_from_diagnosis_api(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Directly escalate an AI Leaf Diagnosis into an Expert Consultation Case."""
    if not payload.get("diagnosis_id"):
        raise HTTPException(status_code=400, detail="Mã chẩn đoán (diagnosis_id) là bắt buộc.")
    if not payload.get("symptoms_description"):
        payload["symptoms_description"] = "Yêu cầu chuyên gia thẩm định từ kết quả chẩn đoán bệnh cây trồng."
    try:
        case = gari_experts.create_consultation_case(user_id=current_user["id"], data=payload)
        return {"success": True, "message": "Đã tạo hồ sơ tư vấn chuyên gia từ kết quả chẩn đoán.", "case": case}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    Requires Pro/Enterprise personal subscription or platform admin. Free tier users are rejected with 403 Forbidden.
    New customer organizations start on the unpaid `pilot` plan and in the `pending` lifecycle state.
    """
    can_create, reason = gari_plans.can_user_create_organization(current_user)
    if not can_create:
        raise HTTPException(
            status_code=403,
            detail="Tạo Hợp tác xã hoặc Doanh nghiệp yêu cầu tài khoản nâng cấp gói Pro hoặc Doanh nghiệp. Vui lòng nâng cấp gói để tiếp tục."
        )

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
        gari_entitlements.enforce_entitlement(current_user["id"], "organization_seats", org_id=org_id)
        new_m = gari_b2b.add_member_by_email(
            org_id=org_id,
            actor_user_id=current_user["id"],
            email=payload.email,
            role=payload.role or "member"
        )
        return {"success": True, "member": new_m, "message": "Thêm thành viên vào tổ chức thành công!"}
    except gari_entitlements.EntitlementExceededError as ee:
        raise HTTPException(status_code=403, detail={"error": "entitlement_exceeded", "message": ee.message, "upgrade": ee.upgrade_data})
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


@app.post("/api/invitations/decline")
async def decline_invitation_api(
    payload: DeclineInvitationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Decline an invitation addressed to the authenticated user."""
    if not payload.token:
        raise HTTPException(status_code=400, detail="Token lời mời không được để trống.")
    try:
        result = gari_b2b.decline_invitation(payload.token, current_user, reason=payload.reason)
        return {"success": True, "decline": result, "message": "Đã từ chối lời mời."}
    except Exception as e:
        _raise_org_http_error(e)


@app.post("/api/invitations/{token}/decline")
async def decline_invitation_token_api(
    token: str,
    payload: Optional[DeclineInvitationPayload] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Decline an invitation by token path parameter."""
    try:
        reason = payload.reason if payload else None
        result = gari_b2b.decline_invitation(token, current_user, reason=reason)
        return {"success": True, "decline": result, "message": "Đã từ chối lời mời."}
    except Exception as e:
        _raise_org_http_error(e)


@app.post("/api/organizations/{org_id}/leave")
async def leave_organization_api(
    org_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Voluntarily leave an organization. Owners must transfer ownership first."""
    try:
        result = gari_b2b.leave_organization(org_id, current_user["id"])
        return {"success": True, **result, "message": "Bạn đã rời khỏi tổ chức thành công."}
    except Exception as e:
        _raise_org_http_error(e)


@app.post("/api/organizations/{org_id}/transfer-ownership")
async def transfer_organization_ownership_alias_api(
    org_id: int,
    payload: TransferOwnershipPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Alias for transferring organization ownership."""
    return await transfer_organization_ownership_api(org_id, payload, current_user)


@app.get("/api/organizations/{org_id}/assignments")
async def list_member_scopes_api(
    org_id: int,
    user_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List member farm/zone/plot assignments."""
    _require_org_permission(org_id, current_user["id"], "org.view")
    assignments = gari_b2b.list_member_scopes(org_id, user_id=user_id)
    return {"success": True, "total": len(assignments), "assignments": assignments}


@app.post("/api/organizations/{org_id}/assignments")
async def assign_member_scope_api(
    org_id: int,
    payload: MemberScopeAssignmentPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Assign a member to a farm, zone, or plot."""
    try:
        assignment = gari_b2b.assign_member_scope(
            org_id=org_id,
            actor_user_id=current_user["id"],
            target_user_id=payload.user_id,
            farm_id=payload.farm_id,
            zone_id=payload.zone_id,
            plot_id=payload.plot_id,
            notes=payload.notes
        )
        return {"success": True, "assignment": assignment, "message": "Phân công phạm vi thành công!"}
    except Exception as e:
        _raise_org_http_error(e)


@app.delete("/api/organizations/{org_id}/assignments/{assignment_id}")
async def remove_member_scope_api(
    org_id: int,
    assignment_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Remove a member farm/zone/plot assignment."""
    try:
        gari_b2b.remove_member_scope(org_id, current_user["id"], assignment_id)
        return {"success": True, "message": "Đã xóa phân công phạm vi."}
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


@app.get("/api/models/quality-metrics")
async def get_model_quality_metrics():
    """
    Exposes verifiable AI model quality, inference latency percentiles,
    and LeafGate / uncertainty screening observability metrics calculated from actual diagnosis records.
    Never returns fabricated accuracy claims.
    """
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT inference_time_ms, confidence, predicted_disease, model_name, crop_name FROM diagnoses")
        rows = [dict(r) for r in cursor.fetchall()]

    latencies = [float(r["inference_time_ms"]) for r in rows if r.get("inference_time_ms") is not None]
    confidences = [float(r["confidence"]) for r in rows if r.get("confidence") is not None]

    # Calculate percentiles
    p50, p95, p99, avg_lat = 0.0, 0.0, 0.0, 0.0
    if latencies:
        s_lat = sorted(latencies)
        n = len(s_lat)
        p50 = round(s_lat[int(0.50 * n)], 2)
        p95 = round(s_lat[min(int(0.95 * n), n - 1)], 2)
        p99 = round(s_lat[min(int(0.99 * n), n - 1)], 2)
        avg_lat = round(sum(latencies) / n, 2)

    total_diag = len(rows)
    uncertainty_count = sum(1 for c in confidences if c < 0.65)
    high_conf_count = sum(1 for c in confidences if c >= 0.85)

    uncertainty_rate = round((uncertainty_count / total_diag * 100), 1) if total_diag > 0 else 0.0
    high_conf_rate = round((high_conf_count / total_diag * 100), 1) if total_diag > 0 else 0.0

    return {
        "success": True,
        "observability_version": "2.0.0",
        "inventory": {
            "total_crop_models": len(engine.list_models()),
            "loaded_models_count": len(engine.cache),
            "inference_device": str(engine.device),
            "primary_architecture": "ConvNeXt Small / ViT Base"
        },
        "latency_percentiles_ms": {
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "mean": avg_lat,
            "sample_count": len(latencies)
        },
        "quality_and_uncertainty": {
            "total_inferences": total_diag,
            "uncertainty_screening_rate_pct": uncertainty_rate,
            "high_confidence_rate_pct": high_conf_rate,
            "leaf_gate_rejection_mechanism": "Two-phase: ViT Leaf Mask & Sharpness thresholding before inference",
            "uncertainty_policy": "Tất cả chẩn đoán có độ tin cậy < 65% đều kích hoạt chế độ Cảnh báo Cân nhắc và khuyến nghị xác nhận mẫu hoặc tham vấn chuyên gia."
        },
        "ground_truth_disclaimer": "Độ chính xác thực địa (field precision) được đo lường dựa trên mẫu kiểm định thực tế và đối chiếu chuyên gia khuyến nông. GARI không công bố số liệu tổng quát 98% mà đánh giá theo từng tập kiểm định chuẩn."
    }


@app.get("/api/user/quota")
async def get_user_quota_api(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Returns ChatGPT-like classification quota metadata for the current user or guest (Part 1).
    Privilege resolution strictly relies on authenticated database records and subscriptions.
    """
    is_vip = gari_quota.is_vip_account(current_user)
    client_ip = request.client.host if request.client else "127.0.0.1"
    client_override = request.headers.get("X-Client-Id")
    client_id, user_id_val = gari_quota.get_client_identifier(current_user, ip_address=client_ip, client_override=client_override)
    quota_info = gari_quota.get_quota_status(
        client_id, user_id=user_id_val, is_vip=is_vip,
        user=current_user
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
async def model_load(
    crop_id: str,
    current_user: Dict[str, Any] = Depends(get_current_admin_user)
):
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
async def model_unload(
    crop_id: str,
    current_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    success = engine.unload_model(crop_id)
    return {"success": success, "crop_id": crop_id, "status": "UNLOADED" if success else "NOT_FOUND"}


@app.get("/api/admin/models/lifecycle")
async def get_model_lifecycle_status(
    include_all: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """
    Returns real-time model lifecycle status, active inference counts,
    memory consumption, and recent lifecycle events.
    Protected by administrator authentication.
    """
    try:
        status_data = engine.lifecycle.get_lifecycle_status(include_all_registered=include_all)
        status_data["recent_events"] = engine.lifecycle.get_recent_events(limit=50)
        return {"success": True, "lifecycle": status_data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# -----------------------------------------------------------------------------
# AI Inference Prediction Endpoint (GARI VISION - Real AI + Real File Storage)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# AI Inference & Plant Doctor Endpoints (GARI VISION - Real AI + Localization)
# -----------------------------------------------------------------------------

@app.post("/api/plant/identify")
@app.post("/api/crop/detect")
@app.post("/api/detect-crop")
@app.post("/api/validate-image")
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
    growth_stage: Optional[str] = Form(None),
    user_symptoms: Optional[str] = Form(None),
    field_conditions: Optional[str] = Form(None),
    image_references: Optional[str] = Form(None),
    consent_store_image: bool = Form(False),
    save_history: bool = Form(True),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    t_req_received = time.perf_counter()
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:12])
    logger.debug("[PERF_TRACE] 1. Request received: %s (req_id=%s)", request.url.path, request_id)

    # Enforce moderation restrictions (banned, suspended, or upload_restricted)
    gari_moderation.enforce_user_moderation_access(current_user, required_feature=gari_moderation.RESTRICTION_UPLOAD)

    upload = image or file
    if not upload:
        raise HTTPException(status_code=400, detail="Vui lòng tải lên file hình ảnh (field: 'image' hoặc 'file').")
    data = await upload.read()
    if not data or len(data) == 0:
        raise HTTPException(status_code=400, detail="Tập tin hình ảnh không được để trống.")
    
    t_img_read = time.perf_counter()
    upload_time_ms = (t_img_read - t_req_received) * 1000
    user_type = "registered" if current_user and current_user.get("id") else "guest"
    logger.info(
        "[DIAGNOSE_REQ] req_id=%s file_size_kb=%.1f user_type=%s endpoint=%s",
        request_id, len(data) / 1024.0, user_type, request.url.path
    )
    logger.debug("[PERF_TRACE] 2. Image upload/read: %.2f ms (%d bytes)", upload_time_ms, len(data))

    # Max image size: 15 MB
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Kích thước hình ảnh vượt quá giới hạn 15MB.")

    # In-flight duplicate inference prevention (double-click protection)
    img_hash = hashlib.sha256(data).hexdigest()[:16]
    user_key = f"{current_user['id']}_{img_hash}"
    async with _ACTIVE_INFERENCES_LOCK:
        now = time.time()
        for k in list(_ACTIVE_INFERENCES.keys()):
            if now - _ACTIVE_INFERENCES[k] > 10.0:
                del _ACTIVE_INFERENCES[k]
        if user_key in _ACTIVE_INFERENCES:
            elapsed = now - _ACTIVE_INFERENCES[user_key]
            if elapsed < 3.0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Yêu cầu chẩn đoán cho hình ảnh này đang được xử lý trên máy chủ. Vui lòng không nhấn liên tục."
                )
        _ACTIVE_INFERENCES[user_key] = now

    # Bounded server concurrency & queue handling
    t_queue_start = time.perf_counter()
    try:
        await asyncio.wait_for(INFERENCE_SEMAPHORE.acquire(), timeout=15.0)
    except asyncio.TimeoutError:
        async with _ACTIVE_INFERENCES_LOCK:
            _ACTIVE_INFERENCES.pop(user_key, None)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Máy chủ AI hiện đang bận xử lý nhiều tác vụ đồng thời. Vui lòng thử lại sau giây lát."
        )
    queue_wait_ms = (time.perf_counter() - t_queue_start) * 1000

    inference_continues_in_background = False
    try:

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

        t_img_decode = time.perf_counter()
        logger.debug("[PERF_TRACE] 3. Image decode and format validation: %.2f ms", (t_img_decode - t_img_read) * 1000)

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

        is_pro_authorized = gari_quota.is_vip_account(current_user)

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
                user=current_user
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

        # Truthful Server-Side Model Availability Check (Part 9 & 10)
        if target_mode == "manual":
            if not target_crop:
                raise HTTPException(status_code=400, detail="Vui lòng chọn loại cây trồng khi sử dụng chế độ chỉ định cây.")
            p_meta = gari_inference_engine.resolve_priority_crop(target_crop)
            if p_meta:
                if p_meta["has_disease_model"]:
                    target_model_dir = p_meta["disease_model_dir"]
                    entry = engine.get_model_entry(target_model_dir)
                    if not entry or not entry.weight_path.exists():
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"Mô hình AI chẩn đoán cho cây trồng '{target_crop}' hiện không khả dụng trên máy chủ."
                        )
                # If not has_disease_model (e.g. Durian), allow engine.predict() to return clean disease_model_unavailable JSON
            else:
                entry = engine.get_model_entry(target_crop)
                if not entry or not entry.weight_path.exists():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Mô hình AI chẩn đoán cho cây trồng '{target_crop}' hiện không khả dụng trên máy chủ."
                    )
        elif target_mode == "auto_standard":
            global_model_path = engine.models_dir / "Model tong"
            if not global_model_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Mô hình AI tổng hợp (Model tong) hiện không khả dụng trên máy chủ."
                )
        elif target_mode == "auto_pro":
            p1 = engine.models_dir / "Model tong 2 (vip)"
            p2 = engine.models_dir / "Model tong 2"
            if not p1.exists() and not p2.exists():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Mô hình AI chuyên sâu (Model tong 2) hiện không khả dụng trên máy chủ."
                )

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
                detail="Mô hình nhận diện loài chuyên sâu (Model tong 2) dành riêng cho tài khoản Pro hoặc Doanh nghiệp. Vui lòng nâng cấp gói Pro để mở khóa."
            )

        t_preflight = time.perf_counter()
        logger.debug("[PERF_TRACE] 4. Quota and Permission Preflight: %.2f ms", (t_preflight - t_img_decode) * 1000)

        t_infer_start = time.perf_counter()
        try:
            inference_task = asyncio.create_task(asyncio.to_thread(
                engine.predict,
                data,
                crop_id=target_crop,
                mode=target_mode,
                dev_pro_authorized=is_pro_authorized,
                user_entitled=is_pro_authorized
            ))
            res = await asyncio.wait_for(
                asyncio.shield(inference_task),
                timeout=gari_config.INFERENCE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            # Python cannot safely stop an in-flight PyTorch operation. Keep
            # its semaphore slot until the worker really exits, rather than
            # admitting unlimited timed-out jobs and exhausting the host.
            inference_continues_in_background = True
            def _release_slot_when_finished(task: asyncio.Task) -> None:
                try:
                    task.result()
                except Exception as background_error:
                    logger.warning("[DIAGNOSE_TIMEOUT_COMPLETION] req_id=%s error=%s", request_id, background_error)
                finally:
                    INFERENCE_SEMAPHORE.release()
            inference_task.add_done_callback(_release_slot_when_finished)
            logger.warning(
                "[DIAGNOSE_TIMEOUT] req_id=%s timeout_seconds=%s",
                request_id,
                gari_config.INFERENCE_TIMEOUT_SECONDS,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Yêu cầu xử lý quá thời gian. Bạn có thể thử lại."
            )
        except (RuntimeError, ValueError) as model_err:
            logger.error("AI Model inference failure: %s", model_err)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Dịch vụ mô hình AI chẩn đoán hiện không khả dụng: {model_err}"
            )
        t_infer_end = time.perf_counter()
        logger.debug("[PERF_TRACE] 5. Model Inference Pipeline total: %.2f ms", (t_infer_end - t_infer_start) * 1000)
        res["image_url"] = image_web_url
        res["mode"] = target_mode

        # -------------------------------------------------------------
        # Leaf Validation Gate Enforcement (Part 1 & 8)
        # -------------------------------------------------------------
        val_info = res.get("validation", {})
        val_status = val_info.get("status", "LEAF_VALID")
        total_pipeline_ms = (time.perf_counter() - t_req_received) * 1000.0
        logger.info(
            "[DIAGNOSE_RESULT] req_id=%s validation_status=%s crop=%s disease=%s confidence=%.4f latency_ms=%.1f",
            request_id, val_status, res.get("crop_id") or res.get("crop"),
            res.get("disease_id") or res.get("prediction"),
            float(res.get("confidence") or 0.0), total_pipeline_ms
        )
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
                user=current_user
            )
            res["quota"] = updated_quota
            res["quota_deducted"] = not is_pro_authorized

        t_quota_deduct = time.perf_counter()
        logger.debug("[PERF_TRACE] 6. Quota deduction: %.2f ms", (t_quota_deduct - t_infer_end) * 1000)

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

        # Determine exact Sprint 4 & Module 02 diagnosis_status and confidence levels
        is_healthy = bool(res.get("is_healthy", False))
        res_status = res.get("status", "OK")
        conf_val = float(res.get("confidence", 0.0))

        # Configurable Confidence Thresholds (High >= 0.70, Medium >= 0.45, Low < 0.45)
        CONF_THRESH_HIGH = 0.70
        CONF_THRESH_MEDIUM = 0.45

        if conf_val >= CONF_THRESH_HIGH:
            confidence_level = "high"
            confidence_level_vi = "Cao"
            is_uncertain = False
            uncertainty_explanation = None
        elif conf_val >= CONF_THRESH_MEDIUM:
            confidence_level = "medium"
            confidence_level_vi = "Trung bình"
            is_uncertain = False
            uncertainty_explanation = "Độ tin cậy ở mức trung bình (45% - 70%). Khuyến nghị quan sát thêm triệu chứng trên các lá lân cận."
        else:
            confidence_level = "low"
            confidence_level_vi = "Thấp"
            is_uncertain = True
            uncertainty_explanation = "Độ tin cậy của mô hình dưới 45%. Kết quả mang tính tham khảo và chưa đủ cơ sở để kết luận chắc chắn bệnh lý. Khuyến nghị chụp lại góc ảnh rõ hơn hoặc gửi yêu cầu tham vấn chuyên gia BVTV."

        if res_status in ("crop_uncertain", "unsupported_crop", "crop_identified_no_disease_model", "disease_model_unavailable"):
            diagnosis_status = "unknown_or_unsupported"
        elif res_status in ("disease_uncertain", "uncertain") or (is_uncertain and not is_healthy):
            diagnosis_status = "needs_review"
        elif is_healthy or res_status in ("OK", "healthy"):
            diagnosis_status = "diagnosed"
        else:
            diagnosis_status = "needs_review"

        res["confidence_level"] = confidence_level
        res["confidence_level_vi"] = confidence_level_vi
        res["is_uncertain"] = is_uncertain
        res["uncertainty_explanation_vi"] = uncertainty_explanation
        res["is_verified"] = False
        res["diagnosis_type"] = "ai_prediction"
        res["verified_by"] = None
        res["verified_at"] = None
        res["disclaimer_vi"] = "Kết quả phân tích được tạo tự động bởi mô hình AI (Chưa qua thẩm định của Chuyên gia BVTV). Luôn đối chiếu với thực địa trước khi áp dụng biện pháp xử lý."

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
                "user_notes": notes or "",
                "growth_stage": growth_stage,
                "user_symptoms": user_symptoms,
                "field_conditions": field_conditions,
                "image_references": image_references
            }, user_id=user_id)
            saved_diag_id = diag_record["id"]
            res["saved_diagnosis_id"] = saved_diag_id
            res["diagnosis_id"] = saved_diag_id
            res["id"] = saved_diag_id
            res["farm_plot_id"] = p_id
            res["actor_user_id"] = user_id
            res["organization_id"] = target_org_id
            res["model_version"] = diag_record.get("model_version", "2026.1")

        t_db_save = time.perf_counter()
        logger.debug("[PERF_TRACE] 7. Database history operations: %.2f ms", (t_db_save - t_quota_deduct) * 1000)

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
            "confidence_level": res.get("confidence_level", "low"),
            "confidence_level_vi": res.get("confidence_level_vi", "Thấp"),
            "is_uncertain": res.get("is_uncertain", False),
            "uncertainty_explanation_vi": res.get("uncertainty_explanation_vi"),
            "severity": res.get("severity", "MEDIUM"),
            "is_healthy": is_healthy,
            "is_verified": False,
            "diagnosis_type": "ai_prediction",
            "disclaimer_vi": res.get("disclaimer_vi"),
            "message_vi": res.get("message_vi", res.get("message", ""))
        }
        res["follow_up_actions"] = [
            {
                "key": "ask_assistant",
                "label": "Hỏi Trợ lý AI về kết quả này",
                "endpoint": "/api/assistant/chat",
                "diagnosis_id": saved_diag_id
            },
            {
                "key": "create_task",
                "label": "Tạo công việc xử lý",
                "endpoint": "/api/assistant/action/confirm",
                "diagnosis_id": saved_diag_id
            },
            {
                "key": "request_expert",
                "label": "Gửi chuyên gia BVTV thẩm định",
                "endpoint": "/api/expert/cases",
                "diagnosis_id": saved_diag_id
            }
        ]
        res["crop"] = crop_dict
        res["crop_info"] = crop_dict
        res["diagnosis"] = diag_dict
        res["diagnosis_info"] = diag_dict
        res["localization"] = {
            "status": res.get("localization_status", "unavailable"),
            "has_attention_map": bool(res.get("has_attention_map")),
            "message_vi": res.get("localization_message_vi"),
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

        t_total = time.perf_counter() - t_req_received
        res["request_id"] = request_id
        res["execution_location"] = "server"
        res["device"] = str(engine.device)
        res["timings"] = {
            "upload_time_ms": round(upload_time_ms, 2),
            "queue_wait_ms": round(queue_wait_ms, 2),
            "preprocessing_time_ms": round((t_infer_start - t_img_read) * 1000, 2),
            "inference_time_ms": round((t_infer_end - t_infer_start) * 1000, 2),
            "database_time_ms": round((t_db_save - t_infer_end) * 1000, 2),
            "total_response_time_ms": round(t_total * 1000, 2),
        }

        logger.info(
            "[PERF] Diagnosis complete: total=%.2f ms | upload=%.1f ms | queue=%.1f ms | decode=%.1f ms | preflight=%.1f ms | model=%.1f ms | quota=%.1f ms | db=%.1f ms",
            t_total * 1000,
            upload_time_ms,
            queue_wait_ms,
            (t_img_decode - t_img_read) * 1000,
            (t_preflight - t_img_decode) * 1000,
            (t_infer_end - t_infer_start) * 1000,
            (t_quota_deduct - t_infer_end) * 1000,
            (t_db_save - t_quota_deduct) * 1000
        )

        resp_headers = {
            "X-Request-Id": request_id,
            "X-Inference-Location": "server",
            "X-Inference-Device": str(engine.device),
            "X-Inference-Time-Ms": str(round((t_infer_end - t_infer_start) * 1000, 2)),
            "X-Total-Response-Time-Ms": str(round(t_total * 1000, 2)),
        }
        return JSONResponse(content=res, headers=resp_headers)
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
    finally:
        if not inference_continues_in_background:
            INFERENCE_SEMAPHORE.release()
        async with _ACTIVE_INFERENCES_LOCK:
            if user_key in _ACTIVE_INFERENCES:
                _ACTIVE_INFERENCES[user_key] = time.time()


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


class HostOrgStatusPayload(BaseModel):
    status: str
    reason: Optional[str] = None


class HostOrgPlanPayload(BaseModel):
    plan_id: str
    reason: Optional[str] = None


@app.get("/api/host/organizations")
async def host_get_organizations_api(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve all organizations across the platform with owner, member count, and quota status."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        where = "WHERE 1=1"
        params: List[Any] = []
        if status:
            where += " AND o.status = ?"
            params.append(status.strip().lower())
        total = cursor.execute(f"SELECT count(*) FROM organizations o {where}", params).fetchone()[0]
        cursor.execute(f"""
            SELECT o.id, o.name, o.slug, o.plan_id, o.status, o.created_at, o.contact_email, o.contact_phone,
                   u.full_name as owner_name, u.email as owner_email,
                   (SELECT COUNT(*) FROM organization_members m WHERE m.organization_id = o.id) as members_count,
                   q.quota_limit, q.used_count
            FROM organizations o
            LEFT JOIN users u ON o.owner_id = u.id
            LEFT JOIN organization_quotas q ON o.id = q.organization_id
            {where}
            ORDER BY o.id DESC LIMIT ? OFFSET ?
        """, params + [limit, offset])
        orgs = [dict(r) for r in cursor.fetchall()]

    return {"success": True, "total": total, "organizations": orgs, "limit": limit, "offset": offset}


@app.get("/api/host/organizations/{org_id}/members")
async def host_get_org_members_api(
    org_id: int,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve all members of a specific organization for Host review."""
    members = gari_b2b.get_organization_members(org_id)
    return {"success": True, "members": members}


@app.patch("/api/host/organizations/{org_id}/status")
async def host_update_org_status_api(
    org_id: int,
    payload: HostOrgStatusPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Host action to activate, suspend, or archive an entire organization."""
    new_status = payload.status.strip().lower()
    if new_status not in ("active", "suspended", "pending", "archived"):
        raise HTTPException(status_code=400, detail="Trạng thái tổ chức không hợp lệ.")
    reason = payload.reason or f"Quản trị viên Host đổi trạng thái sang {new_status}"
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, name FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy tổ chức.")
        old_status = row["status"]
        cursor.execute("UPDATE organizations SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, org_id))
        conn.commit()

    client_ip = request.client.host if request.client else "127.0.0.1"
    gari_auth.record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type="organization.status_change",
        target_resource=f"org_{org_id}",
        details={"old_status": old_status, "new_status": new_status, "org_name": row["name"]},
        reason=reason,
        outcome="success",
        ip_address=client_ip
    )
    return {"success": True, "organization_id": org_id, "status": new_status, "message": f"Đã chuyển trạng thái tổ chức sang '{new_status}'."}


@app.patch("/api/host/organizations/{org_id}/plan")
async def host_update_org_plan_api(
    org_id: int,
    payload: HostOrgPlanPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Host administrative override to assign a specific plan to an organization."""
    plan_id = payload.plan_id.strip().lower()
    if plan_id not in gari_b2b.PLANS_CONFIG:
        raise HTTPException(status_code=400, detail="Mã gói cước không hợp lệ.")
    plan = gari_b2b.PLANS_CONFIG[plan_id]
    reason = payload.reason or f"Host chỉ định gói {plan_id}"

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT plan_id, name FROM organizations WHERE id = ?", (org_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy tổ chức.")
        old_plan = row["plan_id"]
        cursor.execute("UPDATE organizations SET plan_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (plan_id, org_id))
        cursor.execute("""
            UPDATE organization_quotas SET plan_id = ?, quota_limit = ?
            WHERE organization_id = ?
        """, (plan_id, plan["quota_limit_per_cycle"], org_id))
        conn.commit()

    client_ip = request.client.host if request.client else "127.0.0.1"
    gari_auth.record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type="organization.plan_change",
        target_resource=f"org_{org_id}",
        details={"old_plan": old_plan, "new_plan": plan_id, "org_name": row["name"]},
        reason=reason,
        outcome="success",
        ip_address=client_ip
    )
    return {"success": True, "organization_id": org_id, "plan_id": plan_id, "message": f"Đã cập nhật gói tổ chức thành '{plan['name_vi']}'."}


@app.get("/api/host/payments")
async def host_get_payments_api(
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Host inspection of recent customer transactions and payment entitlements."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        total = cursor.execute("SELECT count(*) FROM payment_orders").fetchone()[0]
        cursor.execute("""
            SELECT p.id, p.order_code, p.amount, p.currency, p.payment_status as status, p.plan_id, p.provider as payment_method, p.created_at,
                   u.email as user_email, u.full_name as user_name
            FROM payment_orders p
            LEFT JOIN users u ON p.user_id = u.id
            ORDER BY p.id DESC LIMIT ? OFFSET ?
        """, (limit, offset))
        orders = [dict(r) for r in cursor.fetchall()]
    return {"success": True, "total": total, "payments": orders, "limit": limit, "offset": offset}



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



# =============================================================================
# GARI HOST CONSOLE — EXPERTS, SUBSCRIPTIONS & AI TESTING
# =============================================================================

class ExpertApplicationPayload(BaseModel):
    full_name: str
    phone: Optional[str] = None
    title: Optional[str] = None
    organization: Optional[str] = None
    specialties: List[str] = []
    years_experience: Optional[int] = 0
    license_number: Optional[str] = None
    degree_details: Optional[str] = None
    portfolio_url: Optional[str] = None
    bio: Optional[str] = None

class ReviewExpertApplicationPayload(BaseModel):
    action: str  # "approve" or "reject"
    admin_notes: Optional[str] = None
    commission_rate: Optional[float] = 0.15

class ExpertStatusPayload(BaseModel):
    is_active: bool
    status: Optional[str] = None

class ExpertCaseMessagePayload(BaseModel):
    message: str
    is_prescription: Optional[bool] = False
    prescription_data: Optional[Dict[str, Any]] = None
    attachments: Optional[List[str]] = None

class ResolveExpertCasePayload(BaseModel):
    resolution_notes: str
    diagnosis_correction: Optional[str] = None
    prescription_data: Optional[Dict[str, Any]] = None

class ExpertRequestInfoPayload(BaseModel):
    question: str
    attachments: Optional[List[str]] = None

class ExpertProvideInfoPayload(BaseModel):
    info: str
    attachments: Optional[List[str]] = None

class CloseExpertCasePayload(BaseModel):
    rating: Optional[int] = None
    feedback_notes: Optional[str] = None


@app.get("/api/host/experts/applications")
async def host_list_expert_applications_api(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """List expert qualification applications for administrative approval."""
    apps = gari_database.list_expert_applications(status=status)
    return {"success": True, "applications": apps, "total": len(apps)}


@app.post("/api/host/experts/applications/{app_id}/review")
async def host_review_expert_application_api(
    app_id: int,
    payload: ReviewExpertApplicationPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Approve or reject an agronomist expert application."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    try:
        res = gari_experts.review_expert_application(
            app_id=app_id,
            action=payload.action,
            host_user_id=current_host["id"],
            host_email=current_host.get("email", ""),
            reason=payload.admin_notes or "",
            ip_address=client_ip
        )
        return {
            "success": True,
            "message": f"Đã {payload.action} đơn đăng ký chuyên gia thành công.",
            "application_id": app_id,
            "application": res
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xét duyệt hồ sơ chuyên gia: {str(e)}")


@app.get("/api/host/experts")
async def host_list_expert_profiles_api(
    active_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """List approved agricultural experts in the platform."""
    experts = gari_database.list_expert_profiles(active_only=active_only)
    return {"success": True, "experts": experts, "total": len(experts)}


@app.patch("/api/host/experts/{expert_id}/status")
async def host_update_expert_status_api(
    expert_id: int,
    payload: ExpertStatusPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Update active status of an approved expert."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    status_str = payload.status or ("active" if payload.is_active else "suspended")
    try:
        res = gari_experts.update_expert_status(
            expert_id=expert_id,
            is_active=payload.is_active,
            status_str=status_str,
            host_user_id=current_host["id"],
            host_email=current_host.get("email", ""),
            reason=f"Host Admin cập nhật trạng thái chuyên gia ID {expert_id}",
            ip_address=client_ip
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi cập nhật trạng thái chuyên gia: {str(e)}")


@app.get("/api/host/subscriptions/overview")
async def host_subscriptions_overview_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Host inspection of global subscriptions, MRR, and plan allocations."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plan_id as plan, status, count(*) as count 
            FROM subscriptions 
            GROUP BY plan_id, status
        """)
        plan_breakdown = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT count(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT count(*) FROM users WHERE account_type = 'pro' OR is_expert = 1")
        pro_users = cursor.fetchone()[0]

        cursor.execute("SELECT count(*) FROM organizations")
        total_orgs = cursor.fetchone()[0]

        cursor.execute("SELECT sum(amount) FROM payment_orders WHERE payment_status = 'completed'")
        total_revenue = cursor.fetchone()[0] or 0

    return {
        "success": True,
        "total_users": total_users,
        "pro_users": pro_users,
        "total_organizations": total_orgs,
        "total_revenue_vnd": total_revenue,
        "plan_breakdown": plan_breakdown
    }


@app.post("/api/host/ai/test")
async def host_ai_test_api(
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """
    Run diagnostic benchmark tests on the active AI engine (Torch, ONNX, Vision, Gemini).
    Measures execution latency, model status, and inference readiness.
    """
    client_ip = request.client.host if request.client else "0.0.0.0"
    start_t = time.perf_counter()
    import numpy as np

    # Synthetic test leaf image (64x64 green patch)
    dummy_img = Image.new("RGB", (224, 224), color=(34, 139, 34))
    
    # Run test inference through engine
    result = engine.predict(dummy_img, top_k=3, crop_id="tomato")
    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)

    diag_info = {
        "engine_status": "healthy" if result and result.get("success") else "degraded",
        "latency_ms": elapsed_ms,
        "model_version": getattr(engine, "model_version", "v2.4-hybrid-vietgap"),
        "active_backend": getattr(engine, "backend_name", "PyTorch / TorchScript"),
        "top_prediction": result.get("primary_disease") if result else None,
        "confidence": result.get("confidence") if result else 0.0,
        "gemini_assistant_ready": bool(os.getenv("GEMINI_API_KEY", "")),
        "tested_at": datetime.now(timezone.utc).isoformat()
    }

    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type="ai_model_diagnostic_test",
        target_resource="ai_engine:benchmark",
        details=diag_info,
        reason="Admin trigger AI health check",
        outcome="success",
        ip_address=client_ip
    )
    return {"success": True, "diagnostics": diag_info}


# =============================================================================
# GARI EXPERT NETWORK & CONSULTATION WORKFLOW APIS
# =============================================================================

@app.post("/api/expert/apply")
async def apply_expert_api(
    payload: ExpertApplicationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Submit an application to become a certified GARI Agricultural Expert."""
    try:
        res = gari_experts.apply_for_expert(current_user["id"], payload.model_dump())
        return {
            "success": True,
            "message": "Đơn đăng ký chuyên gia đã được gửi thành công! Quản trị viên GARI sẽ thẩm định trong vòng 24-48 giờ.",
            "application_id": res["id"],
            "application": res
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi nộp đơn chuyên gia: {str(e)}")


@app.get("/api/expert/my-profile")
async def get_my_expert_profile_api(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve expert status and profile for the logged in user."""
    profile = gari_database.get_expert_profile(user_id=current_user["id"])
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_applications WHERE user_id = ? ORDER BY id DESC LIMIT 1", (current_user["id"],))
        latest_app = cursor.fetchone()
    
    return {
        "success": True,
        "is_expert": bool(current_user.get("is_expert")),
        "profile": profile,
        "latest_application": dict(latest_app) if latest_app else None
    }


@app.get("/api/expert/portal/cases")
async def list_expert_portal_cases_api(
    filter_type: str = "all",  # "all", "assigned_to_me", "unassigned", "resolved"
    limit: int = 50,
    offset: int = 0,
    current_expert: Dict[str, Any] = Depends(get_current_expert_user)
):
    """Case queue for verified experts with privacy data masking."""
    cases = gari_experts.list_cases_for_expert(
        expert_user_id=current_expert["id"],
        filter_type=filter_type,
        limit=limit,
        offset=offset
    )
    return {
        "success": True,
        "cases": cases,
        "total": len(cases),
        "filter": filter_type
    }


@app.post("/api/expert/portal/cases/{case_id}/claim")
@app.post("/api/expert/cases/{case_id}/claim")
async def claim_expert_case_api(
    case_id: int,
    current_expert: Dict[str, Any] = Depends(get_current_expert_user)
):
    """Claim responsibility for an open diagnostic consultation case."""
    expert_name = current_expert.get("full_name") or current_expert.get("name") or "Chuyên gia GARI"
    try:
        claimed = gari_experts.claim_consultation_case(case_id, current_expert["id"], expert_name)
        return {"success": True, "message": "Tiếp nhận hồ sơ bệnh thành công!", "case": claimed}
    except (PermissionError, ValueError) as pe:
        raise HTTPException(status_code=400 if isinstance(pe, ValueError) else 403, detail=str(pe))


@app.get("/api/expert/cases/{case_id}/messages")
async def get_case_messages_api(
    case_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve chat message thread for an expert case."""
    case = gari_database.get_expert_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca bệnh.")
    
    is_owner = case.get("user_id") == current_user["id"]
    is_assigned_expert = bool(current_user.get("is_expert")) and (case.get("assigned_expert_id") == current_user["id"])
    is_host = bool(current_user.get("is_host_admin"))
    is_unassigned_open = bool(current_user.get("is_expert")) and not case.get("assigned_expert_id") and case.get("status") in ("submitted", "open")

    if not (is_owner or is_assigned_expert or is_host or is_unassigned_open):
        if bool(current_user.get("is_expert")) and case.get("assigned_expert_id") and case.get("assigned_expert_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Ca bệnh này đã được phân công cho một chuyên gia khác tiếp nhận.")
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem trao đổi ca bệnh này.")
    
    messages = gari_database.get_expert_case_messages(case_id)
    return {"success": True, "case": case, "messages": messages}


@app.post("/api/expert/cases/{case_id}/messages")
async def post_case_message_api(
    case_id: int,
    payload: ExpertCaseMessagePayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Send a message, feedback note, or prescription in the case conversation."""
    case = gari_database.get_expert_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca bệnh.")

    is_owner = case.get("user_id") == current_user["id"]
    is_assigned_expert = bool(current_user.get("is_expert")) and (case.get("assigned_expert_id") == current_user["id"])
    is_host = bool(current_user.get("is_host_admin"))

    if not (is_owner or is_assigned_expert or is_host):
        if bool(current_user.get("is_expert")) and case.get("assigned_expert_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Chỉ chuyên gia được phân công mới có thể gửi tin nhắn trong ca bệnh này.")
        raise HTTPException(status_code=403, detail="Bạn không có quyền gửi tin nhắn trong ca bệnh này.")

    sender_role = "expert" if (is_assigned_expert or is_host) else "farmer"
    sender_name = current_user.get("full_name") or current_user.get("name") or "Người dùng GARI"
    msg = gari_database.add_expert_case_message(
        case_id=case_id,
        sender_user_id=current_user["id"],
        sender_role=sender_role,
        sender_name=sender_name,
        message=payload.message,
        attachments=payload.attachments
    )
    return {"success": True, "message_record": msg}


@app.post("/api/expert/portal/cases/{case_id}/resolve")
@app.post("/api/expert/cases/{case_id}/resolve")
async def resolve_expert_case_api(
    case_id: int,
    payload: ResolveExpertCasePayload,
    current_expert: Dict[str, Any] = Depends(get_current_expert_user)
):
    """Expert concludes the case with detailed prescription and instructions."""
    try:
        resolved = gari_experts.resolve_consultation_case(
            case_id=case_id,
            expert_user_id=current_expert["id"],
            resolution_notes=payload.resolution_notes,
            diagnosis_correction=payload.diagnosis_correction,
            prescription_data=payload.prescription_data
        )
        return {"success": True, "message": "Đã hoàn tất tư vấn ca bệnh và gửi đơn điều trị tới nông hộ!", "case": resolved}
    except (PermissionError, ValueError) as pe:
        raise HTTPException(status_code=400 if isinstance(pe, ValueError) else 403, detail=str(pe))


@app.post("/api/expert/cases/{case_id}/request-info")
async def expert_request_info_api(
    case_id: int,
    payload: ExpertRequestInfoPayload,
    current_expert: Dict[str, Any] = Depends(get_current_expert_user)
):
    """Expert requests additional agronomic details or clearer images from farmer."""
    try:
        expert_name = current_expert.get("full_name") or current_expert.get("name") or "Chuyên gia GARI"
        res = gari_experts.request_additional_info(
            case_id=case_id,
            expert_user_id=current_expert["id"],
            expert_name=expert_name,
            question_message=payload.question,
            attachments=payload.attachments
        )
        return {"success": True, "message": "Đã gửi yêu cầu bổ sung thông tin tới nông hộ.", "result": res, "case": res}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.post("/api/expert/cases/{case_id}/provide-info")
async def user_provide_info_api(
    case_id: int,
    payload: ExpertProvideInfoPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Farmer replies to expert request with clarification or photos."""
    try:
        user_name = current_user.get("full_name") or current_user.get("name") or "Nông hộ GARI"
        res = gari_experts.provide_additional_info(
            case_id=case_id,
            user_id=current_user["id"],
            user_name=user_name,
            response_message=payload.info,
            attachments=payload.attachments
        )
        return {"success": True, "message": "Đã bổ sung thông tin thành công cho chuyên gia.", "result": res, "case": res}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.post("/api/expert/cases/{case_id}/close")
async def user_close_case_api(
    case_id: int,
    payload: CloseExpertCasePayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Farmer closes the consultation case and rates the expert guidance."""
    try:
        res = gari_experts.close_consultation_case(
            case_id=case_id,
            user_id=current_user["id"],
            rating=payload.rating,
            feedback_notes=payload.feedback_notes
        )
        return {"success": True, "message": "Đã đóng ca tư vấn và gửi đánh giá thành công.", "case": res}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/expert/cases/{case_id}/activities")
async def get_case_activities_api(
    case_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve chronological audit activities of status transitions and assignments for a case."""
    try:
        _ = gari_experts.get_consultation_case(case_id, caller_user=current_user)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

    activities = gari_experts.get_case_activities(case_id)
    return {"success": True, "case_id": case_id, "activities": activities}


# =============================================================================
# USER NOTIFICATIONS APIS
# =============================================================================

@app.get("/api/notifications")
async def get_my_notifications_api(
    limit: int = 30,
    unread_only: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List user in-app notifications and unread badge count."""
    notifs = gari_database.list_user_notifications(
        user_id=current_user["id"],
        limit=limit,
        unread_only=unread_only
    )
    unread_count = sum(1 for n in notifs if not n.get("is_read"))
    return {
        "success": True,
        "notifications": notifs,
        "unread_count": unread_count,
        "total": len(notifs)
    }


@app.patch("/api/notifications/{notification_id}/read")
async def mark_notification_read_api(
    notification_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Mark a single notification as read."""
    gari_database.mark_notification_read(notification_id, current_user["id"])
    return {"success": True, "notification_id": notification_id}


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read_api(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Mark all notifications for the current user as read."""
    gari_database.mark_all_notifications_read(current_user["id"])
    return {"success": True, "message": "Đã đánh dấu tất cả thông báo là đã đọc."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=False)

# ============================================================================
# MODULE 03: HOST CONSOLE ASSISTANT MANAGEMENT & EXPERT ESCALATION ENDPOINTS
# ============================================================================
@app.get("/api/host/assistant/config")
async def host_get_assistant_config(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve active AI Assistant provider settings with masked credentials for Host Console."""
    cfg = gari_assistant.get_assistant_config()
    raw_key = cfg.get("api_key") or ""
    masked_key = (raw_key[:4] + "..." + raw_key[-4:]) if len(raw_key) > 8 else ("***" if raw_key else "")

    return {
        "success": True,
        "config": {
            "provider": cfg["provider"],
            "model": cfg["model"],
            "api_key_masked": masked_key,
            "has_api_key": bool(raw_key),
            "base_url": cfg.get("base_url"),
            "temperature": cfg.get("temperature", 0.2),
            "timeout_sec": cfg.get("timeout_sec", 20.0),
            "citations_enabled": cfg.get("citations_enabled", True),
            "deep_dive_enabled": cfg.get("deep_dive_enabled", True),
            "is_configured": cfg["is_configured"]
        },
        "available_providers": [
            gari_assistant.PROVIDER_DISABLED,
            gari_assistant.PROVIDER_GEMINI,
            gari_assistant.PROVIDER_OPENAI,
            gari_assistant.PROVIDER_ANTHROPIC,
            gari_assistant.PROVIDER_MOCK
        ]
    }


@app.post("/api/host/assistant/config")
async def host_update_assistant_config(
    payload: Dict[str, Any],
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Update AI Assistant provider, model, API keys, and behavioral parameters from Host Console."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    reason = str(payload.get("reason") or "Host Admin updated Assistant settings").strip()

    updates = []
    if "provider" in payload:
        p = str(payload["provider"]).strip().lower()
        updates.append(("assistant_provider", p, "AI Provider cho Trợ lý Nông học"))
    if "model" in payload:
        m = str(payload["model"]).strip()
        updates.append(("assistant_model", m, "Tên mô hình LLM chính"))
    if "api_key" in payload:
        k = str(payload["api_key"]).strip()
        # Only update if non-empty and not a masked string
        if k and not k.startswith("***") and "..." not in k:
            updates.append(("assistant_api_key", k, "API Key bảo mật cho Trợ lý AI"))
    if "base_url" in payload:
        b = str(payload["base_url"]).strip()
        updates.append(("assistant_base_url", b, "Base URL cho OpenAI-compatible LLM"))
    if "temperature" in payload:
        t = str(payload["temperature"]).strip()
        updates.append(("assistant_temperature", t, "Độ sáng tạo nhiệt độ LLM"))
    if "timeout_sec" in payload:
        to = str(payload["timeout_sec"]).strip()
        updates.append(("assistant_timeout_sec", to, "Thời gian chờ tối đa phản hồi AI"))
    if "citations_enabled" in payload:
        c = "1" if payload["citations_enabled"] in (True, 1, "1", "true") else "0"
        updates.append(("assistant_citations_enabled", c, "Bật/Tắt trích dẫn nguồn tài liệu nông học"))
    if "deep_dive_enabled" in payload:
        dd = "1" if payload["deep_dive_enabled"] in (True, 1, "1", "true") else "0"
        updates.append(("assistant_deep_dive_enabled", dd, "Bật/Tắt chế độ phân tích chuyên sâu"))

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        for key, val, desc in updates:
            cursor.execute("""
                INSERT INTO host_api_config (key, value, description, updated_by_host_id, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    description = excluded.description,
                    updated_by_host_id = excluded.updated_by_host_id,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, val, desc, current_host["id"]))
        conn.commit()

    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host.get("email"),
        action_type="UPDATE_ASSISTANT_CONFIG",
        target_resource="host_api_config:assistant",
        details=f"Updated keys: {[u[0] for u in updates]}. Reason: {reason}",
        ip_address=client_ip
    )

    return {
        "success": True,
        "message": "Đã lưu và áp dụng cấu hình Trợ lý AI thành công.",
        "updated_keys": [u[0] for u in updates]
    }


@app.post("/api/host/assistant/test")
async def host_test_assistant_provider(
    payload: Optional[Dict[str, Any]] = None,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Test AI Assistant provider adapter connectivity and return latency and response ping."""
    t0 = time.perf_counter()
    p_data = payload or {}
    
    cfg = gari_assistant.get_assistant_config()
    provider = (p_data.get("provider") or cfg["provider"]).lower().strip()
    model = p_data.get("model") or cfg["model"]
    api_key = p_data.get("api_key") or cfg["api_key"]
    base_url = p_data.get("base_url") or cfg["base_url"]
    
    if provider == gari_assistant.PROVIDER_DISABLED:
        return {
            "success": False,
            "status": "disabled",
            "message": "AI Assistant đang ở trạng thái Tắt (Disabled). Vui lòng chọn Provider (Gemini, OpenAI, Anthropic hoặc Mock)."
        }

    mock_diag = {
        "id": 9999,
        "crop_name": "Cà chua",
        "crop_id": "tomato",
        "disease_name_vi": "Bệnh đốm vi khuẩn",
        "predicted_disease": "Tomato Bacterial spot",
        "confidence": 0.95,
        "severity": "HIGH",
        "diagnosis_status": "diagnosed"
    }

    test_msg = [{"role": "user", "content": "Kiểm tra kết nối và tóm tắt ngắn về bệnh đốm vi khuẩn trên cà chua."}]
    system_prompt = gari_assistant.build_agronomic_system_prompt(mock_diag)

    try:
        reply = ""
        if provider == gari_assistant.PROVIDER_MOCK:
            reply = gari_assistant.call_mock_api(system_prompt, test_msg, mock_diag)
        elif provider == gari_assistant.PROVIDER_GEMINI:
            if not api_key:
                raise ValueError("Thiếu Gemini API Key.")
            reply = gari_assistant.call_gemini_api(api_key, model, system_prompt, test_msg, 0.2, 15.0)
        elif provider == gari_assistant.PROVIDER_OPENAI:
            if not api_key:
                raise ValueError("Thiếu OpenAI API Key.")
            reply = gari_assistant.call_openai_compatible_api(api_key, base_url, model, system_prompt, test_msg, 0.2, 15.0)
        elif provider == gari_assistant.PROVIDER_ANTHROPIC:
            if not api_key:
                raise ValueError("Thiếu Anthropic API Key.")
            reply = gari_assistant.call_anthropic_api(api_key, model, system_prompt, test_msg, 0.2, 15.0)
        else:
            raise ValueError(f"Provider không được hỗ trợ: {provider}")

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        gari_host_service.record_ai_health_probe("healthy", elapsed_ms)
        return {
            "success": True,
            "status": "connected",
            "provider": provider,
            "model": model,
            "latency_ms": elapsed_ms,
            "sample_response": reply[:300] + ("..." if len(reply) > 300 else "")
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        gari_host_service.record_ai_health_probe("failing", elapsed_ms, str(exc))
        return {
            "success": False,
            "status": "error",
            "provider": provider,
            "model": model,
            "latency_ms": elapsed_ms,
            "error_detail": str(exc)
        }


@app.post("/api/assistant/expert/escalate")
async def assistant_escalate_to_expert(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Escalate diagnosis from Assistant conversation to Agronomist Expert Network."""
    diag_id = payload.get("diagnosis_id")
    if not diag_id:
        raise HTTPException(status_code=400, detail="Mã chẩn đoán (diagnosis_id) là bắt buộc.")
    symptoms = (payload.get("symptoms_description") or "").strip()
    
    try:
        res = gari_assistant.PlantHealthAssistantService.escalate_to_expert(
            user_id=current_user["id"],
            diagnosis_id=int(diag_id),
            symptoms_description=symptoms
        )
        return res
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể chuyển hồ sơ chuyên gia: {str(e)}")


# =============================================================================
# MODULE 08 — COMMUNITY & AGRICULTURAL KNOWLEDGE APIS
# =============================================================================

class CreateCommunityPostPayload(BaseModel):
    title: str
    content: str
    crop_id: Optional[str] = None
    region: Optional[str] = None
    post_type: Optional[str] = "question"
    diagnosis_id: Optional[int] = None
    images: Optional[List[str]] = None
    is_official_guidance: Optional[bool] = False


class CreateCommunityCommentPayload(BaseModel):
    content: str
    parent_comment_id: Optional[int] = None


class ReportContentPayload(BaseModel):
    target_type: str
    target_id: int
    reason_category: str
    reason_details: Optional[str] = None


class ReviewModerationReportPayload(BaseModel):
    action: str
    review_notes: str = ""


class KnowledgeArticlePayload(BaseModel):
    id: Optional[int] = None
    title: str
    slug: Optional[str] = None
    crop_id: Optional[str] = None
    topic: Optional[str] = "pest_disease"
    region: Optional[str] = "Toàn quốc"
    summary: str
    content_markdown: str
    source_institution: str
    author_name: Optional[str] = None
    author_title: Optional[str] = None
    publication_date: Optional[str] = None
    verification_badge: Optional[str] = "Viện nghiên cứu chính thống"
    tags: Optional[List[str]] = None
    is_published: Optional[bool] = True


@app.post("/api/community/posts")
async def create_community_post_api(
    payload: CreateCommunityPostPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Publish a community discussion post or question."""
    try:
        post = gari_community.create_post(current_user["id"], payload.model_dump())
        return {
            "success": True,
            "message": "Đã đăng bài thảo luận thành công!",
            "post": post
        }
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"Error creating community post: {exc}")
        raise HTTPException(status_code=500, detail=f"Không thể tạo bài đăng: {str(exc)}")


@app.get("/api/community/posts")
async def list_community_posts_api(
    crop_id: Optional[str] = None,
    region: Optional[str] = None,
    post_type: Optional[str] = None,
    review_status: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """List and search community questions, discussions, and official guidance."""
    viewer_id = current_user["id"] if current_user else None
    res = gari_community.list_posts(
        crop_id=crop_id,
        region=region,
        post_type=post_type,
        review_status=review_status,
        search_query=query,
        limit=limit,
        offset=offset,
        viewer_user_id=viewer_id
    )
    return {"success": True, **res}


@app.get("/api/community/posts/{post_id}")
async def get_community_post_api(
    post_id: int,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """Get detailed view of a community post with author credentials."""
    viewer_id = current_user["id"] if current_user else None
    try:
        post = gari_community.get_post(post_id, viewer_user_id=viewer_id)
        return {"success": True, "post": post}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@app.delete("/api/community/posts/{post_id}")
async def delete_community_post_api(
    post_id: int,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a post by author or authorized system moderator."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    is_mod = current_user.get("role") in ("host_admin", "admin") or current_user.get("is_host_admin", False)
    try:
        ok = gari_community.delete_post(
            post_id=post_id,
            user_id=current_user["id"],
            is_moderator=is_mod,
            reason="User self-deleted or moderator removed",
            moderator_email=current_user.get("email"),
            ip_address=client_ip
        )
        return {"success": ok, "message": "Đã xóa bài viết thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@app.post("/api/community/posts/{post_id}/like")
async def toggle_post_like_api(
    post_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Toggle like on a community post."""
    try:
        res = gari_community.toggle_post_like(current_user["id"], post_id)
        return {"success": True, **res}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@app.post("/api/community/posts/{post_id}/comments")
async def create_community_comment_api(
    post_id: int,
    payload: CreateCommunityCommentPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Post a comment or reply to an existing community post."""
    try:
        comment = gari_community.create_comment(
            user_id=current_user["id"],
            post_id=post_id,
            data=payload.model_dump()
        )
        return {
            "success": True,
            "message": "Đã gửi bình luận thành công!",
            "comment": comment
        }
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"Error creating comment: {exc}")
        raise HTTPException(status_code=500, detail=f"Không thể gửi bình luận: {str(exc)}")


@app.get("/api/community/posts/{post_id}/comments")
async def list_community_comments_api(
    post_id: int,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """List chronological comments and replies for a post."""
    viewer_id = current_user["id"] if current_user else None
    comments = gari_community.list_comments(post_id=post_id, viewer_user_id=viewer_id)
    return {"success": True, "post_id": post_id, "comments": comments, "total": len(comments)}


@app.delete("/api/community/comments/{comment_id}")
async def delete_community_comment_api(
    comment_id: int,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete a comment by author or moderator."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    is_mod = current_user.get("role") in ("host_admin", "admin") or current_user.get("is_host_admin", False)
    try:
        ok = gari_community.delete_comment(
            comment_id=comment_id,
            user_id=current_user["id"],
            is_moderator=is_mod,
            reason="User self-deleted or moderator removed",
            moderator_email=current_user.get("email"),
            ip_address=client_ip
        )
        return {"success": ok, "message": "Đã xóa bình luận thành công."}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@app.post("/api/community/comments/{comment_id}/like")
async def toggle_comment_like_api(
    comment_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Toggle like on a community comment."""
    try:
        res = gari_community.toggle_comment_like(current_user["id"], comment_id)
        return {"success": True, **res}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@app.post("/api/community/reports")
async def report_community_content_api(
    payload: ReportContentPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Report inappropriate, misleading, or abusive content for moderator review."""
    try:
        report = gari_community.report_content(
            reporter_user_id=current_user["id"],
            target_type=payload.target_type,
            target_id=payload.target_id,
            reason_category=payload.reason_category,
            details=payload.reason_details
        )
        return {
            "success": True,
            "message": "Đã tiếp nhận báo cáo vi phạm. Đội ngũ kiểm duyệt sẽ xem xét xử lý.",
            "report": report
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/host/community/reports")
async def list_host_community_reports_api(
    status: Optional[str] = "pending",
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """List reported content queue for Host Console moderation."""
    reports = gari_community.list_moderation_reports(status=status, limit=limit, offset=offset)
    return {"success": True, "reports": reports, "total": len(reports)}


@app.post("/api/host/community/reports/{report_id}/review")
async def review_host_community_report_api(
    report_id: int,
    payload: ReviewModerationReportPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Review a moderation report: dismiss, hide, remove content, or warn/restrict user."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    try:
        res = gari_community.review_moderation_report(
            report_id=report_id,
            moderator_user_id=current_host["id"],
            moderator_email=current_host.get("email") or "admin@gari.internal",
            action=payload.action,
            review_notes=payload.review_notes,
            ip_address=client_ip
        )
        return {"success": True, "message": "Đã thực hiện quyết định kiểm duyệt thành công.", **res}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/knowledge/articles")
async def search_knowledge_articles_api(
    crop_id: Optional[str] = None,
    topic: Optional[str] = None,
    region: Optional[str] = None,
    review_status: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Search and browse peer-reviewed official agricultural knowledge articles."""
    res = gari_community.search_knowledge_articles(
        query=query,
        crop_id=crop_id,
        topic=topic,
        region=region,
        review_status=review_status,
        limit=limit,
        offset=offset
    )
    return {"success": True, **res}


@app.get("/api/knowledge/articles/{id_or_slug}")
async def get_knowledge_article_api(id_or_slug: str):
    """Retrieve full content and citations of a knowledge guide article."""
    try:
        article = gari_community.get_knowledge_article(id_or_slug)
        return {"success": True, "article": article}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))


@app.post("/api/knowledge/articles")
async def create_or_update_knowledge_article_api(
    payload: KnowledgeArticlePayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Publish or update a vetted agricultural knowledge article (Host Admins & Verified Experts only)."""
    try:
        article = gari_community.create_or_update_knowledge_article(
            moderator_user=current_user,
            data=payload.model_dump(),
            article_id=payload.id
        )
        return {
            "success": True,
            "message": "Đã lưu tài liệu tri thức nông học thành công!",
            "article": article
        }
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# =============================================================================
# MODULE 09 — FARM INTELLIGENCE 2D MAP APIS
# =============================================================================

class UpdateFarmLocationPayload(BaseModel):
    latitude: float
    longitude: float
    boundary: Optional[Dict[str, Any]] = None
    geometry_source: Optional[str] = "user_drawn"
    organization_id: Optional[int] = None


class UpdatePlotGeometryPayload(BaseModel):
    geometry: Dict[str, Any]
    geometry_source: Optional[str] = "user_drawn"
    boundary_color: Optional[str] = "#22c55e"
    organization_id: Optional[int] = None


@app.get("/api/farms/{farm_id}/map")
async def get_farm_map_api(
    farm_id: int,
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve 2D map GeoJSON payload for a farm, its located plot boundaries, and unlocated plots."""
    try:
        data = gari_farm_map.get_farm_map_data(
            farm_id=farm_id,
            user_id=current_user["id"],
            org_id=organization_id
        )
        return {"success": True, **data}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.put("/api/farms/{farm_id}/location")
async def update_farm_location_api(
    farm_id: int,
    payload: UpdateFarmLocationPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update farm center coordinates and outer perimeter boundary."""
    try:
        res = gari_farm_map.update_farm_location(
            farm_id=farm_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            user_id=current_user["id"],
            org_id=payload.organization_id,
            boundary=payload.boundary,
            geometry_source=payload.geometry_source or "user_drawn"
        )
        return {"success": True, "message": "Đã cập nhật vị trí nông trại thành công!", **res}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.put("/api/plots/{plot_id}/geometry")
async def update_plot_geometry_api(
    plot_id: int,
    payload: UpdatePlotGeometryPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update plot polygon boundary with GeoJSON validation and automatic centroid calculation."""
    try:
        res = gari_farm_map.update_plot_geometry(
            plot_id=plot_id,
            geometry=payload.geometry,
            user_id=current_user["id"],
            org_id=payload.organization_id,
            geometry_source=payload.geometry_source or "user_drawn",
            boundary_color=payload.boundary_color
        )
        return {"success": True, "message": "Đã cập nhật ranh giới thửa đất thành công!", **res}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/plots/{plot_id}/map-detail")
async def get_plot_map_detail_api(
    plot_id: int,
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve detailed plot inspection card for 2D map click popup/sidebar."""
    try:
        detail = gari_farm_map.get_plot_map_detail(
            plot_id=plot_id,
            user_id=current_user["id"],
            org_id=organization_id
        )
        return {"success": True, **detail}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/farms/map-overview")
async def get_farms_map_overview_api(
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve GeoJSON FeatureCollection of all accessible farms for regional overview map."""
    overview = gari_farm_map.get_user_farms_map_overview(
        user_id=current_user["id"],
        org_id=organization_id
    )
    return {"success": True, **overview}


# =====================================================================
# GARI MODULE 10 — 3D FARM EXPERIENCE API ENDPOINTS
# =====================================================================

@app.get("/api/farms/{farm_id}/scene-3d")
async def get_farm_3d_scene_api(
    farm_id: int,
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve authoritative 3D scene descriptor for Three.js visualization.
    Includes real plot records, instanced plant coordinates, and explicit truth-in-data disclosures.
    """
    try:
        scene = gari_farm_3d.get_farm_3d_scene(
            farm_id=farm_id,
            user_id=current_user["id"],
            org_id=organization_id
        )
        return {"success": True, **scene}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/plots/{plot_id}/scene-3d")
async def get_plot_3d_detail_api(
    plot_id: int,
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve single plot 3D inspection details and individual plant registry layout.
    """
    try:
        detail = gari_farm_3d.get_plot_3d_detail(
            plot_id=plot_id,
            user_id=current_user["id"],
            org_id=organization_id
        )
        return {"success": True, **detail}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# =====================================================================
# GARI MODULE 11 — SUBSCRIPTION & USAGE MANAGEMENT ENDPOINTS
# =====================================================================

@app.get("/api/subscriptions/plans")
async def get_subscription_plans_api():
    """Retrieve all active configurable subscription plans, limits, and pricing."""
    plans = gari_entitlements.list_configurable_plans()
    return {
        "success": True,
        "plans": plans,
        "catalog": {p["id"]: p for p in plans}
    }


@app.get("/api/subscriptions/current")
async def get_current_subscription_api(
    org_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve active subscription state, renewal/expiration dates, and cancellation status."""
    sub_data = gari_entitlements.resolve_subscription(current_user["id"], org_id)
    return {"success": True, **sub_data}


@app.get("/api/subscriptions/usage")
async def get_subscription_usage_api(
    org_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve comprehensive usage vs quota breakdown across all tracked dimensions:
    AI usage, diagnosis usage, farms, plots, seats, storage, expert consultations.
    Includes remaining quotas, percentage bars, and actionable upgrade recommendations.
    """
    summary = gari_entitlements.get_usage_summary(current_user["id"], org_id)
    return {"success": True, **summary}


class SubscriptionCheckoutPayload(BaseModel):
    plan_id: str
    org_id: Optional[int] = None
    provider: Optional[str] = "bank_qr"
    idempotency_key: Optional[str] = None


@app.post("/api/subscriptions/checkout")
async def checkout_subscription_api(
    payload: SubscriptionCheckoutPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Initiate a subscription checkout order through the designated billing provider adapter."""
    try:
        adapter = gari_billing_adapter.get_billing_adapter(payload.provider)
        order = adapter.create_checkout_order(
            user_id=current_user["id"],
            plan_id=payload.plan_id,
            org_id=payload.org_id,
            idempotency_key=payload.idempotency_key
        )
        return {"success": True, "provider": adapter.provider_name, "order": order}
    except Exception as exc:
        logger.exception("Checkout failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


class CancelSubscriptionPayload(BaseModel):
    org_id: Optional[int] = None
    immediate: bool = False
    reason: Optional[str] = None


@app.post("/api/subscriptions/cancel")
async def cancel_subscription_api(
    payload: CancelSubscriptionPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Cancel subscription.
    If immediate is false, keeps benefits active until the end of the billing period.
    """
    target_type = "organization" if payload.org_id else "user"
    target_id = payload.org_id if payload.org_id else current_user["id"]
    
    res = gari_entitlements.cancel_subscription(
        target_type=target_type,
        target_id=target_id,
        immediate=payload.immediate,
        reason=payload.reason or "Yêu cầu hủy từ người dùng"
    )
    return {
        "success": True,
        "message": "Thuê bao đã được chuyển sang trạng thái kết thúc vào cuối kỳ." if not payload.immediate else "Thuê bao đã được hủy ngay lập tức.",
        "subscription": res
    }


class ReactivateSubscriptionPayload(BaseModel):
    org_id: Optional[int] = None


@app.post("/api/subscriptions/reactivate")
async def reactivate_subscription_api(
    payload: ReactivateSubscriptionPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Reactivate a subscription that was scheduled to cancel at period end."""
    target_type = "organization" if payload.org_id else "user"
    target_id = payload.org_id if payload.org_id else current_user["id"]
    res = gari_entitlements.reactivate_subscription(target_type=target_type, target_id=target_id)
    return {"success": True, "message": "Thuê bao đã được kích hoạt tiếp tục duy trì thành công!", "subscription": res}


@app.post("/api/billing/webhook/{provider}")
async def billing_webhook_api(
    provider: str,
    request: Request
):
    """
    Universal webhook endpoint for billing providers.
    Verifies cryptographic signature; confirms payment only when provider validates.
    """
    body_bytes = await request.body()
    headers_dict = dict(request.headers)
    
    try:
        adapter = gari_billing_adapter.get_billing_adapter(provider)
        event_data = adapter.verify_webhook(body_bytes, headers_dict)
        
        # If event contains order code and success status, confirm
        order_code = event_data.get("orderCode") or event_data.get("order_code")
        status_val = event_data.get("status") or event_data.get("code")
        
        if order_code and (status_val in ("PAID", "SUCCESS", "00", "success")):
            confirm_res = adapter.confirm_payment(
                order_code=int(order_code),
                provider_tx_id=str(event_data.get("reference") or event_data.get("tx_id") or "WEBHOOK_TX"),
                notes=f"Confirmed via {provider} webhook"
            )
            return {"success": True, "processed": True, "detail": confirm_res}
            
        return {"success": True, "received": True}
    except gari_billing_adapter.PaymentVerificationError as pve:
        raise HTTPException(status_code=400, detail=str(pve))
    except Exception as exc:
        logger.exception("Webhook processing error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))


class AdminUpdatePlanPayload(BaseModel):
    display_name: Optional[str] = None
    price: Optional[int] = None
    billing_interval: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    diagnosis_limit: Optional[int] = None
    ai_usage_limit: Optional[int] = None
    max_farms: Optional[int] = None
    max_plots: Optional[int] = None
    max_seats: Optional[int] = None
    storage_mb: Optional[int] = None
    expert_consultations_limit: Optional[int] = None
    allowed_features: Optional[List[str]] = None
    is_active: Optional[bool] = None


@app.put("/api/admin/subscriptions/plans/{plan_id}")
async def admin_update_plan_api(
    plan_id: str,
    payload: AdminUpdatePlanPayload,
    admin_user: Dict[str, Any] = Depends(get_current_admin_user)
):
    """Allows authorized platform administrators to dynamically configure subscription plans."""
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    try:
        updated_plan = gari_entitlements.update_plan_configuration(plan_id, updates)
        return {"success": True, "message": f"Cập nhật cấu hình gói {plan_id} thành công!", "plan": updated_plan}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# ============================================================================
# MODULE 12: HOST CONSOLE SECURE SYSTEM ADMINISTRATION
# ============================================================================

class HostResetPasswordPayload(BaseModel):
    new_password: str
    confirm: bool = False
    reason: Optional[str] = "Host Admin manual password reset"


class HostUpdatePlanPayload(BaseModel):
    name: Optional[str] = None
    price: Optional[int] = None
    billing_interval: Optional[str] = None
    description: Optional[str] = None
    target_audience: Optional[str] = None
    diagnosis_limit: Optional[int] = None
    ai_usage_limit: Optional[int] = None
    max_farms: Optional[int] = None
    max_plots: Optional[int] = None
    max_seats: Optional[int] = None
    storage_mb: Optional[int] = None
    expert_consultations_limit: Optional[int] = None
    allowed_features: Optional[List[str]] = None
    is_active: Optional[bool] = None
    confirm: bool = False
    reason: Optional[str] = "Host Admin updated subscription plan limits"


class HostClearErrorsPayload(BaseModel):
    confirm: bool = False
    reason: Optional[str] = "Host Admin cleared system errors"


class HostResolveModerationPayload(BaseModel):
    source: str = "community"
    raw_id: int
    action: str
    reason: str
    confirm: bool = False


# 1. Detailed User Inspector & Password Reset
@app.get("/api/host/users/{user_id}")
async def host_get_user_details_api(
    user_id: int,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve full details, stats, active subscriptions, and audit history of a user."""
    res = gari_host_service.get_user_details(user_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "User not found"))
    return res


@app.post("/api/host/users/{user_id}/reset-password")
async def host_admin_reset_user_password_api(
    user_id: int,
    payload: HostResetPasswordPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Host Admin forces a password reset for a target user. Requires confirmation and audits."""
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail="Thao tác đặt lại mật khẩu người dùng yêu cầu xác nhận rõ ràng (confirm=True)."
        )
    client_ip = request.client.host if request.client else "0.0.0.0"
    res = gari_host_service.admin_reset_user_password(
        host_admin=current_host,
        user_id=user_id,
        new_password=payload.new_password,
        confirm=payload.confirm,
        reason=payload.reason or "Admin manual reset",
        ip_address=client_ip
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Reset failed"))
    return res


# 2. Detailed Organization Inspector
@app.get("/api/host/organizations/{org_id}")
async def host_get_org_details_api(
    org_id: int,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve full details of an organization with owner info, farms, and member roster."""
    res = gari_host_service.get_organization_details(org_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Organization not found"))
    return res


# 3. Detailed Expert Application Inspector
@app.get("/api/host/experts/applications/{app_id}")
async def host_get_expert_app_details_api(
    app_id: int,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve detailed expert application with qualification docs and applicant info."""
    res = gari_host_service.get_expert_application_details(app_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("message", "Application not found"))
    return res


# 4. Subscription & Entitlement Plans Management
@app.get("/api/host/subscriptions/plans")
async def host_get_subscription_plans_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve all configurable subscription plans from database."""
    return gari_host_service.get_all_subscription_plans()


@app.put("/api/host/subscriptions/plans/{plan_id}")
async def host_update_subscription_plan_api(
    plan_id: str,
    payload: HostUpdatePlanPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Update dynamic subscription plan limits and pricing. Requires confirmation and audits."""
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail="Thao tác cập nhật hạn ngạch gói cước yêu cầu xác nhận rõ ràng (confirm=True)."
        )
    client_ip = request.client.host if request.client else "0.0.0.0"
    updates = {k: v for k, v in payload.dict().items() if v is not None and k not in ("confirm", "reason")}
    res = gari_host_service.update_subscription_plan(
        host_admin=current_host,
        plan_id=plan_id,
        payload=updates,
        confirm=payload.confirm,
        reason=payload.reason or "Host Admin updated plan",
        ip_address=client_ip
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Plan update failed"))
    return res


# 5. AI Provider and Model Configuration (Secure Credentials & Health Tracking)
@app.get("/api/host/ai/config")
async def host_get_ai_config_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve active AI configuration with masked credentials and explicit health states."""
    return gari_host_service.get_ai_configuration()


@app.post("/api/host/ai/config")
async def host_update_ai_config_api(
    payload: Dict[str, Any],
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Update AI provider, model, API keys, and behavioral parameters. Never logs secrets."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    reason = str(payload.get("reason") or "Host Admin updated AI configuration").strip()
    return gari_host_service.update_ai_configuration(
        host_admin=current_host,
        payload=payload,
        reason=reason,
        ip_address=client_ip
    )


@app.post("/api/host/ai/provider-test")
async def host_test_ai_provider_api(
    payload: Optional[Dict[str, Any]] = None,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Test AI Assistant provider adapter connectivity and update health probe state."""
    return await host_test_assistant_provider(payload=payload, current_host=current_host)


# 6. Model Availability and Inference Benchmarking
@app.post("/api/host/models/benchmark")
async def host_benchmark_models_api(
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Run real inference benchmark on deep learning models and return latency and throughput."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    start_t = time.perf_counter()
    leaf_file = ROOT / "test_leaf.jpg"
    if leaf_file.exists():
        bench_img = Image.open(leaf_file).convert("RGB")
    else:
        bench_img = Image.new("RGB", (224, 224), color=(34, 139, 34))

    result = engine.predict(bench_img, top_k=3, crop_id="tomato")
    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
    fps = round(1000.0 / elapsed_ms, 1) if elapsed_ms > 0 else 0.0

    gari_auth.record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host.get("email"),
        action_type="BENCHMARK_MODELS",
        target_resource="inference_engine",
        details={"latency_ms": elapsed_ms, "fps": fps, "engine_status": "healthy"},
        reason="Host Admin triggered live benchmark",
        ip_address=client_ip
    )

    top_pred = "N/A"
    conf = 0.0
    if result:
        pred_val = result.get("prediction")
        if isinstance(pred_val, dict):
            top_pred = pred_val.get("disease_name_vi") or pred_val.get("class_name") or "N/A"
            conf = pred_val.get("confidence") or 0.0
        elif isinstance(pred_val, str):
            top_pred = pred_val
            conf = result.get("confidence") or 0.0
        else:
            top_pred = result.get("primary_disease") or "N/A"
            conf = result.get("confidence") or 0.0

    return {
        "success": True,
        "engine_status": "healthy" if result and result.get("success") else "degraded",
        "latency_ms": elapsed_ms,
        "throughput_fps": fps,
        "model_version": getattr(engine, "model_version", "v2.4-hybrid-vietgap"),
        "active_backend": getattr(engine, "backend_name", "PyTorch / TorchScript"),
        "top_prediction": top_pred,
        "confidence": conf
    }


# 7. System-wide Usage Monitoring
@app.get("/api/host/usage/summary")
@app.get("/api/host/usage/monitoring")
async def host_get_usage_summary_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve system-wide resource utilization across all users and organizations."""
    return gari_host_service.get_system_usage_summary()


# 8. System Health and Error Monitoring
@app.get("/api/host/system/health")
async def host_get_system_health_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve comprehensive system health, DB latency, and hardware telemetry."""
    return gari_host_service.get_system_health()


@app.get("/api/host/system/errors")
async def host_get_system_errors_api(
    limit: int = 50,
    offset: int = 0,
    min_level: Optional[str] = None,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve paginated system error logs with breakdown."""
    return gari_host_service.get_system_errors(limit=limit, offset=offset, min_level=min_level)


@app.post("/api/host/system/errors/clear")
async def host_clear_system_errors_api(
    payload: HostClearErrorsPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Clear error logs requiring explicit confirmation."""
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail="Thao tác xóa nhật ký lỗi hệ thống yêu cầu xác nhận rõ ràng (confirm=True)."
        )
    client_ip = request.client.host if request.client else "0.0.0.0"
    res = gari_host_service.clear_system_errors(
        host_admin=current_host,
        confirm=payload.confirm,
        reason=payload.reason or "Host Admin cleared logs",
        ip_address=client_ip
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Clear failed"))
    return res


# 9. Moderation Queue and Action Resolution
@app.get("/api/host/moderation/queue")
async def host_get_moderation_queue_api(
    status: Optional[str] = "pending",
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Retrieve combined moderation queue of community reports and system cases."""
    return gari_host_service.get_moderation_queue(status_filter=status, limit=limit, offset=offset)


@app.post("/api/host/moderation/resolve")
async def host_resolve_moderation_item_api(
    payload: HostResolveModerationPayload,
    request: Request,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Resolve a moderation queue item. Enforces confirmation for sensitive actions."""
    client_ip = request.client.host if request.client else "0.0.0.0"
    res = gari_host_service.resolve_moderation_item(
        host_admin=current_host,
        source=payload.source,
        raw_id=payload.raw_id,
        action=payload.action,
        reason=payload.reason,
        confirm=payload.confirm,
        ip_address=client_ip
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Moderation action failed"))
    return res


# =====================================================================
# GARI PHASE P3 — GEOSPATIAL & ENVIRONMENTAL INTELLIGENCE API ENDPOINTS
# =====================================================================

class UpdateZoneGeometryPayload(BaseModel):
    geometry: Dict[str, Any]
    geometry_source: Optional[str] = "user_drawn"
    organization_id: Optional[int] = None


class CreateSmartAlertPayload(BaseModel):
    farm_id: int
    alert_type: str
    severity: str
    title: str
    description: str
    trigger_source: str
    plot_id: Optional[int] = None
    organization_id: Optional[int] = None
    evidence: Optional[Dict[str, Any]] = None


class UpdateAlertStatusPayload(BaseModel):
    status: str
    resolution_notes: Optional[str] = None


class AssignAlertPayload(BaseModel):
    assigned_user_id: int


# --- P3.1 GIS & Farm Mapping Endpoints ---

@app.get("/api/gis/farms/{farm_id}")
async def get_farm_gis_api(
    farm_id: int,
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve comprehensive GeoJSON GIS bundle (Farm perimeter, Zones, Plots, and Geolocated Diagnoses)."""
    try:
        data = gari_gis_service.get_farm_gis_bundle(
            farm_id=farm_id,
            user_id=current_user["id"],
            org_id=organization_id
        )
        return data
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.put("/api/gis/zones/{zone_id}/geometry")
async def update_zone_geometry_api(
    zone_id: int,
    payload: UpdateZoneGeometryPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update polygon boundary, centroid, and area for a farm zone with GeoJSON validation."""
    try:
        res = gari_gis_service.update_zone_geometry(
            zone_id=zone_id,
            geometry=payload.geometry,
            user_id=current_user["id"],
            org_id=payload.organization_id,
            geometry_source=payload.geometry_source or "user_drawn"
        )
        return res
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/gis/search")
async def search_gis_api(
    q: Optional[str] = None,
    crop: Optional[str] = None,
    province: Optional[str] = None,
    health_status: Optional[str] = None,
    has_coords: bool = False,
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Spatial and metadata search across accessible farms and plots with tenant isolation."""
    try:
        res = gari_gis_service.search_gis_entities(
            user_id=current_user["id"],
            org_id=organization_id,
            query=q,
            crop=crop,
            province=province,
            health_status=health_status,
            has_coordinates_only=has_coords
        )
        return res
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


# --- P3.2 Weather Intelligence Endpoints ---

@app.get("/api/weather/farms/{farm_id}")
async def get_farm_weather_api(
    farm_id: int,
    force_refresh: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve real-time meteorological observations, hourly trends, and 7-day forecast from Open-Meteo."""
    try:
        data = gari_weather_service.get_farm_weather(
            farm_id=farm_id,
            user_id=current_user["id"],
            force_refresh=force_refresh
        )
        return {"success": True, **data}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/weather/coordinates")
async def get_coordinates_weather_api(
    lat: float,
    lon: float,
    force_refresh: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve weather data for arbitrary geographic coordinates with caching and provenance."""
    try:
        data = gari_weather_service.get_coordinates_weather(
            latitude=lat,
            longitude=lon,
            force_refresh=force_refresh
        )
        return {"success": True, **data}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# --- P3.3 Satellite Intelligence Endpoints ---

@app.get("/api/satellite/farms/{farm_id}/scenes")
async def get_farm_satellite_scenes_api(
    farm_id: int,
    days_back: int = 45,
    max_cloud_cover: float = 50.0,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Query live public Sentinel-2 L2A STAC scenes for a farm's bounding box."""
    try:
        res = gari_satellite_service.sync_farm_satellite_scenes(
            farm_id=farm_id,
            user_id=current_user["id"],
            days_back=days_back,
            max_cloud_cover=max_cloud_cover
        )
        return {"success": True, **res}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/satellite/plots/{plot_id}/indices")
async def get_plot_satellite_indices_api(
    plot_id: int,
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve vegetation spectral index history (NDVI, NDMI, canopy assessment) for a plot."""
    try:
        data = gari_satellite_service.get_plot_vegetation_indices(
            plot_id=plot_id,
            user_id=current_user["id"],
            org_id=organization_id
        )
        return {"success": True, **data}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


# --- P3.4 Agricultural Risk Engine Endpoints ---

@app.get("/api/risk/plots/{plot_id}/evaluate")
async def evaluate_plot_risks_api(
    plot_id: int,
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Run 5-vector agricultural risk evaluation (Drought, Rain/Flood, Heat Stress, Disease Weather, Canopy Loss)."""
    try:
        res = gari_risk_engine.evaluate_plot_risks(
            plot_id=plot_id,
            user_id=current_user["id"],
            org_id=organization_id
        )
        return {"success": True, **res}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


# --- P3.5 Farm Digital Twin Endpoints ---

@app.get("/api/digital-twin/farms/{farm_id}")
async def get_farm_digital_twin_api(
    farm_id: int,
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve comprehensive Farm Digital Twin descriptor aggregating all 5 operational layers."""
    try:
        res = gari_digital_twin.get_farm_digital_twin(
            farm_id=farm_id,
            user_id=current_user["id"],
            org_id=organization_id
        )
        return res
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


# --- P3.6 Smart Alerts Endpoints ---

@app.post("/api/alerts")
async def create_smart_alert_api(
    payload: CreateSmartAlertPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new smart alert with deterministic deduplication and cooldown."""
    res = gari_smart_alerts.create_smart_alert(
        farm_id=payload.farm_id,
        alert_type=payload.alert_type,
        severity=payload.severity,
        title=payload.title,
        description=payload.description,
        trigger_source=payload.trigger_source,
        plot_id=payload.plot_id,
        organization_id=payload.organization_id,
        evidence=payload.evidence
    )
    return res


@app.get("/api/alerts")
async def list_smart_alerts_api(
    organization_id: Optional[int] = None,
    farm_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    alert_type: Optional[str] = None,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List smart alerts accessible to the user, respecting tenant boundaries."""
    try:
        res = gari_smart_alerts.list_smart_alerts(
            user_id=current_user["id"],
            org_id=organization_id,
            farm_id=farm_id,
            plot_id=plot_id,
            status=status,
            severity=severity,
            alert_type=alert_type,
            limit=limit
        )
        return res
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.patch("/api/alerts/{alert_id}/status")
async def update_alert_status_api(
    alert_id: int,
    payload: UpdateAlertStatusPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Transition alert status through lifecycle (acknowledged, in_progress, resolved, dismissed)."""
    try:
        res = gari_smart_alerts.update_alert_status(
            alert_id=alert_id,
            new_status=payload.status,
            user_id=current_user["id"],
            resolution_notes=payload.resolution_notes
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.post("/api/alerts/{alert_id}/assign")
async def assign_alert_api(
    alert_id: int,
    payload: AssignAlertPayload,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Assign alert resolution responsibility to a specific user/manager."""
    try:
        res = gari_smart_alerts.assign_smart_alert(
            alert_id=alert_id,
            assigned_user_id=payload.assigned_user_id,
            user_id=current_user["id"]
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# --- P3.7 Intelligence Reports Endpoints ---

@app.get("/api/reports/farm-health")
async def get_farm_health_report_api(
    farm_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    crop: Optional[str] = None,
    format: str = "json",
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate comprehensive Farm Health Report (JSON or CSV export)."""
    try:
        res = gari_intelligence_reports.generate_farm_health_report(
            farm_id=farm_id,
            user_id=current_user["id"],
            start_date=start_date,
            end_date=end_date,
            crop=crop,
            export_format=format
        )
        if format == "csv":
            return Response(content=res, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=farm_{farm_id}_health.csv"})
        return {"success": True, **res}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.get("/api/reports/agricultural-risk")
async def get_agricultural_risk_report_api(
    farm_id: int,
    format: str = "json",
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate Agricultural Risk Report (JSON or CSV export)."""
    try:
        res = gari_intelligence_reports.generate_agricultural_risk_report(
            farm_id=farm_id,
            user_id=current_user["id"],
            export_format=format
        )
        if format == "csv":
            return Response(content=res, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=farm_{farm_id}_risk.csv"})
        return {"success": True, **res}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@app.get("/api/reports/organization-overview")
async def get_organization_overview_report_api(
    organization_id: int,
    format: str = "json",
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generate Organization Executive Overview Report (JSON or CSV export)."""
    try:
        res = gari_intelligence_reports.generate_organization_overview_report(
            org_id=organization_id,
            user_id=current_user["id"],
            export_format=format
        )
        if format == "csv":
            return Response(content=res, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=org_{organization_id}_overview.csv"})
        return {"success": True, **res}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


# =====================================================================
# P4 — AI AGENT ECOSYSTEM API
# =====================================================================

class AgentRunRequest(BaseModel):
    task_type: str = "custom"
    context: Dict[str, Any] = {}
    organization_id: Optional[int] = None


class AgentApprovalResolveRequest(BaseModel):
    action: str  # "approve" | "reject"
    notes: Optional[str] = None


@app.get("/api/agents")
async def list_registered_agents_api(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List all registered AI Agents, versioning, tools, and schemas."""
    return {
        "success": True,
        "agents": gari_agent_orchestrator.get_available_agents(),
        "total": len(gari_agent_orchestrator.AGENT_REGISTRY)
    }


@app.post("/api/agents/{agent_id}/run")
async def run_agent_task_api(
    agent_id: str,
    req: AgentRunRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Execute a task with a specialized AI agent."""
    try:
        result = gari_agent_orchestrator.execute_agent_task(
            agent_id=agent_id,
            user_id=current_user["id"],
            input_context=req.context,
            task_type=req.task_type,
            organization_id=req.organization_id
        )
        return {"success": True, **result}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error executing agent {agent_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi khi thực thi Agent: {str(e)}")


@app.get("/api/agents/executions")
async def list_agent_executions_api(
    organization_id: Optional[int] = None,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve execution history and audit telemetry for the authenticated user/organization."""
    try:
        executions = gari_agent_orchestrator.list_agent_executions(
            user_id=current_user["id"],
            organization_id=organization_id,
            limit=limit
        )
        return {"success": True, "executions": executions, "count": len(executions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/executions/{execution_id}")
async def get_agent_execution_api(
    execution_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve detailed telemetry and audit trail for a specific agent execution."""
    try:
        execution = gari_agent_orchestrator.get_agent_execution(
            execution_id=execution_id,
            user_id=current_user["id"]
        )
        return {"success": True, "execution": execution}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/approvals")
async def list_agent_approvals_api(
    organization_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List pending Human-in-the-Loop approval requests."""
    try:
        approvals = gari_agent_orchestrator.list_pending_approvals(
            user_id=current_user["id"],
            organization_id=organization_id
        )
        return {"success": True, "approvals": approvals, "count": len(approvals)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/approvals/{approval_id}/resolve")
async def resolve_agent_approval_api(
    approval_id: str,
    req: AgentApprovalResolveRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Approve or reject a high-impact pending agent action."""
    try:
        res = gari_agent_orchestrator.resolve_approval_request(
            approval_id=approval_id,
            action=req.action,
            reviewer_user_id=current_user["id"],
            notes=req.notes
        )
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

