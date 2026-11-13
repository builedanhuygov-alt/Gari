from pathlib import Path

path = Path("api_server.py")
content = path.read_text(encoding="utf-8")

# 1. Update assistant_chat_message in api_server.py to handle 403 / 404 cleanly
old_chat_endpoint = '''    res = gari_assistant.PlantHealthAssistantService.process_chat(
        user_id=user_id,
        diagnosis_id=int(diag_id),
        message=message,
        conversation_history=conversation_history,
        field_context=field_context,
        deep_dive=deep_dive
    )
    return res'''

new_chat_endpoint = '''    res = gari_assistant.PlantHealthAssistantService.process_chat(
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
    return res'''

content = content.replace(old_chat_endpoint, new_chat_endpoint)

# 2. Add Host Assistant Management endpoints and Expert Escalate endpoint
host_endpoints_code = '''

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
        host_user_id=current_host["id"],
        action="UPDATE_ASSISTANT_CONFIG",
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
'''

content = content + host_endpoints_code

path.write_text(content, encoding="utf-8")
print("api_server.py patched for Module 03.")
