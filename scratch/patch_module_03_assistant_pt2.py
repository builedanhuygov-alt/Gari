import re
from pathlib import Path

path = Path("gari_assistant.py")
content = path.read_text(encoding="utf-8")

# 1. Update build_agronomic_system_prompt signature and prompt template
old_prompt_func = '''def build_agronomic_system_prompt(diagnosis: Dict[str, Any], field_context: Optional[Dict[str, Any]] = None, deep_dive: bool = False) -> str:
    """
    Construct grounded agronomic prompt strictly binding AI to the current diagnosis record.
    Enforces evidence separation, IPM priority, and Vietnamese agronomic clarity.
    """'''

new_prompt_func = '''def build_agronomic_system_prompt(
    diagnosis: Dict[str, Any],
    field_context: Optional[Dict[str, Any]] = None,
    deep_dive: bool = False,
    diagnosis_history: Optional[List[Dict[str, Any]]] = None,
    citations_enabled: bool = True
) -> str:
    """
    Construct grounded agronomic prompt strictly binding AI to the current diagnosis record.
    Enforces evidence separation, IPM priority, missing info inquiries, and Vietnamese agronomic clarity.
    Strictly avoids sending unnecessary PII (no user names, phones, emails, or credentials).
    """'''

content = content.replace(old_prompt_func, new_prompt_func)

# 2. Add diagnosis_history section in build_agronomic_system_prompt
old_fc_block = '''    # Field observation context
    fc = field_context or {}
    growth_stage = fc.get("growth_stage") or diagnosis.get("growth_stage") or "Không khai báo"
    user_symptoms = fc.get("user_symptoms") or diagnosis.get("user_symptoms") or "Không ghi nhận"
    field_conditions = fc.get("field_conditions") or diagnosis.get("field_conditions") or "Không ghi nhận"
    user_notes = fc.get("notes") or diagnosis.get("user_notes") or "Không có"
    farm_name = diagnosis.get("farm_name") or "Vườn cá nhân"'''

new_fc_block = '''    # Field observation context
    fc = field_context or {}
    growth_stage = fc.get("growth_stage") or diagnosis.get("growth_stage") or "Không khai báo"
    user_symptoms = fc.get("user_symptoms") or diagnosis.get("user_symptoms") or "Không ghi nhận"
    field_conditions = fc.get("field_conditions") or diagnosis.get("field_conditions") or "Không ghi nhận"
    user_notes = fc.get("notes") or diagnosis.get("user_notes") or "Không có"
    farm_name = diagnosis.get("farm_name") or "Vườn cá nhân"
    plot_name = diagnosis.get("plot_name") or "Lô trồng hiện tại"

    # History on same plot / farm
    history_lines = []
    if diagnosis_history:
        for h in diagnosis_history[:3]:
            h_id = h.get("id")
            h_dis = h.get("disease_name_vi") or h.get("predicted_disease") or "Không rõ"
            h_conf = round(float(h.get("confidence") or 0.0) * 100, 1)
            h_date = str(h.get("created_at") or "")[:10]
            history_lines.append(f"- Chẩn đoán #{h_id} ({h_date}): {h_dis} (Độ tin cậy: {h_conf}%)")
    hist_text = "\\n".join(history_lines) if history_lines else "- Chưa ghi nhận tiền sử bệnh lý trước đây trên cùng lô trồng."'''

content = content.replace(old_fc_block, new_fc_block)

# 3. Add history to prompt body and safety directives
old_prompt_body = '''- Nông trại / Vùng trồng: {farm_name}
- Kết quả nhận diện mô hình AI: {disease_vi}'''

new_prompt_body = '''- Nông trại / Vùng trồng: {farm_name}
- Lô đất / Khu vực: {plot_name}
- Lịch sử dịch bệnh trên cùng lô gần đây:
{hist_text}
- Kết quả nhận diện mô hình AI: {disease_vi}'''

content = content.replace(old_prompt_body, new_prompt_body)

