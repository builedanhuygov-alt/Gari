from pathlib import Path

path = Path("gari_auth.py")
content = path.read_text(encoding="utf-8")

# 1. Update get_user_by_id SELECT statement
old_get_user = """def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    \"\"\"Retrieve user dictionary by ID.\"\"\"
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            \"\"\"
            SELECT id, full_name, name, email, phone, account_type, is_admin,
                   is_host_admin, is_expert, is_active, moderation_status, feature_restrictions,
                   moderation_reason, moderation_updated_at, created_at
            FROM users WHERE id = ?
            \"\"\",
            (user_id,)
        )"""

new_get_user = """def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    \"\"\"Retrieve user dictionary by ID.\"\"\"
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            \"\"\"
            SELECT id, full_name, name, email, phone, address, province, avatar_url, bio,
                   account_type, is_admin, is_host_admin, is_expert, is_active, moderation_status,
                   feature_restrictions, moderation_reason, moderation_updated_at, firebase_uid, created_at, updated_at
            FROM users WHERE id = ?
            \"\"\",
            (user_id,)
        )"""

# 2. Update validate_session local DB SELECT statement
old_validate_session = """        cursor.execute(
            \"\"\"
            SELECT s.token, s.expires_at, u.id, u.full_name, u.name, u.email, u.phone, u.account_type, u.is_admin, u.is_host_admin, u.is_expert, u.is_active, u.moderation_status, u.feature_restrictions, u.moderation_reason, u.created_at
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
            \"\"\",
            (token, now_iso)
        )"""

new_validate_session = """        cursor.execute(
            \"\"\"
            SELECT s.token, s.expires_at, u.id, u.full_name, u.name, u.email, u.phone, u.address, u.province,
                   u.avatar_url, u.bio, u.account_type, u.is_admin, u.is_host_admin, u.is_expert, u.is_active,
                   u.moderation_status, u.feature_restrictions, u.moderation_reason, u.firebase_uid, u.created_at, u.updated_at
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
            \"\"\",
            (token, now_iso)
        )"""

content = content.replace(old_get_user.replace("\r\n", "\n"), new_get_user.replace("\r\n", "\n"))
content = content.replace(old_get_user, new_get_user)

content = content.replace(old_validate_session.replace("\r\n", "\n"), new_validate_session.replace("\r\n", "\n"))
content = content.replace(old_validate_session, new_validate_session)

