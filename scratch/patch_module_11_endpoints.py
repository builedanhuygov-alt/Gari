"""
Patch api_server.py with Module 11 Entitlement hooks and Subscription endpoints.
"""

import sys

def apply_patch():
    with open("api_server.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Hook in add_farm
    farm_target = '''    try:
        farm = gari_farm_management.create_farm_ext(payload, user_id=current_user["id"], org_id=payload.get("organization_id"))
        return {"success": True, "farm": farm}
    except PermissionError as pe:'''
    
    farm_replacement = '''    try:
        gari_entitlements.enforce_entitlement(current_user["id"], "max_farms", org_id=payload.get("organization_id"))
        farm = gari_farm_management.create_farm_ext(payload, user_id=current_user["id"], org_id=payload.get("organization_id"))
        return {"success": True, "farm": farm}
    except gari_entitlements.EntitlementExceededError as ee:
        raise HTTPException(status_code=403, detail={"error": "entitlement_exceeded", "message": ee.message, "upgrade": ee.upgrade_data})
    except PermissionError as pe:'''

    if farm_target in content:
        content = content.replace(farm_target, farm_replacement, 1)
        print("Hooked add_farm entitlement.")
    else:
        print("Warning: farm_target not found.")

    # 2. Hook in create_plot_api
    plot_target = '''    try:
        plot = gari_farm_management.create_plot_ext(payload, user_id=current_user["id"], org_id=payload.get("organization_id"))
        return {"success": True, "plot": plot}
    except PermissionError as pe:'''

    plot_replacement = '''    try:
        gari_entitlements.enforce_entitlement(current_user["id"], "max_plots", org_id=payload.get("organization_id"))
        plot = gari_farm_management.create_plot_ext(payload, user_id=current_user["id"], org_id=payload.get("organization_id"))
        return {"success": True, "plot": plot}
    except gari_entitlements.EntitlementExceededError as ee:
        raise HTTPException(status_code=403, detail={"error": "entitlement_exceeded", "message": ee.message, "upgrade": ee.upgrade_data})
    except PermissionError as pe:'''

    if plot_target in content:
        content = content.replace(plot_target, plot_replacement, 1)
        print("Hooked create_plot_api entitlement.")
    else:
        print("Warning: plot_target not found.")

    # 3. Hook in add_organization_member_api
    member_target = '''    try:
        new_m = gari_b2b.add_member_by_email('''

    member_replacement = '''    try:
        gari_entitlements.enforce_entitlement(current_user["id"], "organization_seats", org_id=org_id)
        new_m = gari_b2b.add_member_by_email('''

    if member_target in content:
        content = content.replace(member_target, member_replacement, 1)
        print("Hooked add_organization_member_api entitlement.")
    else:
        print("Warning: member_target not found.")

    # 4. Hook in assistant_chat_message
    chat_target = '''    user_id = current_user["id"] if current_user else 1
    diag_id = payload.get("diagnosis_id")'''

    chat_replacement = '''    user_id = current_user["id"] if current_user else 1
    if current_user:
        try:
            gari_entitlements.enforce_entitlement(current_user["id"], "ai_usage")
        except gari_entitlements.EntitlementExceededError as ee:
            raise HTTPException(status_code=403, detail={"error": "entitlement_exceeded", "message": ee.message, "upgrade": ee.upgrade_data})
    diag_id = payload.get("diagnosis_id")'''

    if chat_target in content:
        content = content.replace(chat_target, chat_replacement, 1)
        print("Hooked assistant_chat_message entitlement.")
    else:
        print("Warning: chat_target not found.")

    # Also record AI usage after assistant generation
    chat_record_target = '''    gari_assistant.save_chat_turn(
        user_id=user_id,
        diagnosis_id=diag_id,
        user_message=user_q,
        assistant_reply=reply,
        metadata={"model": meta.get("model", "qwen-local"), "citations": citations}
    )'''

    chat_record_replacement = '''    gari_assistant.save_chat_turn(
        user_id=user_id,
        diagnosis_id=diag_id,
        user_message=user_q,
        assistant_reply=reply,
        metadata={"model": meta.get("model", "qwen-local"), "citations": citations}
    )
    if current_user:
        gari_entitlements.record_usage(current_user["id"], "ai_usage", 1.0)'''

    if chat_record_target in content:
        content = content.replace(chat_record_target, chat_record_replacement, 1)
        print("Hooked assistant AI usage recording.")
    else:
        print("Warning: chat_record_target not found.")

    # 5. Hook in create_expert_case
    expert_target = '''    user_id = current_user["id"] if current_user else 1
    try:
        case = gari_experts.create_consultation_case(user_id=user_id, data=payload)
        return {"success": True, "case": case}'''

    expert_replacement = '''    user_id = current_user["id"] if current_user else 1
    if current_user:
        try:
            gari_entitlements.enforce_entitlement(current_user["id"], "expert_consultations")
        except gari_entitlements.EntitlementExceededError as ee:
            raise HTTPException(status_code=403, detail={"error": "entitlement_exceeded", "message": ee.message, "upgrade": ee.upgrade_data})
    try:
        case = gari_experts.create_consultation_case(user_id=user_id, data=payload)
        if current_user:
            gari_entitlements.record_usage(current_user["id"], "expert_consultations", 1.0)
        return {"success": True, "case": case}'''

    if expert_target in content:
        content = content.replace(expert_target, expert_replacement, 1)
        print("Hooked create_expert_case entitlement.")
    else:
        print("Warning: expert_target not found.")

    # 6. Append Module 11 Subscriptions & Usage API Routes at bottom
    endpoints_code = '''

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
'''

    content += endpoints_code
    with open("api_server.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully patched api_server.py with Module 11 Subscriptions & Entitlements.")

if __name__ == "__main__":
    apply_patch()