# 4. Add Safety Rules: Non-guarantee, citations, missing info inquiry
old_rules = '''QUY TẮC BẮT BUỘC KHI TRẢ LỜI:
1. NGUYÊN TẮC CĂN CỨ BẰNG CHỨNG (GROUNDING):'''

new_rules = '''QUY TẮC BẮT BUỘC KHI TRẢ LỜI:
0. NGUYÊN TẮC TRUNG THỰC KHOA HỌC & KHÔNG CAM KẾT TUYỆT ĐỐI:
   - Đây là nhận diện thị giác máy học sơ bộ (AI prediction), KHÔNG PHẢI chẩn đoán y học thực vật khẳng định trong phòng thí nghiệm.
   - TUYỆT ĐỐI KHÔNG CAM KẾT CHỮA KHỎI 100% hay khẳng định "chắc chắn khỏi sau khi áp dụng". Mọi biện pháp phụ thuộc vào thời tiết, mật độ và liều lượng.
   - Khi độ tin cậy < 45% hoặc chẩn đoán chưa chắc chắn: PHẢI nói rõ "Mô hình có độ tin cậy thấp, chưa đủ căn cứ dứt khoát" và chủ động hỏi người dùng về các dấu hiệu còn thiếu ngoài thực địa.

1. NGUYÊN TẮC CĂN CỨ BẰNG CHỨNG (GROUNDING):'''

content = content.replace(old_rules, new_rules)

