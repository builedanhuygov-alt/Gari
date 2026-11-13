with open('api_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import gari_assistant
if "import gari_assistant" not in content:
    content = content.replace("import gari_firebase\n", "import gari_firebase\nimport gari_assistant\n", 1)
    print("Added import gari_assistant")

# 2. Add assistant endpoints after copilot
copilot_end = """    return {"success": True, "task": task, "message": "Đã thêm công việc vào Lịch canh tác thành công!"}"""

assistant_endpoints = """    return {"success": True, "task": task, "message": "Đã thêm công việc vào Lịch canh tác thành công!"}


# -----------------------------------------------------------------------------
# GARI Plant Health Assistant & AI Disease Explainer API
# -----------------------------------------------------------------------------

@app.get("/api/assistant/status")
async def assistant_get_status():
    \"\"\"Retrieve public status and provider readiness of Plant Health Assistant.\"\"\"
    return gari_assistant.get_public_assistant_status()


@app.post("/api/assistant/chat")
async def assistant_chat_message(
    payload: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    \"\"\"Process multi-turn agronomic disease explainer chat bound to diagnosis record.\"\"\"
    user_id = current_user["id"] if current_user else 1
    diag_id = payload.get("diagnosis_id")
    if not diag_id:
        raise HTTPException(status_code=400, detail="Thiếu diagnosis_id cho phiên giải thích bệnh học.")
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
    return res


@app.get("/api/assistant/history/{diagnosis_id}")
async def assistant_get_history(
    diagnosis_id: int,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    \"\"\"Retrieve conversation history for a given diagnosis.\"\"\"
    user_id = current_user["id"] if current_user else 1
    history = gari_assistant.PlantHealthAssistantService.get_history(user_id=user_id, diagnosis_id=diagnosis_id)
    return {"success": True, "history": history}


@app.post("/api/assistant/action/confirm")
async def assistant_confirm_action(
    payload: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    \"\"\"Explicit user confirmation to convert an Assistant action draft into a persistent cultivation task.\"\"\"
    user_id = current_user["id"] if current_user else 1
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
    return {"success": True, "task": task, "message": "Đã thêm công việc vào Lịch canh tác thành công!"}"""

if copilot_end in content and "/api/assistant/chat" not in content:
    content = content.replace(copilot_end, assistant_endpoints, 1)
    print("Added assistant endpoints")

# 3. Add field observation parameters to predict function
old_predict_sig = """    notes: Optional[str] = Form(None),
    consent_store_image: bool = Form(False),"""

new_predict_sig = """    notes: Optional[str] = Form(None),
    growth_stage: Optional[str] = Form(None),
    user_symptoms: Optional[str] = Form(None),
    field_conditions: Optional[str] = Form(None),
    image_references: Optional[str] = Form(None),
    consent_store_image: bool = Form(False),"""

if old_predict_sig in content:
    content = content.replace(old_predict_sig, new_predict_sig, 1)
    print("Added field observation params to predict signature")

# 4. Pass field observation params into save_diagnosis call
old_diag_save = """                "user_notes": notes or ""
            }, user_id=user_id)"""

new_diag_save = """                "user_notes": notes or "",
                "growth_stage": growth_stage,
                "user_symptoms": user_symptoms,
                "field_conditions": field_conditions,
                "image_references": image_references
            }, user_id=user_id)"""

if old_diag_save in content:
    content = content.replace(old_diag_save, new_diag_save, 1)
    print("Passed field observation params to save_diagnosis")

with open('api_server.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print("Done updating api_server.py")
