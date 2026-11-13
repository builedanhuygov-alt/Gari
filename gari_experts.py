"""
GARI Module 07 — Expert Network & Consultation Service Layer
Authoritative workflows for:
1. Expert onboarding & qualification verification.
2. Separation of Expert and Host Admin privileges.
3. Consultation case creation from leaf diagnosis with explicit farm privacy consent.
4. Case assignment, info requests, farmer follow-up, and resolution.
5. Strict expert access isolation and audit logging.
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from gari_database import get_connection
import gari_auth
from gari_auth import record_host_audit

logger = logging.getLogger("gari.experts")

VALID_URGENCIES = {"low", "medium", "high", "urgent"}
VALID_CASE_STATUSES = {"submitted", "open", "in_review", "waiting_user_info", "resolved", "closed"}


# ---------------------------------------------------------------------------
# Helper: Activity Logging for Expert Cases
# ---------------------------------------------------------------------------

def log_case_activity(
    case_id: int,
    actor_user_id: Optional[int],
    action: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    details: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> None:
    """Log an audit entry for a case status or assignment mutation."""
    try:
        if conn is not None:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO expert_case_activities (
                    case_id, actor_user_id, action, old_value, new_value, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (case_id, actor_user_id, action, old_value, new_value, details))
        else:
            with get_connection() as c:
                cursor = c.cursor()
                cursor.execute("""
                    INSERT INTO expert_case_activities (
                        case_id, actor_user_id, action, old_value, new_value, details, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (case_id, actor_user_id, action, old_value, new_value, details))
                c.commit()
    except Exception as e:
        logger.error(f"Error logging case activity for case {case_id}: {e}")


def get_case_activities(case_id: int) -> List[Dict[str, Any]]:
    """Retrieve full audit history for a consultation case."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, u.full_name as actor_name, u.email as actor_email
            FROM expert_case_activities a
            LEFT JOIN users u ON a.actor_user_id = u.id
            WHERE a.case_id = ?
            ORDER BY a.created_at ASC, a.id ASC
        """, (case_id,))
        return [dict(r) for r in cursor.fetchall()]


# ---------------------------------------------------------------------------
# 1. Expert Onboarding & Host Admin Verification
# ---------------------------------------------------------------------------

def apply_for_expert(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Submit an expert application with qualifications, primary crops, and institutions.
    """
    full_name = (data.get("full_name") or "").strip()
    institution = (data.get("institution") or data.get("organization") or "").strip()
    degree = (data.get("degree") or data.get("degree_details") or data.get("title") or "Kỹ sư Nông học").strip()
    specialization = (data.get("specialization") or (", ".join(data.get("specialties")) if isinstance(data.get("specialties"), list) else str(data.get("specialties") or "")) or "").strip()

    if not full_name or not institution or not specialization:
        raise ValueError("Vui lòng cung cấp đầy đủ: Họ tên, Cơ quan công tác, và Chuyên ngành nông học.")

    crops = data.get("primary_crops") or data.get("specialties") or ["Tomato", "Rice"]
    crops_json = json.dumps(crops if isinstance(crops, list) else [crops], ensure_ascii=False)

    regions = data.get("farming_regions") or ["Toàn quốc"]
    regions_json = json.dumps(regions if isinstance(regions, list) else [regions], ensure_ascii=False)

    email = data.get("email") or ""
    phone = data.get("phone") or ""
    bio = data.get("bio") or ""
    cert_url = data.get("certificate_url") or ""

    with get_connection() as conn:
        cursor = conn.cursor()
        # Verify user exists
        cursor.execute("SELECT id, email, is_expert, is_host_admin FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            raise ValueError(f"Không tìm thấy người dùng #{user_id}.")
        if not email:
            email = user_row["email"]

        # Check existing pending application
        cursor.execute("""
            SELECT id FROM expert_applications
            WHERE user_id = ? AND status = 'submitted'
        """, (user_id,))
        if cursor.fetchone():
            raise ValueError("Bạn đã có một đơn đăng ký chuyên gia đang chờ ban quản trị xét duyệt.")

        cursor.execute("""
            INSERT INTO expert_applications (
                user_id, full_name, email, phone, institution, degree,
                specialization, primary_crops_json, farming_regions_json,
                bio, certificate_url, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            user_id, full_name, email, phone, institution, degree,
            specialization, crops_json, regions_json, bio, cert_url
        ))
        conn.commit()
        app_id = cursor.lastrowid

        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        return dict(cursor.fetchone())


