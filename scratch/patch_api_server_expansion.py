import sys

code_to_insert = '''
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


@app.get("/api/host/experts/applications")
async def host_list_expert_applications_api(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """List expert qualification applications for administrative approval."""
    apps = gari_database.list_expert_applications(status=status, limit=limit, offset=offset)
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
    app_record = gari_database.get_expert_application(app_id)
    if not app_record:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đăng ký chuyên gia.")
    
    res = gari_database.review_expert_application(
        app_id=app_id,
        reviewer_id=current_host["id"],
        action=payload.action,
        admin_notes=payload.admin_notes or "",
        commission_rate=payload.commission_rate or 0.15
    )
    if not res:
        raise HTTPException(status_code=400, detail="Thao tác xét duyệt thất bại.")
    
    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type=f"expert_application_{payload.action.lower()}",
        target_resource=f"expert_application:{app_id}",
        details={"applicant_name": app_record.get("full_name"), "action": payload.action, "notes": payload.admin_notes},
        reason=f"Xét duyệt đơn chuyên gia: {payload.action}",
        outcome="success",
        ip_address=client_ip
    )
    return {"success": True, "message": f"Đã {payload.action} đơn đăng ký chuyên gia thành công.", "application": res}


@app.get("/api/host/experts")
async def host_list_expert_profiles_api(
    active_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """List approved agricultural experts in the platform."""
    experts = gari_database.list_expert_profiles(active_only=active_only, limit=limit, offset=offset)
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
    status_str = "active" if payload.is_active else "suspended"
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE expert_profiles SET status = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status_str, 1 if payload.is_active else 0, expert_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ chuyên gia.")
        conn.commit()

    record_host_audit(
        host_admin_id=current_host["id"],
        host_email=current_host["email"],
        action_type="expert_status_update",
        target_resource=f"expert_profile:{expert_id}",
        details={"is_active": payload.is_active, "status": status_str},
        reason=f"Cập nhật trạng thái chuyên gia ID {expert_id}",
        outcome="success",
        ip_address=client_ip
    )
    return {"success": True, "expert_id": expert_id, "is_active": payload.is_active, "status": status_str}


@app.get("/api/host/subscriptions/overview")
async def host_subscriptions_overview_api(
    current_host: Dict[str, Any] = Depends(get_current_host_admin)
):
    """Host inspection of global subscriptions, MRR, and plan allocations."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plan, status, count(*) as count 
            FROM subscriptions 
            GROUP BY plan, status
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
    result = engine.predict(dummy_img, top_k=3, crop_filter="Tomato")
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
    app_data = payload.model_dump()
    result = gari_database.create_expert_application(current_user["id"], app_data)
    if not result:
        raise HTTPException(status_code=400, detail="Không thể nộp đơn. Bạn có thể đã có đơn đang chờ duyệt.")
    return {
        "success": True,
        "message": "Đơn đăng ký chuyên gia đã được gửi thành công! Quản trị viên GARI sẽ thẩm định trong vòng 24-48 giờ.",
        "application_id": result["id"]
    }


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
    """Case queue for verified experts."""
    expert_id = current_expert["id"]
    cases = gari_database.list_expert_cases_for_expert(expert_id=expert_id, status=None, limit=limit, offset=offset)
    
    if filter_type == "assigned_to_me":
        cases = [c for c in cases if c.get("assigned_expert_id") == expert_id]
    elif filter_type == "unassigned":
        cases = [c for c in cases if not c.get("assigned_expert_id") and c.get("status") in ("Pending", "Chờ phản hồi", "Open")]
    elif filter_type == "resolved":
        cases = [c for c in cases if c.get("status") in ("Resolved", "Đã tư vấn", "Answered")]

    return {
        "success": True,
        "cases": cases,
        "total": len(cases),
        "filter": filter_type
    }


@app.post("/api/expert/cases/{case_id}/claim")
async def claim_expert_case_api(
    case_id: int,
    current_expert: Dict[str, Any] = Depends(get_current_expert_user)
):
    """Claim responsibility for an open diagnostic consultation case."""
    expert_name = current_expert.get("full_name") or current_expert.get("name") or "Chuyên gia GARI"
    claimed = gari_database.claim_expert_case(case_id, current_expert["id"], expert_name)
    if not claimed:
        raise HTTPException(status_code=400, detail="Không thể nhận ca bệnh này. Ca có thể đã được chuyên gia khác tiếp nhận.")
    
    return {"success": True, "message": "Tiếp nhận hồ sơ bệnh thành công!", "case": claimed}


@app.get("/api/expert/cases/{case_id}/messages")
async def get_case_messages_api(
    case_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Retrieve chat message thread for an expert case."""
    # Verify access: user must be case owner OR expert OR host admin
    case = gari_database.get_expert_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca bệnh.")
    
    is_owner = case.get("user_id") == current_user["id"]
    is_exp = bool(current_user.get("is_expert"))
    is_host = bool(current_user.get("is_host_admin"))

    if not (is_owner or is_exp or is_host):
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
    case = gari_database.get_expert_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca bệnh.")

    is_owner = case.get("user_id") == current_user["id"]
    is_exp = bool(current_user.get("is_expert"))
    is_host = bool(current_user.get("is_host_admin"))

    if not (is_owner or is_exp or is_host):
        raise HTTPException(status_code=403, detail="Bạn không có quyền gửi tin nhắn trong ca bệnh này.")

    sender_role = "expert" if (is_exp or is_host) else "farmer"
    msg = gari_database.add_expert_case_message(
        case_id=case_id,
        sender_id=current_user["id"],
        sender_role=sender_role,
        message=payload.message,
        is_prescription=payload.is_prescription,
        prescription_data=payload.prescription_data,
        attachments=payload.attachments
    )
    return {"success": True, "message_record": msg}


@app.post("/api/expert/cases/{case_id}/resolve")
async def resolve_expert_case_api(
    case_id: int,
    payload: ResolveExpertCasePayload,
    current_expert: Dict[str, Any] = Depends(get_current_expert_user)
):
    """Expert concludes the case with detailed prescription and instructions."""
    resolved = gari_database.resolve_expert_case(
        case_id=case_id,
        expert_id=current_expert["id"],
        resolution_notes=payload.resolution_notes,
        diagnosis_correction=payload.diagnosis_correction,
        prescription_data=payload.prescription_data
    )
    if not resolved:
        raise HTTPException(status_code=400, detail="Không thể hoàn tất ca tư vấn.")
    return {"success": True, "message": "Đã hoàn tất tư vấn ca bệnh và gửi đơn điều trị tới nông hộ!", "case": resolved}


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
'''

with open('api_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update gari_auth imports
old_imp = "from gari_auth import get_current_user, get_current_user_optional, get_current_admin_user, get_current_host_admin, record_host_audit"
new_imp = "from gari_auth import get_current_user, get_current_user_optional, get_current_admin_user, get_current_host_admin, get_current_expert_user, record_host_audit"

if old_imp in content:
    content = content.replace(old_imp, new_imp)
    print("Updated gari_auth import statement.")
else:
    print("Warning: old import statement not found directly.")

# 2. Add code before "if __name__ == '__main__':"
target_split = 'if __name__ == "__main__":'
if target_split in content:
    parts = content.split(target_split)
    new_content = parts[0] + code_to_insert + "\n\n" + target_split + parts[1]
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully patched api_server.py with expansion endpoints!")
else:
    print("Error: Could not find target split in api_server.py")
