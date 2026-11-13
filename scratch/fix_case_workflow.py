# 1. Add get_expert_case to gari_database.py
with open('gari_database.py', 'r', encoding='utf-8') as f:
    db_text = f.read()

target_db = "def claim_expert_case("
func_db = """def get_expert_case(case_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


"""

if "def get_expert_case(" not in db_text:
    db_text = db_text.replace(target_db, func_db + target_db, 1)
    with open('gari_database.py', 'w', encoding='utf-8') as f:
        f.write(db_text)
    print("Added get_expert_case to gari_database.py")

# 2. Update api_server.py case endpoints
with open('api_server.py', 'r', encoding='utf-8') as f:
    api_text = f.read()

old_endpoints = '''@app.get("/api/expert/portal/cases")
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
    )'''

new_endpoints = '''@app.get("/api/expert/portal/cases")
async def list_expert_portal_cases_api(
    filter_type: str = "all",  # "all", "assigned_to_me", "unassigned", "resolved"
    limit: int = 50,
    offset: int = 0,
    current_expert: Dict[str, Any] = Depends(get_current_expert_user)
):
    """Case queue for verified experts."""
    expert_id = current_expert["id"]
    cases = gari_database.list_expert_cases_for_expert(expert_user_id=expert_id, status=None)
    
    if filter_type == "assigned_to_me":
        cases = [c for c in cases if c.get("assigned_expert_id") == expert_id]
    elif filter_type == "unassigned":
        cases = [c for c in cases if not c.get("assigned_expert_id") and c.get("status") in ("Pending", "Chờ phản hồi", "Open", "Submitted", "under_review")]
    elif filter_type == "resolved":
        cases = [c for c in cases if c.get("status") in ("Resolved", "Đã tư vấn", "Answered", "resolved")]

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
    case = gari_database.get_expert_case(case_id)
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
    case = gari_database.get_expert_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca bệnh.")

    is_owner = case.get("user_id") == current_user["id"]
    is_exp = bool(current_user.get("is_expert"))
    is_host = bool(current_user.get("is_host_admin"))

    if not (is_owner or is_exp or is_host):
        raise HTTPException(status_code=403, detail="Bạn không có quyền gửi tin nhắn trong ca bệnh này.")

    sender_role = "expert" if (is_exp or is_host) else "farmer"
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


@app.post("/api/expert/cases/{case_id}/resolve")
async def resolve_expert_case_api(
    case_id: int,
    payload: ResolveExpertCasePayload,
    current_expert: Dict[str, Any] = Depends(get_current_expert_user)
):
    """Expert concludes the case with detailed prescription and instructions."""
    notes = payload.resolution_notes
    if payload.prescription_data:
        import json
        notes += f"\\n\\n[ĐƠN THUỐC PHÁC ĐỒ]: {json.dumps(payload.prescription_data, ensure_ascii=False)}"
    if payload.diagnosis_correction:
        notes += f"\\n[CHẨN ĐOÁN XÁC NHẬN]: {payload.diagnosis_correction}"

    resolved = gari_database.resolve_expert_case(
        case_id=case_id,
        expert_user_id=current_expert["id"],
        resolution_notes=notes
    )'''

# Normalize and replace
api_norm = api_text.replace('\r\n', '\n')
old_norm = old_endpoints.replace('\r\n', '\n')
new_norm = new_endpoints.replace('\r\n', '\n')

if old_norm in api_norm:
    api_norm = api_norm.replace(old_norm, new_norm, 1)
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(api_norm)
    print("Updated expert portal routes in api_server.py")
else:
    print("Old endpoints not found in api_server.py")