def review_expert_application(
    app_id: int,
    action: str,  # 'approve' or 'reject'
    host_user_id: int,
    host_email: str,
    reason: Optional[str] = None,
    ip_address: str = "0.0.0.0"
) -> Dict[str, Any]:
    """
    Host Admin reviews an expert application.
    Enforces that Expert status is granted while keeping Host Admin status strictly separate.
    """
    action = action.lower()
    if action not in ("approve", "reject"):
        raise ValueError("Hành động xét duyệt phải là 'approve' hoặc 'reject'.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        app_row = cursor.fetchone()
        if not app_row:
            raise ValueError(f"Không tìm thấy đơn đăng ký chuyên gia #{app_id}.")
        app_data = dict(app_row)
        user_id = app_data["user_id"]

        if action == "approve":
            cursor.execute("""
                UPDATE expert_applications
                SET status = 'approved',
                    reviewed_by_host_id = ?,
                    reviewed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (host_user_id, app_id))

            # Grant Expert account_type and is_expert flag.
            # IMPORTANT: Does NOT modify is_host_admin (preserves separation of privileges).
            cursor.execute("""
                UPDATE users
                SET is_expert = 1,
                    account_type = 'expert',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id,))

            # Create or update expert_profiles
            display_title = f"Chuyên gia Nông học ({app_data['degree']})"
            cursor.execute("""
                INSERT INTO expert_profiles (
                    user_id, full_name, display_title, institution, degree,
                    specialization, primary_crops_json, farming_regions_json,
                    bio, verification_status, status, verified_by_host_id,
                    is_active, verified_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', 'active', ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_title = excluded.display_title,
                    institution = excluded.institution,
                    degree = excluded.degree,
                    specialization = excluded.specialization,
                    primary_crops_json = excluded.primary_crops_json,
                    farming_regions_json = excluded.farming_regions_json,
                    bio = excluded.bio,
                    verification_status = 'approved',
                    status = 'active',
                    verified_by_host_id = excluded.verified_by_host_id,
                    is_active = 1,
                    verified_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                user_id, app_data["full_name"], display_title, app_data["institution"],
                app_data["degree"], app_data["specialization"], app_data["primary_crops_json"],
                app_data["farming_regions_json"], app_data["bio"], host_user_id
            ))

            # In-app notification to applicant
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Chúc mừng! Hồ sơ Chuyên gia Nông học đã được phê duyệt',
                        'Bạn đã trở thành Chuyên gia Nông học chính thức trên GARI. Hãy truy cập Expert Portal để tiếp nhận các ca chẩn đoán thực địa.',
                        'success', '/frontend2/expert-portal.html')
            """, (user_id,))

        else:  # reject
            cursor.execute("""
                UPDATE expert_applications
                SET status = 'rejected',
                    rejection_reason = ?,
                    reviewed_by_host_id = ?,
                    reviewed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (reason or "Hồ sơ chưa đáp ứng đủ tiêu chuẩn chuyên gia.", host_user_id, app_id))

            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Thông báo về đơn đăng ký Chuyên gia Nông học',
                        ?, 'warning', '/frontend2/support.html')
            """, (user_id, f"Đơn đăng ký chuyên gia của bạn chưa được phê duyệt. Lý do: {reason or 'Cần bổ sung hồ sơ chứng chỉ'}. Vui lòng cập nhật và nộp lại sau."))

        conn.commit()

    # Record Host Audit Log
    act_suffix = "approved" if action == "approve" else "rejected"
    record_host_audit(
        host_admin_id=host_user_id,
        host_email=host_email,
        action_type=f"expert_application_{act_suffix}",
        target_resource=f"expert_application:{app_id}",
        details={
            "applicant_id": user_id,
            "applicant_name": app_data.get("full_name"),
            "action": action,
            "reason": reason
        },
        reason=f"Xét duyệt đơn chuyên gia #{app_id}: {action}",
        outcome="success",
        ip_address=ip_address
    )

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        return dict(cursor.fetchone())