# 5. Add call_mock_api before extract_action_drafts
mock_api_code = '''def call_mock_api(
    system_prompt: str,
    messages: List[Dict[str, str]],
    diagnosis: Dict[str, Any],
    deep_dive: bool = False,
    citations_enabled: bool = True
) -> str:
    """
    Mock / Offline AI Provider Adapter for deterministic testing, offline environments,
    and verified pipeline evaluation without external API dependencies.
    """
    crop_name = diagnosis.get("crop_name") or diagnosis.get("crop_id") or "Cây trồng"
    disease_vi = diagnosis.get("disease_name_vi") or diagnosis.get("predicted_disease") or "Không xác định"
    conf_val = float(diagnosis.get("confidence") or 0.0)
    conf_pct = round(conf_val * 100, 1)
    is_healthy = bool("khỏe" in disease_vi.lower() or "healthy" in disease_vi.lower())
    is_uncertain = conf_val < 0.45 or diagnosis.get("is_uncertain", False) or diagnosis.get("status") == "disease_uncertain"

    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") in ("user", "human"):
            last_user_msg = m.get("content", "").strip()
            break

    lines = []
    if is_uncertain:
        lines.append(f"Chào bà con, kết quả phân tích ảnh cho thấy mô hình AI có **độ tin cậy thấp ({conf_pct}%)**, chưa đủ cơ sở dứt khoát để khẳng định cây {crop_name} mắc {disease_vi}.")
        lines.append("\\nĐể có cơ sở chính xác hơn, bà con vui lòng kiểm tra thêm một số dấu hiệu thực địa:")
        lines.append("1. **Vết bệnh ở tầng lá nào?** (Lá non trên ngọn, lá bánh tẻ, hay lá già sát gốc?)")
        lines.append("2. **Mặt dưới lá có mốc hay phấn không?** (Sáng sớm quan sát xem có lớp tơ mốc trắng, xám hay bào tử đen không?)")
        lines.append("3. **Vườn có bị úng nước hoặc mưa liên tục 2-3 ngày gần đây không?**")
        lines.append("\\nKhuyến nghị bà con chưa vội phun thuốc hóa học. Hãy chụp lại ảnh rõ nét dưới ánh sáng tự nhiên hoặc gửi mẫu để Chuyên gia BVTV thẩm định.")
    elif is_healthy:
        lines.append(f"Chào bà con, hình ảnh lá cây {crop_name} cho thấy phiến lá phát triển tốt, màu sắc đồng đều và **không ghi nhận dấu hiệu mầm bệnh nguy hiểm** (Độ tương đồng mô hình: {conf_pct}%).")
        lines.append("\\n**Hướng dẫn chăm sóc tiếp theo:**")
        lines.append("- Duy trì chế độ tưới tiêu hợp lý vào sáng sớm, tránh để đọng nước qua đêm.")
        lines.append("- Bổ sung vi sinh đối kháng Trichoderma định kỳ để tăng sức đề kháng tự nhiên cho bộ rễ.")
        lines.append("- Tiếp tục thăm vườn định kỳ 2-3 ngày/lần.")
    else:
        lines.append(f"Chào bà con, qua ảnh chụp lá cây {crop_name}, mô hình AI nhận diện biểu hiện nghi ngờ **{disease_vi}** với độ tin cậy mô hình đạt **{conf_pct}%**.")
        
        if deep_dive:
            lines.append(f"\\n🔬 **Phân tích bệnh học chuyên sâu:**")
            lines.append(f"- Tác nhân nghi ngờ thường do nấm hoặc vi khuẩn xâm nhiễm qua khí khổng hoặc vết thương hở khi độ ẩm không khí >85%.")
            lines.append(f"- Triệu chứng mô học: Mô lá bị hoại tử dần, tế bào diệp lục bị phá hủy tạo thành quầng vàng viền quanh vết đốm.")
        else:
            lines.append(f"\\n🔍 **Dấu hiệu thực địa cần đối chiếu:**")
            lines.append(f"- Vết đốm sẫm màu, mép lá có thể xuất hiện quầng vàng hoặc cháy khô mép phiến lá.")
            lines.append(f"- Cần kiểm tra kỹ các cây lân cận trong bán kính 2-3m xem vết bệnh có lây lan hay không.")

        lines.append("\\n📋 **Lộ trình xử lý đồng ruộng 5 bước an toàn sinh thái:**")
        lines.append("1. **Khảo sát:** Kiểm tra mặt dưới lá và gốc cây vào sáng sớm.")
        lines.append("2. **Vệ sinh:** Tỉa bỏ nhẹ nhàng các lá bệnh nặng, thu gom tiêu hủy xa vườn, không vứt xuống rãnh nước.")
        lines.append("3. **Điều chỉnh tưới:** Tạm dừng tưới phun mưa lên tán lá, chỉ tưới gốc vào buổi sáng.")
        lines.append("4. **Theo dõi:** Đánh dấu 3-5 cây bệnh để theo dõi tốc độ phát triển sau 48-72 giờ.")
        lines.append("5. **Tham vấn:** Nếu vết bệnh lan rộng nhanh >20% tán cây, hãy bấm nút Gửi Chuyên gia BVTV để nhận phác đồ trực tiếp.")

    # Action Draft
    if not is_healthy:
        lines.append(f'\\n```gari-action\\n{{"title": "Kiểm tra mặt dưới lá và vệ sinh lá đốm trên {crop_name}", "due_days": 2, "priority": "high", "task_type": "treatment", "description": "Khảo sát tiến triển vết bệnh {disease_vi} sau 48h, thu gom lá bệnh tiêu hủy xa nguồn nước."}}\\n```')

    # Citations
    if citations_enabled:
        lines.append("\\n\\n📚 **Tài liệu tham khảo nông học:**")
        lines.append("- *Viện Bảo vệ Thực vật Việt Nam (PPRI) — Cẩm nang nhận diện dịch hại cây trồng*")
        lines.append("- *Cơ sở dữ liệu Nông học GARI IPM Lab 2026*")
        lines.append("- *Quy chuẩn Kỹ thuật Quốc gia về BVTV (QCVN 01-189:2019/BNNPTNT)*")

    return "\\n".join(lines)


'''

if "def call_mock_api" not in content:
    idx_extract = content.find("def extract_action_drafts(")
    content = content[:idx_extract] + mock_api_code + content[idx_extract:]

