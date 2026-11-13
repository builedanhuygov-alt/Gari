"""
GARI Leaf Intelligence — Plant Health Assistant Service
======================================================
Dedicated AI Disease Explainer Chatbot and Agronomic Decision Support engine.
Supports host-configurable AI providers (Gemini, OpenAI-compatible, Anthropic),
strict diagnosis grounding, IPM compliance, multi-turn dialogue, and explicit
task proposal confirmation into cultivation_tasks.
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

import httpx

import gari_database
import gari_b2b

logger = logging.getLogger("gari.assistant")

# Supported Providers
PROVIDER_DISABLED = "disabled"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai_compatible"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_MOCK = "mock"

CONFIDENCE_TIER_HIGH = "high_confidence"
CONFIDENCE_TIER_MEDIUM = "medium_confidence"
CONFIDENCE_TIER_LOW = "low_confidence"
CONFIDENCE_TIER_INSUFFICIENT = "insufficient_image"
CONFIDENCE_TIER_UNSUPPORTED = "unsupported_crop"


def get_assistant_config() -> Dict[str, Any]:
    """
    Retrieve Assistant settings with hierarchy:
    1. host_api_config table in SQLite
    2. Environment variables fallback
    3. Safe defaults (disabled)
    """
    db_configs: Dict[str, str] = {}
    try:
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM host_api_config WHERE key LIKE 'assistant_%'")
            for r in cursor.fetchall():
                db_configs[r[0]] = str(r[1]).strip()
    except Exception as exc:
        logger.warning("Could not read host_api_config for assistant: %s", exc)

    # Provider resolution
    provider = db_configs.get("assistant_provider") or os.getenv("AI_ASSISTANT_PROVIDER") or os.getenv("ASSISTANT_PROVIDER")
    if not provider:
        # Auto-detect if API keys are present in env
        if os.getenv("GEMINI_API_KEY"):
            provider = PROVIDER_GEMINI
        elif os.getenv("OPENAI_API_KEY"):
            provider = PROVIDER_OPENAI
        elif os.getenv("ANTHROPIC_API_KEY"):
            provider = PROVIDER_ANTHROPIC
        else:
            provider = PROVIDER_DISABLED

    provider = provider.lower().strip()

    # Model resolution
    default_model = "gemini-2.5-flash" if provider == PROVIDER_GEMINI else ("gpt-4o-mini" if provider == PROVIDER_OPENAI else "claude-3-5-sonnet-20241022")
    model = db_configs.get("assistant_model") or os.getenv("AI_ASSISTANT_MODEL") or default_model

    # API Key resolution
    api_key = db_configs.get("assistant_api_key")
    if not api_key:
        if provider == PROVIDER_GEMINI:
            api_key = os.getenv("GEMINI_API_KEY")
        elif provider == PROVIDER_OPENAI:
            api_key = os.getenv("OPENAI_API_KEY")
        elif provider == PROVIDER_ANTHROPIC:
            api_key = os.getenv("ANTHROPIC_API_KEY")

    # Base URL resolution
    base_url = db_configs.get("assistant_base_url") or os.getenv("AI_ASSISTANT_BASE_URL")
    if not base_url and provider == PROVIDER_OPENAI:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # Temperature & Timeout
    temperature = float(db_configs.get("assistant_temperature") or os.getenv("AI_ASSISTANT_TEMPERATURE", "0.2"))
    timeout_sec = float(db_configs.get("assistant_timeout_sec") or os.getenv("AI_ASSISTANT_TIMEOUT", "20.0"))

    citations_enabled = bool(db_configs.get("assistant_citations_enabled", "1") in ("1", "true", "True"))
    deep_dive_enabled = bool(db_configs.get("assistant_deep_dive_enabled", "1") in ("1", "true", "True"))

    if provider == PROVIDER_MOCK:
        is_configured = True
    else:
        is_configured = bool(provider != PROVIDER_DISABLED and api_key and len(api_key.strip()) > 5)

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key.strip() if api_key else None,
        "base_url": base_url.strip() if base_url else None,
        "temperature": temperature,
        "timeout_sec": timeout_sec,
        "citations_enabled": citations_enabled,
        "deep_dive_enabled": deep_dive_enabled,
        "is_configured": is_configured,
    }


def get_public_assistant_status() -> Dict[str, Any]:
    """
    Return non-sensitive public assistant status for client UI.
    NEVER expose API keys or internal credentials.
    """
    cfg = get_assistant_config()
    is_ready = cfg["is_configured"]

    if is_ready:
        return {
            "status": "ready",
            "is_configured": True,
            "provider": cfg["provider"],
            "model": cfg["model"],
            "system_name": "GARI Plant Health Assistant",
            "message": "Trợ lý AI chuyên gia đã sẵn sàng giải thích bệnh học thực địa."
        }
    else:
        return {
            "status": "api_unconfigured",
            "is_configured": False,
            "provider": PROVIDER_DISABLED,
            "model": None,
            "system_name": "GARI Plant Health Assistant",
            "message": "Trợ lý AI chuyên gia chưa được cấu hình. Vui lòng quay lại sau."
        }


def compute_confidence_tier(confidence: float, status: str, is_healthy: bool) -> str:
    """Classify confidence into explicit agronomic tiers."""
    if status in ("unsupported_crop", "crop_identified_no_disease_model", "disease_model_unavailable"):
        return CONFIDENCE_TIER_UNSUPPORTED
    if status in ("rejected", "not_a_leaf", "invalid_image"):
        return CONFIDENCE_TIER_INSUFFICIENT
    if is_healthy:
        return CONFIDENCE_TIER_HIGH if confidence >= 0.70 else CONFIDENCE_TIER_MEDIUM

    if confidence >= 0.85:
        return CONFIDENCE_TIER_HIGH
    elif confidence >= 0.60:
        return CONFIDENCE_TIER_MEDIUM
    else:
        return CONFIDENCE_TIER_LOW


def build_agronomic_system_prompt(
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
    """
    crop_name = diagnosis.get("crop_name") or diagnosis.get("crop_id") or "Cây trồng"
    disease_vi = diagnosis.get("disease_name_vi") or diagnosis.get("predicted_disease") or "Không xác định"
    conf_val = float(diagnosis.get("confidence") or 0.0)
    conf_pct = round(conf_val * 100, 1)
    severity = diagnosis.get("severity") or "MEDIUM"
    diag_status = diagnosis.get("diagnosis_status") or "diagnosed"
    is_healthy = bool("khỏe" in disease_vi.lower() or "healthy" in disease_vi.lower())

    tier = compute_confidence_tier(conf_val, diag_status, is_healthy)

    # Top predictions / candidates
    candidates = []
    top_preds = diagnosis.get("top_predictions") or []
    if isinstance(top_preds, list):
        for p in top_preds[:4]:
            if isinstance(p, dict):
                c_name = p.get("disease_vi") or p.get("disease") or p.get("label") or p.get("class_id")
                c_score = p.get("confidence") or p.get("score") or 0.0
                candidates.append(f"- {c_name}: {round(float(c_score)*100, 1)}%")

    # Field observation context
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
    hist_text = "\n".join(history_lines) if history_lines else "- Chưa ghi nhận tiền sử bệnh lý trước đây trên cùng lô trồng."

    # Grad-CAM regions info
    regions = diagnosis.get("regions") or []
    regions_count = len(regions) if isinstance(regions, list) else 0

    mode_text = "Giải thích chuyên sâu (bệnh học, chu kỳ mầm bệnh, cấu trúc tế bào)" if deep_dive else "Giải thích phổ thông (dễ hiểu cho nông dân trực tiếp ngoài vườn)"

    prompt = f"""Bạn là GARI Plant Health Assistant — Trợ lý AI Bác sĩ Cây Trồng chuyên nghiệp của GARI AgriTech AI Lab.
Nhiệm vụ của bạn là giải thích kết quả chẩn đoán bệnh lá cho nông dân hoặc chủ vườn, giúp họ hiểu rõ từ ảnh đến kết luận và hướng xử lý đồng ruộng thực tế.

CHẾ ĐỘ GIẢI THÍCH: {mode_text}.

THÔNG TIN BẢN GHI CHẨN ĐOÁN (NGUỒN SỰ THẬT TỐI CAO - BẮT BUỘC TUÂN THỦ):
- Mã chẩn đoán (Diagnosis ID): #{diagnosis.get('id', 'N/A')}
- Cây trồng: {crop_name}
- Nông trại / Vùng trồng: {farm_name}
- Lô đất / Khu vực: {plot_name}
- Lịch sử dịch bệnh trên cùng lô gần đây:
{hist_text}
- Kết quả nhận diện mô hình AI: {disease_vi}
- Điểm tương đồng mô hình (Softmax): {conf_pct}%
- Mức độ tin cậy phân loại (Confidence Tier): {tier} (high_confidence >= 85%, medium_confidence 60-84%, low_confidence < 60%)
- Mức độ nghiêm trọng: {severity}
- Trạng thái chẩn đoán: {diag_status}
- Số vùng nghi vấn phát hiện (Grad-CAM / LAB): {regions_count} vùng đốm bệnh
- Các khả năng mầm bệnh tiềm năng khác (Candidates):
{chr(10).join(candidates) if candidates else '- Không có ứng viên phụ'}

THÔNG TIN THỰC ĐỊA BỔ SUNG TỪ NGƯỜI DÙNG:
- Giai đoạn sinh trưởng: {growth_stage}
- Triệu chứng quan sát trực quan: {user_symptoms}
- Điều kiện thời tiết & chăm sóc gần đây: {field_conditions}
- Ghi chú thêm: {user_notes}

QUY TẮC BẮT BUỘC KHI TRẢ LỜI:
0. NGUYÊN TẮC TRUNG THỰC KHOA HỌC & KHÔNG CAM KẾT TUYỆT ĐỐI:
   - Đây là nhận diện thị giác máy học sơ bộ (AI prediction), KHÔNG PHẢI chẩn đoán y học thực vật khẳng định trong phòng thí nghiệm.
   - TUYỆT ĐỐI KHÔNG CAM KẾT CHỮA KHỎI 100% hay khẳng định "chắc chắn khỏi sau khi áp dụng". Mọi biện pháp phụ thuộc vào thời tiết, mật độ và liều lượng.
   - Khi độ tin cậy < 45% hoặc chẩn đoán chưa chắc chắn: PHẢI nói rõ "Mô hình có độ tin cậy thấp, chưa đủ căn cứ dứt khoát" và chủ động hỏi người dùng về các dấu hiệu còn thiếu ngoài thực địa.

1. NGUYÊN TẮC CĂN CỨ BẰNG CHỨNG (GROUNDING):
   - Phân biệt rành mạch 4 yếu tố:
     (a) Điều mô hình thị giác AI thực sự phát hiện trên ảnh lá (đốm tổn thương, quầng vàng, vết cháy mép, bào tử).
     (b) Dấu hiệu quan sát thực tế người dùng cung cấp (giai đoạn sinh trưởng, thời tiết, triệu chứng).
     (c) Các khả năng bệnh lý tiềm năng khác có thể nhầm lẫn (differential diagnosis).
     (d) Giả thuyết nông học cần kiểm chứng thêm ngoài ruộng.
   - Tuyệt đối không bịa đặt triệu chứng không có trong dữ liệu hay trên ảnh.

2. LỘ TRÌNH HÀNH ĐỘNG 5 BƯỚC NÔNG HỌC THỰC TẾ:
   Khi đưa ra hướng dẫn, luôn cấu trúc rõ ràng:
   - Bước 1 (Khảo sát ngay): Kiểm tra mặt dưới lá, chóp lá non, mật độ vết bệnh trong bán kính 2m.
   - Bước 2 (Giảm thiểu rủi ro): Vệ sinh lá bệnh rơi rụng, tỉa cành thông thoáng, dừng tưới phun mưa lúc chiều tối.
   - Bước 3 (Theo dõi 48-72h): Tiêu chí xác định bệnh dừng phát triển hay lây lan.
   - Bước 4 (Dấu hiệu cần chụp lại ảnh): Góc chụp, độ sáng, chụp mặt dưới phiến lá.
   - Bước 5 (Ngưỡng tham vấn chuyên gia): Khi vết bệnh lan nhanh >20% tán cây hoặc xuất hiện héo rũ gốc.

3. AN TOÀN NÔNG HỌC & IPM (INTEGRATED PEST MANAGEMENT):
   - Ưu tiên hàng đầu: Biện pháp canh tác, vệ sinh đồng ruộng, vi sinh đối kháng (Trichoderma, Bacillus), khoáng hữu cơ.
   - TUYỆT ĐỐI KHÔNG QUẢNG CÁO HAY KÊ ĐƠN TÊN THƯƠNG MẠI THUỐC BVTV HÓA HỌC. Nếu cần can thiệp hóa học, chỉ nêu tên hoạt chất phổ quát được Bộ NN&PTNT cấp phép và dặn dò tuân thủ nguyên tắc 4 đúng và thời gian cách ly.

4. ĐỀ XUẤT CÔNG VIỆC THEO DÕI (ACTION PROPOSAL):
   Nếu phù hợp, bạn có thể đề xuất MỘT công việc canh tác cụ thể để nông dân đưa vào Lịch canh tác. Định dạng khối JSON ở cuối câu trả lời theo mẫu chính xác sau:
   ```gari-action
   {{"title": "Kiểm tra tiến triển vết bệnh sau 48h", "due_days": 2, "priority": "medium", "task_type": "scouting", "description": "Kiểm tra mặt dưới lá và đo lường kích thước vết bệnh trên cây {crop_name}."}}
   ```
   Nếu không cần đề xuất công việc mới, không cần thêm khối này.

Trả lời bằng tiếng Việt tự nhiên, ân cần, khúc chiết, chuẩn mực nông nghiệp Việt Nam.
"""
    return prompt