def update_expert_status(
    expert_id: int,
    is_active: bool,
    host_user_id: int,
    host_email: str,
    reason: Optional[str] = None,
    ip_address: str = "0.0.0.0",
    status_str: Optional[str] = None
) -> Dict[str, Any]:
    """
    Host Admin suspends or reactivates an approved expert.
    """
    status_val = status_str or ("active" if is_active else "suspended")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id FROM expert_profiles WHERE id = ? OR user_id = ?", (expert_id, expert_id))
        prof = cursor.fetchone()
        if not prof:
            raise ValueError(f"Không tìm thấy hồ sơ chuyên gia #{expert_id}.")
        prof_id = prof["id"]
        target_user_id = prof["user_id"]

        cursor.execute("""
            UPDATE expert_profiles
            SET is_active = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (1 if is_active else 0, status_val, prof_id))

        cursor.execute("""
            UPDATE users
            SET is_expert = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (1 if is_active else 0, target_user_id))

        conn.commit()

    record_host_audit(
        host_admin_id=host_user_id,
        host_email=host_email,
        action_type="expert_status_update",
        target_resource=f"expert_profile:{prof_id}",
        details={"is_active": is_active, "status": status_val, "reason": reason},
        reason=f"Cập nhật trạng thái chuyên gia ID {prof_id} thành {status_val}",
        outcome="success",
        ip_address=ip_address
    )

    return {"success": True, "expert_id": prof_id, "user_id": target_user_id, "is_active": is_active, "status": status_val}


# ---------------------------------------------------------------------------
# 2. Consultation Case Lifecycle & Farm Privacy Consent
# ---------------------------------------------------------------------------

def create_consultation_case(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new expert consultation case with explicit farm data consent.
    """
    symptoms = (data.get("symptoms_description") or data.get("notes") or data.get("question") or data.get("message") or "").strip()
    if not symptoms:
        raise ValueError("Mô tả triệu chứng bệnh thực địa là bắt buộc.")

    diagnosis_id = data.get("diagnosis_id")
    crop_name = data.get("crop_name") or "Cây trồng"
    suspected_disease = data.get("suspected_disease") or ""
    image_preview = data.get("image_preview") or ""
    farm_id = data.get("farm_id")
    farm_name = data.get("farm_name") or ""
    farmer_name = data.get("farmer_name") or ""
    phone = data.get("phone") or ""
    field_conditions = data.get("field_conditions") or ""
    urgency = (data.get("urgency") or "medium").lower()
    if urgency not in VALID_URGENCIES:
        urgency = "medium"

    consent_share_farm_data = 1 if data.get("consent_share_farm_data", True) else 0
    organization_id = data.get("organization_id")

    with get_connection() as conn:
        cursor = conn.cursor()

        # If diagnosis_id provided, inherit details
        if diagnosis_id:
            cursor.execute("SELECT * FROM diagnoses WHERE id = ?", (diagnosis_id,))
            diag_row = cursor.fetchone()
            if diag_row:
                diag = dict(diag_row)
                crop_name = diag.get("crop_name") or diag.get("crop_id") or crop_name
                suspected_disease = diag.get("disease_name_vi") or diag.get("predicted_disease") or suspected_disease
                if not image_preview:
                    image_preview = diag.get("image_preview") or diag.get("image_path") or ""
                if not farm_id and diag.get("farm_id"):
                    farm_id = diag.get("farm_id")
                    farm_name = diag.get("farm_name") or ""
                if not organization_id and diag.get("organization_id"):
                    organization_id = diag.get("organization_id")

        if not farmer_name:
            cursor.execute("SELECT full_name, phone FROM users WHERE id = ?", (user_id,))
            u_row = cursor.fetchone()
            if u_row:
                u = dict(u_row)
                farmer_name = u.get("full_name") or "Nông dân GARI"
                if not phone and u.get("phone"):
                    phone = u.get("phone")

        cursor.execute("""
            INSERT INTO expert_cases (
                user_id, diagnosis_id, farm_id, farm_name, farmer_name, phone,
                crop_name, suspected_disease, symptoms_description, field_conditions,
                image_preview, status, urgency, consent_share_farm_data, user_consent_history,
                organization_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            user_id, diagnosis_id, farm_id, farm_name, farmer_name, phone,
            crop_name, suspected_disease, symptoms, field_conditions,
            image_preview, urgency, consent_share_farm_data, consent_share_farm_data,
            organization_id
        ))
        conn.commit()
        case_id = cursor.lastrowid

    log_case_activity(
        case_id=case_id,
        actor_user_id=user_id,
        action="created",
        new_value="submitted",
        details=f"Tạo hồ sơ tư vấn chuyên gia: {crop_name} ({suspected_disease or 'Chưa rõ bệnh'}). Mức độ: {urgency}."
    )

    return get_consultation_case(case_id, caller_user={"id": user_id, "is_host_admin": False, "is_expert": False})


