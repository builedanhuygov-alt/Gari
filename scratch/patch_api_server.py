from pathlib import Path

path = Path("api_server.py")
content = path.read_text(encoding="utf-8")

# 1. Add FirebaseLoginPayload model after LoginPayload
old_login_payload = """class LoginPayload(BaseModel):
    email: str
    password: str
    remember_me: Optional[bool] = False"""

new_login_payload = """class LoginPayload(BaseModel):
    email: str
    password: str
    remember_me: Optional[bool] = False


class FirebaseLoginPayload(BaseModel):
    id_token: str
    remember_me: Optional[bool] = False


class ProfileUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    province: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None"""

content = content.replace(old_login_payload.replace("\r\n", "\n"), new_login_payload.replace("\r\n", "\n"))
content = content.replace(old_login_payload, new_login_payload)

# 2. Add /api/auth/firebase-login right after get_firebase_status
old_fb_status = """    return {
        "success": True,
        "admin_initialized": admin_ready,
        "client_configured": client_ready,
        "app_env": os.getenv("APP_ENV", "development"),
        "message": "Firebase sẵn sàng" if (admin_ready and client_ready) else "Firebase Auth cần cấu hình khóa Firebase trong môi trường hoặc tệp dịch vụ để bật xác thực trực tiếp."
    }"""

new_fb_login_code = """    return {
        "success": True,
        "admin_initialized": admin_ready,
        "client_configured": client_ready,
        "app_env": os.getenv("APP_ENV", "development"),
        "message": "Firebase sẵn sàng" if (admin_ready and client_ready) else "Firebase Auth cần cấu hình khóa Firebase trong môi trường hoặc tệp dịch vụ để bật xác thực trực tiếp."
    }


@app.post("/api/auth/firebase-login")
async def firebase_login_endpoint(payload: FirebaseLoginPayload, request: Request, response: Response):
    \"\"\"
    Authenticate user using a cryptographically verified Firebase ID token.
    Synchronizes user to internal SQLite database, issues a secure internal session token,
    and sets an HttpOnly cookie for session persistence.
    \"\"\"
    import gari_firebase
    fb_data = gari_firebase.verify_firebase_id_token(payload.id_token)
    if not fb_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token không hợp lệ hoặc đã hết hạn."
        )

    user = gari_firebase.get_or_sync_firebase_user(fb_data)
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
        secure=False,
        max_age=max_age_seconds,
        path="/"
    )

    profile = gari_auth.get_centralized_user_profile(user["id"])
    return {
        "success": True,
        "message": "Đăng nhập Firebase thành công!",
        "token": token,
        "user": profile
    }"""

content = content.replace(old_fb_status.replace("\r\n", "\n"), new_fb_login_code.replace("\r\n", "\n"))
content = content.replace(old_fb_status, new_fb_login_code)

# 3. Replace @app.get("/api/user/profile") implementation with centralized user profile and add PATCH/PUT endpoints
old_profile_func = """@app.get("/api/user/profile")
async def get_user_profile_separated(current_user: Dict[str, Any] = Depends(get_current_user)):
    \"\"\"
    Authoritative separated profile following 5-layer model:
    1. Identity (Firebase UID / session token)
    2. User Profile (Demographics)
    3. Subscription Status (Entitlements & Quotas)
    4. Organization Memberships (B2B RBAC)
    5. System Roles
    \"\"\"
    entitlement = gari_plans.resolve_user_entitlement(current_user)
    orgs = gari_b2b.get_user_organizations(current_user["id"], include_test=False)

    # 1. Identity
    identity = {
        "uid": current_user.get("firebase_uid") or f"user_{current_user['id']}",
        "firebase_uid": current_user.get("firebase_uid"),
        "email": current_user.get("email"),
        "email_verified": bool(current_user.get("is_verified", False)),
        "display_name": current_user.get("full_name") or current_user.get("name") or (current_user.get("email", "").split("@")[0] if current_user.get("email") else "Nông dân"),
        "photo_url": current_user.get("avatar_url"),
        "provider_id": "firebase" if current_user.get("firebase_uid") else "password"
    }

    # 2. Profile
    profile = {
        "id": current_user["id"],
        "full_name": current_user.get("full_name") or current_user.get("name"),
        "phone": current_user.get("phone"),
        "address": current_user.get("address"),
        "province": current_user.get("province"),
        "created_at": current_user.get("created_at"),
        "updated_at": current_user.get("updated_at")
    }

    # 3. Subscription Status
    is_vip = bool(entitlement.get("has_vip_models"))
    plan_id = entitlement.get("plan_id", "free")
    plan_normalized = "pro" if plan_id in ("pro", "personal") else plan_id
    subscription = {
        "plan": plan_normalized,
        "plan_name": "Cá nhân Pro" if plan_normalized == "pro" else entitlement.get("plan_name", "Miễn phí"),
        "status": entitlement.get("subscription_status", "active"),
        "is_active": entitlement.get("is_active", True),
        "is_vip": is_vip,
        "has_vip_models": is_vip,
        "can_create_organization": entitlement.get("can_create_organization", False),
        "quota_limit": entitlement.get("quota_limit", 5),
        "current_period_end": entitlement.get("current_period_end")
    }

    # 4. Organization Memberships
    memberships = []
    for org in orgs:
        memberships.append({
            "org_id": org.get("id"),
            "org_name": org.get("name"),
            "role": org.get("role", "member"),
            "status": org.get("status", "active"),
            "plan_id": org.get("plan_id", "pilot")
        })

    # 5. System Roles
    system_role = {
        "is_admin": bool(current_user.get("is_admin", False)),
        "role": current_user.get("role", "admin" if current_user.get("is_admin") else "user")
    }

    return {
        "success": True,
        "identity": identity,
        "profile": profile,
        "subscription": subscription,
        "organizations": memberships,
        "system_role": system_role,
        "raw_user": dict(current_user)
    }"""