def call_gemini_api(api_key: str, model: str, system_prompt: str, messages: List[Dict[str, str]], temperature: float, timeout_sec: float) -> str:
    """Call Google Gemini REST API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    # Convert conversation turns
    contents = []
    for msg in messages:
        role = "user" if msg.get("role") in ("user", "human") else "model"
        contents.append({
            "role": role,
            "parts": [{"text": msg.get("content", "")}]
        })

    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 2048,
        }
    }

    with httpx.Client(timeout=timeout_sec) as client:
        resp = client.post(url, json=payload, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return "Trợ lý AI không tạo được phản hồi. Vui lòng thử lại."
        parts = candidates[0].get("content", {}).get("parts") or []
        return "".join([p.get("text", "") for p in parts]).strip()


def call_openai_compatible_api(api_key: str, base_url: str, model: str, system_prompt: str, messages: List[Dict[str, str]], temperature: float, timeout_sec: float) -> str:
    """Call OpenAI-compatible chat completions REST API."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = "assistant" if msg.get("role") in ("assistant", "model", "bot") else "user"
        api_messages.append({"role": role, "content": msg.get("content", "")})

    payload = {
        "model": model,
        "messages": api_messages,
        "temperature": temperature,
        "max_tokens": 2048
    }

    with httpx.Client(timeout=timeout_sec) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return "Trợ lý AI không tạo được phản hồi. Vui lòng thử lại."
        return choices[0].get("message", {}).get("content", "").strip()