def get_consultation_case(case_id: int, caller_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve case with strict permission boundaries and data consent scrubbing.
    """
    caller_id = caller_user["id"]
    is_host = bool(caller_user.get("is_host_admin"))
    is_expert = bool(caller_user.get("is_expert"))

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy hồ sơ ca bệnh #{case_id}.")
        case = dict(row)

    is_creator = case["user_id"] == caller_id
    assigned_expert_id = case.get("assigned_expert_id")
    is_assigned_expert = assigned_expert_id == caller_id
    is_unassigned_open = not assigned_expert_id and case["status"] in ("submitted", "open")

    # Access Boundary Enforcement
    if not (is_creator or is_host or is_assigned_expert or (is_expert and is_unassigned_open)):
        if is_expert and assigned_expert_id and assigned_expert_id != caller_id:
            raise PermissionError("Ca bệnh này đã được phân công cho một chuyên gia khác tiếp nhận.")
        raise PermissionError("Bạn không có quyền truy cập hồ sơ tư vấn này.")

    # Data Consent Boundary: Scrub private farm data if consent not granted
    consent = case.get("consent_share_farm_data", 1)
    if not consent and not is_creator and not is_host:
        case["farm_id"] = None
        case["farm_name"] = "[ĐÃ ẨN THEO YÊU CẦU BẢO MẬT NÔNG TRẠI]"
        case["phone"] = "[ẨN SỐ ĐIỆN THOẠI]"
        case["field_conditions"] = "[DỮ LIỆU ĐỊA ĐIỂM ĐÃ ĐƯỢC ẨN]"

    # Attach conversation messages and audit activities
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_case_messages WHERE case_id = ? ORDER BY id ASC", (case_id,))
        messages = []
        for r in cursor.fetchall():
            m = dict(r)
            try:
                m["attachments"] = json.loads(m.get("attachments_json") or "[]")
            except Exception:
                m["attachments"] = []
            messages.append(m)
        case["messages"] = messages

    case["activities"] = get_case_activities(case_id)
    return case


def claim_consultation_case(case_id: int, expert_user_id: int, expert_name: str) -> Dict[str, Any]:
    """
    Verified expert accepts/claims responsibility for an open case.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        case_row = cursor.fetchone()
        if not case_row:
            raise ValueError(f"Không tìm thấy ca bệnh #{case_id}.")
        case = dict(case_row)

        if case.get("assigned_expert_id") and case["assigned_expert_id"] != expert_user_id:
            raise PermissionError("Ca bệnh này đã được tiếp nhận bởi chuyên gia khác.")

        old_status = case.get("status")
        cursor.execute("""
            UPDATE expert_cases
            SET assigned_expert_id = ?,
                assigned_expert = ?,
                status = 'in_review',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (expert_user_id, expert_name, case_id))

        # Add system message
        cursor.execute("""
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message)
            VALUES (?, ?, 'system', 'Hệ thống GARI', ?)
        """, (case_id, expert_user_id, f"Chuyên gia {expert_name} đã chính thức tiếp nhận hồ sơ chẩn đoán này."))

        # Notify farmer
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, target_url)
            VALUES (?, 'Chuyên gia đã tiếp nhận ca chẩn đoán', ?, 'info', '/frontend2/support.html')
        """, (case["user_id"], f"Chuyên gia {expert_name} đã tiếp nhận hồ sơ bệnh {case.get('crop_name', 'cây')} (#{case_id}) của bạn."))

        conn.commit()

    log_case_activity(
        case_id=case_id,
        actor_user_id=expert_user_id,
        action="claimed",
        old_value=old_status,
        new_value="in_review",
        details=f"Chuyên gia {expert_name} (#ID {expert_user_id}) tiếp nhận xử lý."
    )

    return get_consultation_case(case_id, caller_user={"id": expert_user_id, "is_expert": True, "is_host_admin": False})