# 3. Append Centralized Profile & RBAC helpers
helpers = """

# -----------------------------------------------------------------------------
# Module 01: Centralized User Profile & Enterprise RBAC Architecture
# -----------------------------------------------------------------------------

FORBIDDEN_PROFILE_UPDATE_FIELDS = {
    "is_admin",
    "is_host_admin",
    "is_expert",
    "account_type",
    "moderation_status",
    "feature_restrictions",
    "is_active",
    "id",
    "email",
    "password_hash",
    "firebase_uid",
    "role",
    "system_role",
    "system_roles"
}


def get_centralized_user_profile(user_id: int) -> Dict[str, Any]:
    \"\"\"
    Centralized, authoritative user profile model following the 5-layer architecture:
    1. Identity (Firebase UID / session provider / email)
    2. User Demographics & Profile (name, phone, address, province, avatar, bio)
    3. Canonical Account Type (single active account type)
    4. System Roles (host_admin, admin, expert, farmer)
    5. Subscription Status (Entitlements, quotas, VIP)
    6. Organization Memberships (B2B RBAC & tenant roles)
    \"\"\"
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            \"\"\"
            SELECT id, email, full_name, name, phone, address, province, avatar_url, bio,
                   account_type, is_admin, is_host_admin, is_expert, is_active,
                   moderation_status, feature_restrictions, moderation_reason,
                   firebase_uid, created_at, updated_at
            FROM users WHERE id = ?
            \"\"\",
            (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")
        user = dict(row)

    import gari_b2b
    import gari_plans

    # 1. Identity
    email = user.get("email") or ""
    firebase_uid = user.get("firebase_uid")
    display_name = user.get("full_name") or user.get("name") or (email.split("@")[0] if email else "Nông dân")
    identity = {
        "uid": firebase_uid or f"user_{user['id']}",
        "firebase_uid": firebase_uid,
        "email": email,
        "email_verified": bool(firebase_uid),
        "display_name": display_name,
        "photo_url": user.get("avatar_url"),
        "provider_id": "firebase" if firebase_uid else "password"
    }

    # 2. Demographic Profile
    profile = {
        "id": user["id"],
        "full_name": display_name,
        "name": user.get("name") or display_name,
        "phone": user.get("phone"),
        "address": user.get("address"),
        "province": user.get("province"),
        "avatar_url": user.get("avatar_url"),
        "bio": user.get("bio"),
        "created_at": user.get("created_at"),
        "updated_at": user.get("updated_at")
    }

    # 3. Canonical Single Active Account Type
    canonical_acc_type = normalize_account_type(user.get("account_type")) or ACCOUNT_TYPE_FARMER
    acc_config = ACCOUNT_TYPE_CONFIG.get(canonical_acc_type, {
        "key": canonical_acc_type,
        "label": canonical_acc_type.capitalize(),
        "description": ""
    })
    account_type_info = {
        "key": canonical_acc_type,
        "label": acc_config["label"],
        "description": acc_config["description"]
    }

    # 4. System Roles
    is_host_admin = bool(user.get("is_host_admin"))
    is_admin = bool(user.get("is_admin"))
    is_expert = bool(user.get("is_expert"))
    if is_host_admin:
        primary_role = "host_admin"
        primary_label = "Quản trị viên Máy chủ cấp cao"
    elif is_admin:
        primary_role = "admin"
        primary_label = "Quản trị viên Nền tảng"
    elif is_expert:
        primary_role = "expert"
        primary_label = "Chuyên gia BVTV"
    else:
        primary_role = canonical_acc_type
        primary_label = acc_config["label"]

    system_roles = {
        "primary_role": primary_role,
        "primary_label": primary_label,
        "is_host_admin": is_host_admin,
        "is_admin": is_admin,
        "is_expert": is_expert,
        "is_active": bool(user.get("is_active", 1)),
        "moderation_status": user.get("moderation_status") or "clean",
        "feature_restrictions": user.get("feature_restrictions") or ""
    }

    # 5. Subscription Status & Entitlements
    entitlement = gari_plans.resolve_user_entitlement(user)
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

    # 6. Organization Memberships
    org_list = gari_b2b.get_user_organizations(user["id"], include_test=False)
    memberships = []
    for org in org_list:
        org_role = org.get("role", "member")
        memberships.append({
            "org_id": org.get("id"),
            "org_name": org.get("name"),
            "role": org_role,
            "status": org.get("status", "active"),
            "plan_id": org.get("plan_id", "pilot"),
            "permissions": sorted(gari_b2b.ROLE_PERMISSIONS.get(org_role, set()))
        })

    return {
        "success": True,
        "identity": identity,
        "profile": profile,
        "account_type": account_type_info,
        "system_roles": system_roles,
        "system_role": {"is_admin": is_admin, "role": primary_role},
        "subscription": subscription,
        "organizations": memberships,
        "has_organizations": len(memberships) > 0,
        "raw_user": user
    }


def update_user_profile(
    user_id: int,
    updates: Dict[str, Any],
    actor_id: Optional[int] = None
) -> Dict[str, Any]:
    \"\"\"
    Safely update demographic profile fields for a user.
    Strictly forbids self-assignment or privilege escalation attempts.
    \"\"\"
    if not isinstance(updates, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dữ liệu cập nhật không hợp lệ."
        )

    # Check for unauthorized privilege escalation keys
    attempted_forbidden = [k for k in updates.keys() if k.lower() in FORBIDDEN_PROFILE_UPDATE_FIELDS]
    if attempted_forbidden:
        logger.warning(
            "Security Alert: User %s attempted privilege escalation on fields %s",
            user_id, attempted_forbidden
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không được phép tự nâng cấp quyền hệ thống hoặc thay đổi thuộc tính bảo mật ({', '.join(attempted_forbidden)}) qua API thông tin cá nhân."
        )

    allowed_fields = {
        "full_name": str,
        "name": str,
        "phone": str,
        "address": str,
        "province": str,
        "avatar_url": str,
        "bio": str
    }

    set_clauses = []
    params = []

    for field in allowed_fields:
        if field in updates:
            val = updates[field]
            if val is not None:
                val = str(val).strip()
            if field == "full_name" and val:
                set_clauses.append("full_name = ?")
                params.append(val)
                if "name" not in updates:
                    set_clauses.append("name = ?")
                    params.append(val)
            elif field != "name":
                set_clauses.append(f"{field} = ?")
                params.append(val)

    if not set_clauses:
        return get_centralized_user_profile(user_id)

    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
    params.append(user_id)

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        sql = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
        cursor.execute(sql, tuple(params))
        conn.commit()

    return get_centralized_user_profile(user_id)


def require_org_role(*allowed_roles: str, org_id_param: str = "org_id"):
    \"\"\"
    FastAPI dependency factory enforcing tenant-isolated organization role checks.
    Supports single role or multiple permitted roles (e.g., 'owner', 'admin').
    Extracts org_id from path parameters, query parameters, or 'X-Organization-Id' header.
    Host Admins bypass tenant checks for platform administration.
    \"\"\"
    permitted = {r.lower() for r in allowed_roles}

    async def dependency(request: Request, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        # Host Admin bypass
        if current_user.get("is_host_admin"):
            return {"user": current_user, "role": "host_admin", "org_id": None}

        # Extract org_id from path params or query params or header
        raw_org_id = (
            request.path_params.get(org_id_param)
            or request.query_params.get(org_id_param)
            or request.headers.get("X-Organization-Id")
        )
        if not raw_org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Thiếu định danh tổ chức ({org_id_param})."
            )

        try:
            org_id = int(raw_org_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Định danh tổ chức không hợp lệ."
            )

        import gari_b2b
        role = gari_b2b.get_member_role(org_id, current_user["id"])
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Truy cập bị từ chối: Bạn không phải thành viên của tổ chức này."
            )

        if permitted and role not in permitted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Truy cập bị từ chối: Vai trò '{role}' không có quyền thực hiện thao tác này. Yêu cầu: {', '.join(sorted(permitted))}."
            )

        return {"user": current_user, "role": role, "org_id": org_id}

    return dependency
"""

if "def get_centralized_user_profile" not in content:
    content += helpers

path.write_text(content, encoding="utf-8")
print("gari_auth.py patched with centralized profile & RBAC dependencies.")