def call_anthropic_api(api_key: str, model: str, system_prompt: str, messages: List[Dict[str, str]], temperature: float, timeout_sec: float) -> str:
    """Call Anthropic Messages REST API."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    api_messages = []
    for msg in messages:
        role = "assistant" if msg.get("role") in ("assistant", "model", "bot") else "user"
        api_messages.append({"role": role, "content": msg.get("content", "")})

    payload = {
        "model": model,
        "system": system_prompt,
        "messages": api_messages,
        "temperature": temperature,
        "max_tokens": 2048
    }

    with httpx.Client(timeout=timeout_sec) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        content_items = data.get("content") or []
        return "".join([c.get("text", "") for c in content_items if c.get("type") == "text"]).strip()


def call_mock_api(
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
        lines.append("\nĐể có cơ sở chính xác hơn, bà con vui lòng kiểm tra thêm một số dấu hiệu thực địa:")
        lines.append("1. **Vết bệnh ở tầng lá nào?** (Lá non trên ngọn, lá bánh tẻ, hay lá già sát gốc?)")
        lines.append("2. **Mặt dưới lá có mốc hay phấn không?** (Sáng sớm quan sát xem có lớp tơ mốc trắng, xám hay bào tử đen không?)")
        lines.append("3. **Vườn có bị úng nước hoặc mưa liên tục 2-3 ngày gần đây không?**")
        lines.append("\nKhuyến nghị bà con chưa vội phun thuốc hóa học. Hãy chụp lại ảnh rõ nét dưới ánh sáng tự nhiên hoặc gửi mẫu để Chuyên gia BVTV thẩm định.")
    elif is_healthy:
        lines.append(f"Chào bà con, hình ảnh lá cây {crop_name} cho thấy phiến lá phát triển tốt, màu sắc đồng đều và **không ghi nhận dấu hiệu mầm bệnh nguy hiểm** (Độ tương đồng mô hình: {conf_pct}%).")
        lines.append("\n**Hướng dẫn chăm sóc tiếp theo:**")
        lines.append("- Duy trì chế độ tưới tiêu hợp lý vào sáng sớm, tránh để đọng nước qua đêm.")
        lines.append("- Bổ sung vi sinh đối kháng Trichoderma định kỳ để tăng sức đề kháng tự nhiên cho bộ rễ.")
        lines.append("- Tiếp tục thăm vườn định kỳ 2-3 ngày/lần.")
    else:
        lines.append(f"Chào bà con, qua ảnh chụp lá cây {crop_name}, mô hình AI nhận diện biểu hiện nghi ngờ **{disease_vi}** với độ tin cậy mô hình đạt **{conf_pct}%**.")
        
        if deep_dive:
            lines.append(f"\n🔬 **Phân tích bệnh học chuyên sâu:**")
            lines.append(f"- Tác nhân nghi ngờ thường do nấm hoặc vi khuẩn xâm nhiễm qua khí khổng hoặc vết thương hở khi độ ẩm không khí >85%.")
            lines.append(f"- Triệu chứng mô học: Mô lá bị hoại tử dần, tế bào diệp lục bị phá hủy tạo thành quầng vàng viền quanh vết đốm.")
        else:
            lines.append(f"\n🔍 **Dấu hiệu thực địa cần đối chiếu:**")
            lines.append(f"- Vết đốm sẫm màu, mép lá có thể xuất hiện quầng vàng hoặc cháy khô mép phiến lá.")
            lines.append(f"- Cần kiểm tra kỹ các cây lân cận trong bán kính 2-3m xem vết bệnh có lây lan hay không.")

        lines.append("\n📋 **Lộ trình xử lý đồng ruộng 5 bước an toàn sinh thái:**")
        lines.append("1. **Khảo sát:** Kiểm tra mặt dưới lá và gốc cây vào sáng sớm.")
        lines.append("2. **Vệ sinh:** Tỉa bỏ nhẹ nhàng các lá bệnh nặng, thu gom tiêu hủy xa vườn, không vứt xuống rãnh nước.")
        lines.append("3. **Điều chỉnh tưới:** Tạm dừng tưới phun mưa lên tán lá, chỉ tưới gốc vào buổi sáng.")
        lines.append("4. **Theo dõi:** Đánh dấu 3-5 cây bệnh để theo dõi tốc độ phát triển sau 48-72 giờ.")
        lines.append("5. **Tham vấn:** Nếu vết bệnh lan rộng nhanh >20% tán cây, hãy bấm nút Gửi Chuyên gia BVTV để nhận phác đồ trực tiếp.")

    # Action Draft
    if not is_healthy:
        lines.append(f'\n```gari-action\n{{"title": "Kiểm tra mặt dưới lá và vệ sinh lá đốm trên {crop_name}", "due_days": 2, "priority": "high", "task_type": "treatment", "description": "Khảo sát tiến triển vết bệnh {disease_vi} sau 48h, thu gom lá bệnh tiêu hủy xa nguồn nước."}}\n```')

    # Citations
    if citations_enabled:
        lines.append("\n\n📚 **Tài liệu tham khảo nông học:**")
        lines.append("- *Viện Bảo vệ Thực vật Việt Nam (PPRI) — Cẩm nang nhận diện dịch hại cây trồng*")
        lines.append("- *Cơ sở dữ liệu Nông học GARI IPM Lab 2026*")
        lines.append("- *Quy chuẩn Kỹ thuật Quốc gia về BVTV (QCVN 01-189:2019/BNNPTNT)*")

    return "\n".join(lines)


def extract_action_drafts(reply_text: str, diagnosis: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Parse any ```gari-action JSON blocks emitted by the LLM.
    Returns cleaned reply text and a list of structured action draft objects.
    """
    actions: List[Dict[str, Any]] = []
    cleaned_reply = reply_text

    marker_start = "```gari-action"
    marker_end = "```"

    while marker_start in cleaned_reply:
        p_start = cleaned_reply.find(marker_start)
        p_end = cleaned_reply.find(marker_end, p_start + len(marker_start))
        if p_end == -1:
            break

        json_str = cleaned_reply[p_start + len(marker_start):p_end].strip()
        try:
            draft = json.loads(json_str)
            if isinstance(draft, dict) and draft.get("title"):
                due_days = int(draft.get("due_days", 2))
                due_date = (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d")
                actions.append({
                    "title": draft.get("title"),
                    "description": draft.get("description", ""),
                    "due_date": due_date,
                    "priority": draft.get("priority", "medium"),
                    "task_type": draft.get("task_type", "scouting"),
                    "crop_id": diagnosis.get("crop_id") or "Tomato",
                    "farm_id": diagnosis.get("farm_id"),
                    "plot_id": diagnosis.get("plot_id") or diagnosis.get("farm_plot_id"),
                    "diagnosis_id": diagnosis.get("id"),
                    "requires_confirmation": True
                })
        except Exception as exc:
            logger.debug("Failed parsing gari-action block: %s", exc)

        # Remove the code block from visible chat text
        cleaned_reply = (cleaned_reply[:p_start] + cleaned_reply[p_end + len(marker_end):]).strip()

    return cleaned_reply, actions


class PlantHealthAssistantService:
    """Unified service handling diagnosis explanations, multi-turn chat, and confirmed actions."""

    @classmethod
    def process_chat(
        cls,
        user_id: int,
        diagnosis_id: int,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        field_context: Optional[Dict[str, Any]] = None,
        deep_dive: bool = False
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()

        # 1. Fetch diagnosis record and enforce ownership
        diag = gari_database.get_diagnosis(diagnosis_id, user_id=user_id)
        if not diag:
            # Check if diagnosis belongs to an organization the user belongs to
            diag_any = gari_database.get_diagnosis(diagnosis_id)
            if not diag_any:
                return {
                    "success": False,
                    "status": "not_found",
                    "reply": f"Không tìm thấy bản ghi chẩn đoán #{diagnosis_id} trong hệ thống.",
                    "actions": []
                }
            # Enforce access: if diagnosis has user_id and it doesn't match
            if diag_any.get("user_id") and diag_any.get("user_id") != user_id:
                # Check organization membership
                user_orgs = gari_b2b.get_user_organizations(user_id)
                user_org_ids = [o["id"] for o in user_orgs]
                if not (diag_any.get("organization_id") and diag_any.get("organization_id") in user_org_ids):
                    return {
                        "success": False,
                        "status": "forbidden",
                        "reply": "Bạn không có quyền truy cập hồ sơ chẩn đoán này.",
                        "actions": []
                    }
            diag = diag_any

        # 2. Check Assistant Provider Configuration
        cfg = get_assistant_config()
        if not cfg["is_configured"]:
            logger.info("Assistant called but provider is unconfigured.")
            return {
                "success": False,
                "status": "api_unconfigured",
                "reply": "Trợ lý AI chuyên gia chưa được cấu hình. Vui lòng quay lại sau.",
                "actions": [],
                "provider": PROVIDER_DISABLED
            }

        # 3. Build grounded system prompt
        system_prompt = build_agronomic_system_prompt(diag, field_context=field_context, deep_dive=deep_dive)

        # 4. Assemble messages history
        history = list(conversation_history or [])
        history.append({"role": "user", "content": message.strip()})

        # 5. Call Provider Adapter
        provider = cfg["provider"]
        model = cfg["model"]
        api_key = cfg["api_key"]
        base_url = cfg["base_url"]
        temperature = cfg["temperature"]
        timeout_sec = cfg["timeout_sec"]

        raw_reply = ""
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
                }
        except httpx.HTTPStatusError as exc:
            logger.error("AI provider HTTP %d error: %s", exc.response.status_code, exc.response.text[:200])
            return {
                "success": False,
                "status": "api_error",
                "reply": "Hệ thống AI chuyên gia đang bận hoặc quá tải kết nối. Vui lòng thử lại sau giây lát.",
                "actions": []
            }
        except Exception as exc:
            logger.error("AI Assistant dispatch error: %s", exc, exc_info=True)
            return {
                "success": False,
                "status": "api_error",
                "reply": "Không thể kết nối đến máy chủ AI chuyên gia. Xin vui lòng kiểm tra kết nối mạng.",
                "actions": []
            }

        # 6. Extract action drafts and clean reply
        cleaned_reply, proposed_actions = extract_action_drafts(raw_reply, diag)
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

        # 7. Persist turn to chat_history
        try:
            with gari_database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chat_history (
                        user_id, prediction_id, diagnosis_id, user_message, bot_response,
                        message_type, response_source, response_time_ms, actions_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    None,
                    diagnosis_id,
                    message,
                    cleaned_reply,
                    "leaf_intelligence_consultation",
                    f"{provider}:{model}",
                    elapsed_ms,
                    json.dumps(proposed_actions) if proposed_actions else None
                ))
                conn.commit()
        except Exception as exc:
            logger.warning("Could not persist assistant chat_history: %s", exc)

        return {
            "success": True,
            "status": "ready",
            "reply": cleaned_reply,
            "actions": proposed_actions,
            "elapsed_ms": elapsed_ms,
            "provider": provider,
            "model": model,
            "grounding_crop": diag.get("crop_name") or diag.get("crop_id") if diag else None,
            "grounding_disease": diag.get("disease_name_vi") or diag.get("predicted_disease") if diag else None,
            "diagnosis_id": diagnosis_id
        }

    @classmethod
    def get_history(cls, user_id: int, diagnosis_id: int) -> List[Dict[str, Any]]:
        """Retrieve conversation history for a given diagnosis with tenant isolation."""
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, prediction_id, user_message, bot_response,
                       response_source, response_time_ms, actions_json, created_at
                FROM chat_history
                WHERE (diagnosis_id = ? OR prediction_id = ?) AND user_id = ?
                ORDER BY id ASC
            """, (diagnosis_id, diagnosis_id, user_id))
            rows = []
            for r in cursor.fetchall():
                row_dict = dict(r)
                if row_dict.get("actions_json"):
                    try:
                        row_dict["actions"] = json.loads(row_dict["actions_json"])
                    except Exception:
                        row_dict["actions"] = []
                else:
                    row_dict["actions"] = []
                rows.append(row_dict)
            return rows

    @classmethod
    def confirm_action_to_task(cls, user_id: int, diagnosis_id: int, action_draft: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Explicitly convert a chatbot-proposed action draft into a persistent cultivation_task.
        Strictly requires explicit user trigger.
        """
        title = (action_draft.get("title") or "").strip()
        if not title:
            return None

        # Verify diagnosis ownership or access
        diag = gari_database.get_diagnosis(diagnosis_id, user_id=user_id)
        farm_id = action_draft.get("farm_id") or (diag.get("farm_id") if diag else None)
        plot_id = action_draft.get("plot_id") or (diag.get("plot_id") if diag else None)
        crop_id = action_draft.get("crop_id") or (diag.get("crop_id") if diag else "Tomato")
        org_id = diag.get("organization_id") if diag else None

        # Fallbacks for farm / plot if unassociated
        if not farm_id:
            user_farms = gari_database.list_farms(user_id=user_id)
            if user_farms:
                farm_id = user_farms[0]["id"]
        if not plot_id and farm_id:
            user_plots = gari_database.list_plots(farm_id=farm_id, user_id=user_id)
            if user_plots:
                plot_id = user_plots[0]["id"]

        due_date = action_draft.get("due_date") or (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        priority = action_draft.get("priority", "medium")
        task_type = action_draft.get("task_type", "scouting")
        description = action_draft.get("description", "")
        notes = f"Được xác nhận từ GARI Plant Health Assistant (Hồ sơ chẩn đoán #{diagnosis_id})"

        created_task = gari_database.create_cultivation_task({
            "title": title,
            "description": description,
            "due_date": due_date,
            "priority": priority,
            "status": "pending",
            "task_type": task_type,
            "crop_id": crop_id,
            "farm_id": farm_id,
            "plot_id": plot_id,
            "notes": notes
        }, user_id=user_id, org_id=org_id)

        return created_task

    @classmethod
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

        crop_name = diag.get("crop_name") or crop_id
        case = gari_database.submit_expert_case({
            "crop_id": crop_id,
            "crop_name": crop_name,
            "symptoms_description": symptoms_description or "Yêu cầu thẩm định thực địa từ GARI Assistant",
            "suspected_disease": pred_disease,
            "predicted_disease": pred_disease,
            "confidence": confidence,
            "diagnosis_id": diagnosis_id,
            "farm_id": diag.get("farm_id"),
            "plot_id": diag.get("plot_id") or diag.get("farm_plot_id")
        }, user_id=user_id)

        case["predicted_disease"] = case.get("suspected_disease") or pred_disease
        case["crop_id"] = crop_id
        case["crop_name"] = crop_name

        return {
            "success": True,
            "case_id": case.get("id"),
            "case": case,
            "message": f"Đã gửi hồ sơ #{case.get('id')} tới Chuyên gia BVTV thành công."
        }