new_profile_func = """@app.get("/api/user/profile")
@app.get("/api/auth/profile")
async def get_user_profile_api(current_user: Dict[str, Any] = Depends(get_current_user)):
    \"\"\"
    Authoritative centralized user profile following the 5-layer model:
    Identity, Profile, Canonical Account Type, System Roles, Subscription, Organizations.
    \"\"\"
    return gari_auth.get_centralized_user_profile(current_user["id"])


@app.patch("/api/auth/profile")
@app.put("/api/user/profile")
async def update_user_profile_api(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    \"\"\"
    Safely update user profile information.
    Strictly forbids self-assignment of privileged roles (is_admin, is_host_admin, is_expert, account_type).
    \"\"\"
    return gari_auth.update_user_profile(
        user_id=current_user["id"],
        updates=payload,
        actor_id=current_user["id"]
    )"""

content = content.replace(old_profile_func.replace("\r\n", "\n"), new_profile_func.replace("\r\n", "\n"))
content = content.replace(old_profile_func, new_profile_func)

# 4. Fix season-report endpoints to require authentication and verify farm ownership
old_season_reports = """@app.get("/api/farms/{farm_id}/season-report")
async def get_farm_season_report_json(
    farm_id: int,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    \"\"\"
    Get consolidated seasonal management, task adherence, and disease report as JSON.
    Strictly isolated by user ownership.
    \"\"\"
    user_id = current_user["id"] if current_user else 1
    report = gari_database.generate_farm_season_report(farm_id, user_id=user_id)
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền truy cập.")
    return {"success": True, "report": report}


@app.get("/api/farms/{farm_id}/export-season-report", response_class=HTMLResponse)
async def export_farm_season_report_html(
    farm_id: int,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    \"\"\"
    Render executive printable VietGAP Seasonal Cultivation Journal with digital audit hash.
    Can be printed or saved directly to PDF from browser.
    \"\"\"
    user_id = current_user["id"] if current_user else 1
    report = gari_database.generate_farm_season_report(farm_id, user_id=user_id)
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền truy cập.")
    html_content = gari_database.render_farm_season_report_html(report)
    return HTMLResponse(content=html_content)"""

new_season_reports = """@app.get("/api/farms/{farm_id}/season-report")
async def get_farm_season_report_json(
    farm_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    \"\"\"
    Get consolidated seasonal management, task adherence, and disease report as JSON.
    Strictly isolated by user ownership and tenant boundaries.
    \"\"\"
    user_id = current_user["id"]
    farm = gari_database.get_farm(farm_id, user_id=user_id)
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
    \"\"\"
    Render executive printable VietGAP Seasonal Cultivation Journal with digital audit hash.
    Strictly isolated by user ownership and tenant boundaries.
    \"\"\"
    user_id = current_user["id"]
    farm = gari_database.get_farm(farm_id, user_id=user_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Không tìm thấy nông trại hoặc bạn không có quyền truy cập.")
    report = gari_database.generate_farm_season_report(farm_id, user_id=user_id)
    if not report:
        raise HTTPException(status_code=404, detail="Không tìm thấy dữ liệu báo cáo mùa vụ.")
    html_content = gari_database.render_farm_season_report_html(report)
    return HTMLResponse(content=html_content)"""

content = content.replace(old_season_reports.replace("\r\n", "\n"), new_season_reports.replace("\r\n", "\n"))
content = content.replace(old_season_reports, new_season_reports)

path.write_text(content, encoding="utf-8")
print("api_server.py patched successfully.")