def request_additional_info(
    case_id: int,
    expert_user_id: int,
    expert_name: str,
    question_message: str,
    attachments: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Expert asks the farmer for additional symptoms, clearer leaf photos, or environmental stats.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        case_row = cursor.fetchone()
        if not case_row:
            raise ValueError(f"Không tìm thấy ca bệnh #{case_id}.")
        case = dict(case_row)

        if case.get("assigned_expert_id") != expert_user_id:
            raise PermissionError("Bạn không phải chuyên gia được phân công cho ca bệnh này.")

        old_status = case.get("status")
        # Change status to waiting_user_info
        cursor.execute("""
            UPDATE expert_cases
            SET status = 'waiting_user_info', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (case_id,))

        att_json = json.dumps(attachments, ensure_ascii=False) if attachments else None
        cursor.execute("""
            INSERT INTO expert_case_messages (
                case_id, sender_user_id, sender_role, sender_name, message, attachments_json
            ) VALUES (?, ?, 'expert', ?, ?, ?)
        """, (case_id, expert_user_id, expert_name, question_message.strip(), att_json))

        # Notify farmer
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, target_url)
            VALUES (?, 'Chuyên gia yêu cầu bổ sung thông tin ca bệnh', ?, 'warning', '/frontend2/support.html')
        """, (case["user_id"], f"Chuyên gia {expert_name} cần thêm thông tin cho ca bệnh #{case_id}: \"{question_message[:60]}...\""))

        conn.commit()

    log_case_activity(
        case_id=case_id,
        actor_user_id=expert_user_id,
        action="info_requested",
        old_value=old_status,
        new_value="waiting_user_info",
        details=f"Yêu cầu bổ sung thông tin: {question_message[:80]}"
    )

    return get_consultation_case(case_id, caller_user={"id": expert_user_id, "is_expert": True, "is_host_admin": False})


def provide_additional_info(
    case_id: int,
    user_id: int,
    user_name: str,
    response_message: str,
    attachments: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Farmer provides the requested field information or follow-up questions.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        case_row = cursor.fetchone()
        if not case_row:
            raise ValueError(f"Không tìm thấy ca bệnh #{case_id}.")
        case = dict(case_row)

        if case["user_id"] != user_id:
            raise PermissionError("Bạn không phải là chủ sở hữu của ca bệnh này.")

        old_status = case.get("status")
        cursor.execute("""
            UPDATE expert_cases
            SET status = 'in_review', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (case_id,))

        att_json = json.dumps(attachments, ensure_ascii=False) if attachments else None
        cursor.execute("""
            INSERT INTO expert_case_messages (
                case_id, sender_user_id, sender_role, sender_name, message, attachments_json
            ) VALUES (?, ?, 'farmer', ?, ?, ?)
        """, (case_id, user_id, user_name, response_message.strip(), att_json))

        # Notify assigned expert
        if case.get("assigned_expert_id"):
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Nông dân đã bổ sung thông tin ca bệnh', ?, 'info', '/frontend2/expert-portal.html')
            """, (case["assigned_expert_id"], f"Nông hộ {user_name} đã phản hồi cho ca bệnh #{case_id}."))

        conn.commit()

    log_case_activity(
        case_id=case_id,
        actor_user_id=user_id,
        action="info_provided",
        old_value=old_status,
        new_value="in_review",
        details=f"Nông hộ gửi phản hồi: {response_message[:80]}"
    )

    return get_consultation_case(case_id, caller_user={"id": user_id, "is_expert": False, "is_host_admin": False})


def resolve_consultation_case(
    case_id: int,
    expert_user_id: int,
    resolution_notes: str,
    diagnosis_correction: Optional[str] = None,
    prescription_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Conclude case with confirmed diagnosis, IPM prescription, and instructions.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        case_row = cursor.fetchone()
        if not case_row:
            raise ValueError(f"Không tìm thấy ca bệnh #{case_id}.")
        case = dict(case_row)

        if case.get("assigned_expert_id") != expert_user_id:
            raise PermissionError("Chỉ chuyên gia được phân công mới có thể kết luận ca tư vấn.")

        full_notes = resolution_notes.strip()
        if diagnosis_correction:
            full_notes += f"\n[CHẨN ĐOÁN XÁC NHẬN]: {diagnosis_correction}"
        if prescription_data:
            full_notes += f"\n[PHÁC ĐỒ ĐIỀU TRỊ]: {json.dumps(prescription_data, ensure_ascii=False)}"

        old_status = case.get("status")
        cursor.execute("""
            UPDATE expert_cases
            SET status = 'resolved',
                resolved_at = CURRENT_TIMESTAMP,
                resolution_notes = ?,
                expert_notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (full_notes, full_notes, case_id))

        # Update linked diagnosis if correction provided
        if case.get("diagnosis_id") and diagnosis_correction:
            cursor.execute("""
                UPDATE diagnoses
                SET is_verified_by_expert = 1,
                    disease_name_vi = ?,
                    treatment_status = 'expert_verified'
                WHERE id = ?
            """, (diagnosis_correction, case["diagnosis_id"]))

        # Increment expert resolution counter
        cursor.execute("""
            UPDATE expert_profiles
            SET cases_resolved_count = cases_resolved_count + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (expert_user_id,))

        # System message in case
        cursor.execute("""
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message)
            VALUES (?, ?, 'system', 'Hệ thống GARI', ?)
        """, (case_id, expert_user_id, f"Chuyên gia đã đưa ra phác đồ điều trị và kết luận ca bệnh."))

        # Notification to farmer
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, target_url)
            VALUES (?, 'Chuyên gia đã hoàn tất tư vấn ca bệnh', ?, 'success', '/frontend2/support.html')
        """, (case["user_id"], f"Hồ sơ bệnh #{case_id} đã có phác đồ điều trị từ chuyên gia. Vui lòng kiểm tra hướng dẫn xử lý."))

        conn.commit()

    log_case_activity(
        case_id=case_id,
        actor_user_id=expert_user_id,
        action="resolved",
        old_value=old_status,
        new_value="resolved",
        details=f"Phác đồ: {resolution_notes[:100]}"
    )

    return get_consultation_case(case_id, caller_user={"id": expert_user_id, "is_expert": True, "is_host_admin": False})


def close_consultation_case(
    case_id: int,
    user_id: int,
    rating: Optional[float] = None,
    feedback_notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Farmer confirms satisfaction and closes the case, optionally rating the expert.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        case_row = cursor.fetchone()
        if not case_row:
            raise ValueError(f"Không tìm thấy ca bệnh #{case_id}.")
        case = dict(case_row)

        if case["user_id"] != user_id:
            raise PermissionError("Bạn không có quyền đóng ca bệnh này.")

        old_status = case.get("status")
        cursor.execute("""
            UPDATE expert_cases
            SET status = 'closed',
                closed_at = CURRENT_TIMESTAMP,
                rating = ?,
                feedback_notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (rating, feedback_notes, case_id))

        # Update expert average rating if provided
        if rating and case.get("assigned_expert_id"):
            cursor.execute("""
                UPDATE expert_profiles
                SET rating = ROUND((rating * cases_resolved_count + ?) / (cases_resolved_count + 1), 2)
                WHERE user_id = ?
            """, (rating, case["assigned_expert_id"]))

        conn.commit()

    log_case_activity(
        case_id=case_id,
        actor_user_id=user_id,
        action="closed",
        old_value=old_status,
        new_value="closed",
        details=f"Đóng ca tư vấn. Đánh giá: {rating or 'Không'} sao."
    )

    return get_consultation_case(case_id, caller_user={"id": user_id, "is_expert": False, "is_host_admin": False})


# ---------------------------------------------------------------------------
# 3. Queues & Listing
# ---------------------------------------------------------------------------

def list_cases_for_expert(
    expert_user_id: int,
    filter_type: str = "all",
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Retrieve expert queue with consent-based data masking.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        if filter_type == "assigned_to_me":
            cursor.execute("""
                SELECT * FROM expert_cases
                WHERE assigned_expert_id = ?
                ORDER BY id DESC LIMIT ? OFFSET ?
            """, (expert_user_id, limit, offset))
        elif filter_type == "unassigned":
            cursor.execute("""
                SELECT * FROM expert_cases
                WHERE assigned_expert_id IS NULL AND status IN ('submitted', 'open')
                ORDER BY id DESC LIMIT ? OFFSET ?
            """, (limit, offset))
        elif filter_type == "resolved":
            cursor.execute("""
                SELECT * FROM expert_cases
                WHERE assigned_expert_id = ? AND status IN ('resolved', 'closed')
                ORDER BY id DESC LIMIT ? OFFSET ?
            """, (expert_user_id, limit, offset))
        else:  # all accessible to this expert
            cursor.execute("""
                SELECT * FROM expert_cases
                WHERE assigned_expert_id = ? OR (assigned_expert_id IS NULL AND status IN ('submitted', 'open'))
                ORDER BY id DESC LIMIT ? OFFSET ?
            """, (expert_user_id, limit, offset))

        rows = [dict(r) for r in cursor.fetchall()]

    # Apply consent privacy scrubbing
    for c in rows:
        if not c.get("consent_share_farm_data", 1):
            c["farm_id"] = None
            c["farm_name"] = "[BẢO MẬT: Nông hộ không chia sẻ tên nông trại]"
            c["phone"] = "[ẨN SỐ ĐIỆN THOẠI]"

    return rows
