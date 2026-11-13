from pathlib import Path

path = Path("api_server.py")
content = path.read_text(encoding="utf-8")

# 1. Update manual mode model availability check
old_check = """        # Truthful Server-Side Model Availability Check (Part 9 & 10)
        if target_mode == "manual":
            if not target_crop:
                raise HTTPException(status_code=400, detail="Vui lòng chọn loại cây trồng khi sử dụng chế độ chỉ định cây.")
            entry = engine.get_model_entry(target_crop)
            if not entry or not entry.weight_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Mô hình AI chẩn đoán cho cây trồng '{target_crop}' hiện không khả dụng trên máy chủ."
                )"""

new_check = """        # Truthful Server-Side Model Availability Check (Part 9 & 10)
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
                    )"""

content = content.replace(old_check.replace("\r\n", "\n"), new_check.replace("\r\n", "\n"))
content = content.replace(old_check, new_check)

# 2. Update confidence threshold categorization and verification metadata
old_conf_status = """        # Determine exact Sprint 4 diagnosis_status
        is_healthy = bool(res.get("is_healthy", False))
        res_status = res.get("status", "OK")
        conf_val = float(res.get("confidence", 0.0))

        if res_status in ("crop_uncertain", "unsupported_crop", "crop_identified_no_disease_model", "disease_model_unavailable"):
            diagnosis_status = "unknown_or_unsupported"
        elif res_status in ("disease_uncertain", "uncertain") or (conf_val < 0.60 and not is_healthy):
            diagnosis_status = "needs_review"
        elif is_healthy or res_status in ("OK", "healthy"):
            diagnosis_status = "diagnosed"
        else:
            diagnosis_status = "needs_review" """

# Also find without trailing space
old_conf_status_alt = """        # Determine exact Sprint 4 diagnosis_status
        is_healthy = bool(res.get("is_healthy", False))
        res_status = res.get("status", "OK")
        conf_val = float(res.get("confidence", 0.0))

        if res_status in ("crop_uncertain", "unsupported_crop", "crop_identified_no_disease_model", "disease_model_unavailable"):
            diagnosis_status = "unknown_or_unsupported"
        elif res_status in ("disease_uncertain", "uncertain") or (conf_val < 0.60 and not is_healthy):
            diagnosis_status = "needs_review"
        elif is_healthy or res_status in ("OK", "healthy"):
            diagnosis_status = "diagnosed"
        else:
            diagnosis_status = "needs_review" """

new_conf_status = """        # Determine exact Sprint 4 & Module 02 diagnosis_status and confidence levels
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
        res["disclaimer_vi"] = "Kết quả phân tích được tạo tự động bởi mô hình AI (Chưa qua thẩm định của Chuyên gia BVTV). Luôn đối chiếu với thực địa trước khi áp dụng biện pháp xử lý." """

# Replace status logic
if "CONF_THRESH_HIGH = 0.70" not in content:
    content = content.replace(old_conf_status.replace("\r\n", "\n").strip(), new_conf_status.replace("\r\n", "\n").strip())

# 3. Add follow-up actions array to response
old_resp_format = """        diag_dict = {
            "status": diag_status,
            "disease_id": res.get("class_id") if (res.get("status") in ("OK", "healthy") or is_healthy) else None,
            "name_vi": res.get("disease_name_vi", res.get("prediction")) if (res.get("status") in ("OK", "healthy") or is_healthy) else None,
            "name_en": res.get("prediction_en", res.get("prediction")) if (res.get("status") in ("OK", "healthy") or is_healthy) else None,
            "score": res.get("confidence") if (res.get("status") in ("OK", "healthy") or is_healthy) else None,
            "confidence_percent": res.get("confidence_percent", 0.0),
            "confidence_level_vi": res.get("confidence_level_vi", "Thấp"),
            "severity": res.get("severity", "MEDIUM"),
            "is_healthy": is_healthy,
            "message_vi": res.get("message_vi", res.get("message", ""))
        }"""

new_resp_format = """        diag_dict = {
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
        ]"""

content = content.replace(old_resp_format.replace("\r\n", "\n"), new_resp_format.replace("\r\n", "\n"))
content = content.replace(old_resp_format, new_resp_format)

path.write_text(content, encoding="utf-8")
print("api_server.py patched successfully for Module 02.")