# 6. Update process_chat to handle mock provider and diagnosis history
old_dispatch = '''        raw_reply = ""
        try:
            if provider == PROVIDER_GEMINI:
                raw_reply = call_gemini_api(api_key, model, system_prompt, history, temperature, timeout_sec)
            elif provider == PROVIDER_OPENAI:
                raw_reply = call_openai_compatible_api(api_key, base_url, model, system_prompt, history, temperature, timeout_sec)
            elif provider == PROVIDER_ANTHROPIC:
                raw_reply = call_anthropic_api(api_key, model, system_prompt, history, temperature, timeout_sec)
            else:
                return {
                    "success": False,
                    "status": "api_unconfigured",
                    "reply": "Trợ lý AI chuyên gia chưa được cấu hình. Vui lòng quay lại sau.",
                    "actions": []
                }'''

new_dispatch = '''        raw_reply = ""
        try:
            if provider == PROVIDER_MOCK:
                raw_reply = call_mock_api(system_prompt, history, diag, deep_dive=deep_dive, citations_enabled=cfg.get("citations_enabled", True))
            elif provider == PROVIDER_GEMINI:
                raw_reply = call_gemini_api(api_key, model, system_prompt, history, temperature, timeout_sec)
            elif provider == PROVIDER_OPENAI:
                raw_reply = call_openai_compatible_api(api_key, base_url, model, system_prompt, history, temperature, timeout_sec)
            elif provider == PROVIDER_ANTHROPIC:
                raw_reply = call_anthropic_api(api_key, model, system_prompt, history, temperature, timeout_sec)
            else:
                return {
                    "success": False,
                    "status": "api_unconfigured",
                    "reply": "Trợ lý AI chuyên gia chưa được cấu hình. Vui lòng quay lại sau.",
                    "actions": [],
                    "provider": PROVIDER_DISABLED
                }'''

content = content.replace(old_dispatch, new_dispatch)

# 7. Add escalate_to_expert in PlantHealthAssistantService
expert_escalate_code = '''    @classmethod
    def escalate_to_expert(cls, user_id: int, diagnosis_id: int, symptoms_description: str) -> Dict[str, Any]:
        """
        Escalate the current diagnosis and assistant consultation to an Agronomist Expert review case.
        Strictly enforces access authorization.
        """
        diag = gari_database.get_diagnosis(diagnosis_id, user_id=user_id)
        if not diag:
            diag_any = gari_database.get_diagnosis(diagnosis_id)
            if not diag_any:
                raise ValueError(f"Không tìm thấy bản ghi chẩn đoán #{diagnosis_id}")
            if diag_any.get("user_id") and diag_any.get("user_id") != user_id:
                user_orgs = gari_b2b.get_user_organizations(user_id)
                user_org_ids = [o["id"] for o in user_orgs]
                if not (diag_any.get("organization_id") and diag_any.get("organization_id") in user_org_ids):
                    raise PermissionError("Bạn không có quyền chuyển hồ sơ chẩn đoán này cho chuyên gia.")
            diag = diag_any

        crop_id = diag.get("crop_id") or "unknown"
        pred_disease = diag.get("disease_name_vi") or diag.get("predicted_disease") or "Chưa xác định"
        confidence = float(diag.get("confidence") or 0.0)

        case = gari_database.submit_expert_case({
            "crop_id": crop_id,
            "symptoms_description": symptoms_description or "Yêu cầu thẩm định thực địa từ GARI Assistant",
            "predicted_disease": pred_disease,
            "confidence": confidence,
            "diagnosis_id": diagnosis_id,
            "farm_id": diag.get("farm_id"),
            "plot_id": diag.get("plot_id") or diag.get("farm_plot_id")
        }, user_id=user_id)

        return {
            "success": True,
            "case_id": case.get("id"),
            "case": case,
            "message": f"Đã gửi hồ sơ #{case.get('id')} tới Chuyên gia BVTV thành công."
        }
'''

if "def escalate_to_expert" not in content:
    content = content + "\n" + expert_escalate_code

path.write_text(content, encoding="utf-8")
print("gari_assistant.py part 2 applied.")
