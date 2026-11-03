"""
GARI AI LAB — Violation Moderation & Host Review Engine (gari_moderation.py)

Provides:
- Deterministic and heuristic violation detection pipeline (Spam, Scam, Harassment, Non-Agricultural, Unsafe Uploads, API/Voucher Abuse).
- Automated review case generation (AI/rules NEVER auto-ban; all severe enforcement requires Host approval).
- Host Review Queue management (pending, high priority, dismissed, restricted, suspended, banned).
- Host Moderation Actions (dismiss, false_positive, warn, restrict, suspend, ban, restore).
- User Appeals workflow (submission and Host review).
- Backend enforcement gates (feature restrictions, suspended/banned checks).
- Full immutable audit logging.
"""

import json
import logging
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import HTTPException, status
import gari_database

logger = logging.getLogger("gari_moderation")

# -----------------------------------------------------------------------------
# Categories & Enums
# -----------------------------------------------------------------------------
CATEGORY_SPAM = "spam"
CATEGORY_SCAM_IMPERSONATION = "scam_impersonation"
CATEGORY_HARASSMENT_ABUSE = "harassment_abuse"
CATEGORY_NON_AGRICULTURAL = "non_agricultural"
CATEGORY_REPEATED_VIOLATION = "repeated_violation"
CATEGORY_API_ABUSE = "api_abuse"
CATEGORY_UNSAFE_UPLOAD = "unsafe_upload"

VALID_CATEGORIES = {
    CATEGORY_SPAM: "Spam & Nội dung rác lặp lại",
    CATEGORY_SCAM_IMPERSONATION: "Lừa đảo, Giả mạo BQT / Cán bộ GARI",
    CATEGORY_HARASSMENT_ABUSE: "Quấy rối, Xúc phạm & Đe dọa",
    CATEGORY_NON_AGRICULTURAL: "Nội dung sai lệch ngoài nông nghiệp",
    CATEGORY_REPEATED_VIOLATION: "Vi phạm chính sách nhiều lần",
    CATEGORY_API_ABUSE: "Lạm dụng API, Quá tải & Brute-force",
    CATEGORY_UNSAFE_UPLOAD: "Tải lên tệp độc hại hoặc không an toàn"
}

SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_CRITICAL = "critical"
VALID_SEVERITIES = {SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH, SEVERITY_CRITICAL}

STATUS_PENDING = "pending"
STATUS_DISMISSED = "dismissed"
STATUS_FALSE_POSITIVE = "false_positive"
STATUS_WARNED = "warned"
STATUS_RESTRICTED = "restricted"
STATUS_SUSPENDED = "suspended"
STATUS_BANNED = "banned"

# Feature restriction constants
RESTRICTION_UPLOAD = "upload_restricted"
RESTRICTION_FEEDBACK = "feedback_restricted"
RESTRICTION_CHAT = "chat_restricted"

# -----------------------------------------------------------------------------
# Pattern Dictionaries for Deterministic Scanning
# -----------------------------------------------------------------------------
_SCAM_IMPERSONATION_PATTERNS = [
    re.compile(r"\b(admin[_\s]?gari|ban[_\s]?qu[aả]n[_\s]?tr[iị][_\s]?gari|bqt[_\s]?gari|nh[aâ]n[_\s]?vi[eê]n[_\s]?gari)\b", re.IGNORECASE),
    re.compile(r"\b(cung[_\s]?c[aấ]p[_\s]?m[aã][_\s]?otp|g[uử]i[_\s]?m[aậ]t[_\s]?kh[aẩ]u|chuy[eể]n[_\s]?kho[aả]n[_\s]?nh[aậ]n[_\s]?qu[aà])\b", re.IGNORECASE),
    re.compile(r"\b(h[oỗ][_\s]?tr[oợ][_\s]?k[yỹ][_\s]?thu[aậ]t[_\s]?zalo|zalo[_\s]?admin|li[eê]n[_\s]?h[eệ][_\s]?telegram)\b", re.IGNORECASE)
]

_SPAM_PATTERNS = [
    re.compile(r"\b(nh[aà][_\s]?c[aá]i|ku[_\s]?bet|t[aà]i[_\s]?x[iỉ]u|l[oô][_\s]?đ[eề]|game[_\s]?b[aà]i|c[aá][_\s]?c[uư][oợ]c)\b", re.IGNORECASE),
    re.compile(r"\b(vay[_\s]?ti[eề]n[_\s]?nhanh|l[aã]i[_\s]?su[aấ]t[_\s]?0%|gi[aả]i[_\s]?ng[aâ]n[_\s]?trong[_\s]?ng[aà]y)\b", re.IGNORECASE),
    re.compile(r"\b(crypto|pump[_\s]?coin|ti[eề]n[_\s]?[aả]o|đ[aà]o[_\s]?coin)\b", re.IGNORECASE)
]

_HARASSMENT_PATTERNS = [
    re.compile(r"\b(đ[iị]t[_\s]?m[eẹ]|đ[mmeẹ]|v[ccl]|đ[eéo]|ch[oó][_\s]?ch[eế]t|gi[aế]t[_\s]?m[aà]y)\b", re.IGNORECASE),
    re.compile(r"\b(fuck|shit|bitch|bastard|scammer|asshole)\b", re.IGNORECASE)
]

_NON_AGRI_PATTERNS = [
    re.compile(r"\b(b[aá]n[_\s]?sim[_\s]?s[oố][_\s]?đ[eẹp]|d[iị]ch[_\s]?v[uụ][_\s]?seo|t[aă]ng[_\s]?follow|h[eẹ][_\s]?h[oò][_\s]?t[iì]nh[_\s]?d[uụ]c)\b", re.IGNORECASE)
]

_PROHIBITED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".php", ".phtml", ".py", ".pyw",
    ".js", ".vbs", ".ps1", ".jar", ".dll", ".so", ".bin", ".scr"
}

# -----------------------------------------------------------------------------
# In-Memory Rate & Activity Tracking (Sliding Window)
# -----------------------------------------------------------------------------
_API_ACTIVITY_TRACKER: Dict[str, List[float]] = {}
_VOUCHER_FAILURES_TRACKER: Dict[str, List[float]] = {}
ACTIVITY_WINDOW_SECONDS = 60
BURST_THRESHOLD = 30  # Max requests per minute before flagging api_abuse


def now_utc_iso() -> str:
    """Return ISO formatted UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# -----------------------------------------------------------------------------
# 1. Detection Pipeline (Deterministic Scanners)
# -----------------------------------------------------------------------------

def scan_content_text(
    text: Optional[str],
    context: str = "general",
    user_id: Optional[int] = None,
    user_email: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Deterministically scan text content for policy violations.
    Checks:
    - Scam & Impersonation (BQT/Admin spoofing, phishing)
    - Spam & Commercial Unrelated Advertising (Gambling, loans)
    - Harassment, Threats & Severe Profanity
    - Non-agricultural spam
    Returns a violation descriptor or None if clean.
    """
    if not text:
        return None
    cleaned = str(text).strip()
    if len(cleaned) < 2:
        return None

    # 1. Scam & Impersonation (Critical / High)
    for pat in _SCAM_IMPERSONATION_PATTERNS:
        match = pat.search(cleaned)
        if match:
            return {
                "category": CATEGORY_SCAM_IMPERSONATION,
                "severity": SEVERITY_HIGH if "zalo" in match.group(0).lower() else SEVERITY_CRITICAL,
                "source": f"text_scanner:{context}",
                "summary": f"Phát hiện dấu hiệu giả mạo ban quản trị hoặc thu thập thông tin trái phép: '{match.group(0)}'",
                "evidence_reference": cleaned[:120],
                "confidence_score": 0.95
            }

    # 2. Spam & Gambling / Crypto (High)
    for pat in _SPAM_PATTERNS:
        match = pat.search(cleaned)
        if match:
            return {
                "category": CATEGORY_SPAM,
                "severity": SEVERITY_HIGH,
                "source": f"text_scanner:{context}",
                "summary": f"Nội dung chứa từ khóa quảng cáo cờ bạc, vay nóng hoặc spam thương mại: '{match.group(0)}'",
                "evidence_reference": cleaned[:120],
                "confidence_score": 0.90
            }

    # 3. Harassment & Abusive Language (Medium to High)
    for pat in _HARASSMENT_PATTERNS:
        match = pat.search(cleaned)
        if match:
            return {
                "category": CATEGORY_HARASSMENT_ABUSE,
                "severity": SEVERITY_HIGH if any(w in cleaned.lower() for w in ["giết", "chó chết"]) else SEVERITY_MEDIUM,
                "source": f"text_scanner:{context}",
                "summary": f"Phát hiện ngôn từ thù địch, xúc phạm hoặc đe dọa: '{match.group(0)}'",
                "evidence_reference": cleaned[:120],
                "confidence_score": 0.88
            }

    # 4. Content Unrelated to Agricultural Use (Low / Medium)
    for pat in _NON_AGRI_PATTERNS:
        match = pat.search(cleaned)
        if match:
            return {
                "category": CATEGORY_NON_AGRICULTURAL,
                "severity": SEVERITY_MEDIUM,
                "source": f"text_scanner:{context}",
                "summary": f"Nội dung hoàn toàn không liên quan đến mục đích nông nghiệp của GARI: '{match.group(0)}'",
                "evidence_reference": cleaned[:120],
                "confidence_score": 0.85
            }

    return None


def scan_uploaded_file(
    filename: str,
    file_bytes: bytes,
    mime_type: Optional[str] = None,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Inspect uploaded files for potential security hazards:
    - Executable scripts (.exe, .php, .py, .sh, .bat, etc.)
    - Disguised polyglot binaries with embedded scripts
    - Corrupted or excessively oversized files (>25MB)
    """
    fn_lower = (filename or "").lower().strip()
    ext = "." + fn_lower.split(".")[-1] if "." in fn_lower else ""

    # 1. Prohibited Executable Extensions
    if ext in _PROHIBITED_EXTENSIONS:
        return {
            "category": CATEGORY_UNSAFE_UPLOAD,
            "severity": SEVERITY_CRITICAL,
            "source": "upload_file_scanner",
            "summary": f"Tệp tải lên mang định dạng thực thi nguy hiểm ({ext}) bị cấm tuyệt đối.",
            "evidence_reference": f"Filename: {filename}",
            "confidence_score": 1.0
        }

    # 2. Magic byte / script injection checks in image files
    sample_header = file_bytes[:512].lower() if file_bytes else b""
    if b"<?php" in sample_header or b"<script" in sample_header or b"#!/bin/" in sample_header:
        return {
            "category": CATEGORY_UNSAFE_UPLOAD,
            "severity": SEVERITY_CRITICAL,
            "source": "upload_file_scanner:deep_inspect",
            "summary": f"Tệp hình ảnh chứa mã độc hại hoặc script nhúng nguy hiểm trong header.",
            "evidence_reference": f"Filename: {filename} (Script payload detected)",
            "confidence_score": 0.99
        }

    # 3. Executable binary signature (MZ / ELF)
    if file_bytes and (file_bytes.startswith(b"MZ") or file_bytes.startswith(b"\x7fELF")):
        return {
            "category": CATEGORY_UNSAFE_UPLOAD,
            "severity": SEVERITY_CRITICAL,
            "source": "upload_file_scanner:binary_check",
            "summary": f"Tệp hình ảnh giả mạo nhị phân thực thi hệ thống (MZ/ELF header).",
            "evidence_reference": f"Filename: {filename}",
            "confidence_score": 1.0
        }

    # 4. Excessive file size (> 25MB)
    if len(file_bytes) > 25 * 1024 * 1024:
        return {
            "category": CATEGORY_UNSAFE_UPLOAD,
            "severity": SEVERITY_LOW,
            "source": "upload_file_scanner:size_limit",
            "summary": f"Dung lượng tệp vượt ngưỡng an toàn cho phép ({round(len(file_bytes)/(1024*1024), 1)}MB > 25MB).",
            "evidence_reference": f"Filename: {filename}",
            "confidence_score": 0.90
        }

    return None


def scan_api_activity(
    user_id: Optional[int],
    user_email: Optional[str],
    endpoint: str,
    client_ip: str,
    is_voucher_failure: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Monitor rapid API request velocity and voucher brute-force attempts.
    """
    now = time.time()
    identifier = f"user_{user_id}" if user_id else f"ip_{client_ip}"

    # 1. Voucher brute-force check
    if is_voucher_failure:
        attempts = _VOUCHER_FAILURES_TRACKER.get(identifier, [])
        attempts = [t for t in attempts if now - t < 600]  # 10 min window
        attempts.append(now)
        _VOUCHER_FAILURES_TRACKER[identifier] = attempts
        if len(attempts) >= 5:
            return {
                "category": CATEGORY_API_ABUSE,
                "severity": SEVERITY_HIGH,
                "source": "api_sentinel:voucher_guard",
                "summary": f"Phát hiện hành vi đoán mò hoặc lạm dụng mã voucher ({len(attempts)} lần thất bại liên tiếp).",
                "evidence_reference": f"Target: {endpoint} | IP: {client_ip}",
                "confidence_score": 0.95
            }

    # 2. General request burst velocity
    records = _API_ACTIVITY_TRACKER.get(identifier, [])
    records = [t for t in records if now - t < ACTIVITY_WINDOW_SECONDS]
    records.append(now)
    _API_ACTIVITY_TRACKER[identifier] = records

    if len(records) >= BURST_THRESHOLD:
        return {
            "category": CATEGORY_API_ABUSE,
            "severity": SEVERITY_MEDIUM,
            "source": "api_sentinel:rate_monitor",
            "summary": f"Tần suất gửi yêu cầu bất thường ({len(records)} requests/phút) vượt ngưỡng an toàn.",
            "evidence_reference": f"Endpoint: {endpoint} | IP: {client_ip}",
            "confidence_score": 0.85
        }

    return None


# -----------------------------------------------------------------------------
# 2. Case Generation & Pipeline Storage
# -----------------------------------------------------------------------------

def create_moderation_case(
    user_id: int,
    user_email: str,
    category: Optional[str] = None,
    severity: str = SEVERITY_MEDIUM,
    source: str = "automated_rule",
    evidence_summary: str = "",
    evidence_reference: Optional[str] = None,
    confidence_score: float = 1.0,
    *,
    violation_category: Optional[str] = None,
    detection_source: Optional[str] = None,
    evidence_ref: Optional[str] = None
) -> Dict[str, Any]:
    """
    Stores an automated detection case in moderation_cases.
    CRITICAL SAFETY GUARANTEE:
    Automated detection NEVER automatically issues permanent account bans or suspensions.
    The case is saved in 'pending' status for Host human review.
    """
    if category is None and violation_category:
        category = violation_category
    if (not source or source == "automated_rule") and detection_source:
        source = detection_source
    if evidence_reference is None and evidence_ref:
        evidence_reference = evidence_ref

    category = category or CATEGORY_SPAM
    if category not in VALID_CATEGORIES:
        category = CATEGORY_SPAM
    if severity not in VALID_SEVERITIES:
        severity = SEVERITY_MEDIUM

    # Generate unique readable Case ID
    case_uid = secrets.token_hex(4).upper()
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    case_id = f"MOD-{date_str}-{case_uid}"

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()

        # Check previous violations for repeated violation escalation
        cursor.execute(
            """
            SELECT count(*) FROM moderation_cases
            WHERE user_id = ? AND status IN ('warned', 'restricted', 'suspended', 'pending')
            """,
            (user_id,)
        )
        prev_violation_count = cursor.fetchone()[0]

        effective_severity = severity
        if prev_violation_count >= 2 and severity in (SEVERITY_LOW, SEVERITY_MEDIUM):
            effective_severity = SEVERITY_HIGH
            evidence_summary += f" [Cảnh báo: Tài khoản đã có {prev_violation_count} ca vi phạm trước đó]."

        now_iso = now_utc_iso()
        cursor.execute(
            """
            INSERT INTO moderation_cases (
                case_id, user_id, user_email, violation_category, severity,
                detection_source, evidence_summary, evidence_reference,
                confidence_score, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                case_id, user_id, user_email, category, effective_severity,
                source, evidence_summary, evidence_reference,
                float(confidence_score), now_iso, now_iso
            )
        )
        conn.commit()

        cursor.execute("SELECT * FROM moderation_cases WHERE case_id = ?", (case_id,))
        case_data = dict(cursor.fetchone())

    logger.warning(
        "Created Moderation Case %s for user #%d (%s): %s [%s]",
        case_id, user_id, user_email, category, effective_severity
    )
    return case_data


# -----------------------------------------------------------------------------
# 3. Host Moderation Actions & Review Queue
# -----------------------------------------------------------------------------

def scan_content_and_report(
    user_id: int,
    user_email: str,
    content_type: str,
    text: str,
    evidence_ref: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience method: scans content and if violation detected,
    creates and persists a pending moderation case.
    """
    viol = scan_content_text(text, context=content_type, user_id=user_id, user_email=user_email)
    if viol:
        return create_moderation_case(
            user_id=user_id,
            user_email=user_email,
            category=viol["category"],
            severity=viol["severity"],
            source=viol["source"],
            evidence_summary=viol["summary"],
            evidence_reference=evidence_ref or viol.get("evidence_reference"),
            confidence_score=viol.get("confidence_score", 0.9)
        )
    return None


def list_moderation_cases(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """Retrieve filtered, paginated moderation cases for Host Console review queue."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = """
        SELECT c.*, u.moderation_status as user_current_moderation_status,
               u.is_active as user_is_active, u.account_type as user_account_type
        FROM moderation_cases c
        LEFT JOIN users u ON c.user_id = u.id
        WHERE 1=1
    """
    params: List[Any] = []

    if user_id is not None:
        query += " AND c.user_id = ?"
        params.append(user_id)
    if status:
        query += " AND c.status = ?"
        params.append(status.strip().lower())
    if severity:
        query += " AND c.severity = ?"
        params.append(severity.strip().lower())
    if category:
        query += " AND c.violation_category = ?"
        params.append(category.strip().lower())
    if search:
        st = f"%{search.strip().lower()}%"
        query += " AND (LOWER(c.case_id) LIKE ? OR LOWER(c.user_email) LIKE ? OR CAST(c.user_id AS TEXT) = ?)"
        params.extend([st, st, search.strip()])

    count_query = f"SELECT count(*) FROM ({query})"

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        total = cursor.execute(count_query, params).fetchone()[0]

        query += " ORDER BY CASE c.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, c.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        cases = [dict(r) for r in cursor.fetchall()]

    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "cases": cases
    }


def get_moderation_case(case_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full detail for a single moderation case including past user record."""
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM moderation_cases WHERE case_id = ?", (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        case = dict(row)

        # Retrieve previous confirmed violations for this user
        cursor.execute(
            """
            SELECT id, case_id, violation_category, severity, status, reviewed_at
            FROM moderation_cases
            WHERE user_id = ? AND case_id != ?
            ORDER BY id DESC LIMIT 10
            """,
            (case["user_id"], case_id)
        )
        case["user_history"] = [dict(r) for r in cursor.fetchall()]

        # User profile snippet
        cursor.execute(
            "SELECT id, email, full_name, account_type, moderation_status, feature_restrictions, is_active FROM users WHERE id = ?",
            (case["user_id"],)
        )
        u_row = cursor.fetchone()
        case["user_profile"] = dict(u_row) if u_row else None

    return case


def resolve_moderation_case(
    case_id: str,
    action: str,
    host_admin_id: int,
    host_email: str,
    reason: str,
    restrictions: Optional[str] = None,
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """
    Authorized Host Administrator applies moderation action to a case.
    Supported actions:
    - 'dismiss': Dismiss case as non-actionable
    - 'false_positive': Mark detection as false positive. Restores user to clean status if flagged.
    - 'warn': Issue official warning.
    - 'restrict': Temporarily restrict selected features (e.g. upload_restricted).
    - 'suspend': Temporarily suspend user account (is_active = 0, invalidates sessions).
    - 'ban': Permanently ban user account (is_active = 0, moderation_status = 'banned').
    - 'restore': Restore account to active, clean status.
    """
    action = (action or "").strip().lower()
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp lý do rõ ràng (tối thiểu 3 ký tự) để xử lý kiểm duyệt."
        )

    allowed_actions = {"dismiss", "false_positive", "warn", "restrict", "suspend", "ban", "restore"}
    if action not in allowed_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hành động kiểm duyệt không hợp lệ. Phải là một trong: {', '.join(sorted(allowed_actions))}."
        )

    now_iso = now_utc_iso()

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM moderation_cases WHERE case_id = ?", (case_id,))
        case_row = cursor.fetchone()
        if not case_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy hồ sơ vi phạm.")

        case = dict(case_row)
        user_id = case["user_id"]

        # Fetch current user state
        cursor.execute(
            "SELECT id, email, is_active, moderation_status, feature_restrictions, is_host_admin FROM users WHERE id = ?",
            (user_id,)
        )
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng.")

        user = dict(user_row)
        prev_mod_status = user.get("moderation_status") or "clean"
        prev_is_active = user.get("is_active", 1)

        # Host admin safety guard: cannot suspend or ban yourself
        if user_id == host_admin_id and action in ("suspend", "ban", "restrict"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quản trị viên máy chủ không thể tự kỷ luật hoặc khóa tài khoản của chính mình."
            )

        new_mod_status = prev_mod_status
        new_is_active = prev_is_active
        new_restrictions = user.get("feature_restrictions") or ""
        case_status = case["status"]

        if action == "dismiss":
            case_status = STATUS_DISMISSED
        elif action == "false_positive":
            case_status = STATUS_FALSE_POSITIVE
            # If user had been restricted from this issue, clear restriction
            new_mod_status = "clean"
            new_restrictions = ""
        elif action == "warn":
            case_status = STATUS_WARNED
            new_mod_status = STATUS_WARNED
        elif action == "restrict":
            case_status = STATUS_RESTRICTED
            new_mod_status = STATUS_RESTRICTED
            new_restrictions = restrictions or RESTRICTION_UPLOAD
        elif action == "suspend":
            case_status = STATUS_SUSPENDED
            new_mod_status = STATUS_SUSPENDED
            new_is_active = 0
        elif action == "ban":
            case_status = STATUS_BANNED
            new_mod_status = STATUS_BANNED
            new_is_active = 0
        elif action == "restore":
            case_status = STATUS_DISMISSED
            new_mod_status = "clean"
            new_is_active = 1
            new_restrictions = ""

        # Update case
        cursor.execute(
            """
            UPDATE moderation_cases
            SET status = ?, decision_notes = ?, reviewed_by_host_id = ?, reviewed_at = ?, updated_at = ?
            WHERE case_id = ?
            """,
            (case_status, reason, host_admin_id, now_iso, now_iso, case_id)
        )

        # Update user
        cursor.execute(
            """
            UPDATE users
            SET moderation_status = ?, is_active = ?, feature_restrictions = ?, moderation_reason = ?, moderation_updated_at = ?
            WHERE id = ?
            """,
            (new_mod_status, new_is_active, new_restrictions, reason, now_iso, user_id)
        )

        # If suspending or banning, immediately purge user active sessions
        if new_is_active == 0:
            cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))

        # Record into moderation_audit_logs
        cursor.execute(
            """
            INSERT INTO moderation_audit_logs (
                case_id, target_user_id, target_email, actor_admin_id, actor_email,
                action, reason, previous_status, resulting_status, details_json,
                ip_address, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id, user_id, user["email"], host_admin_id, host_email,
                action, reason, prev_mod_status, new_mod_status,
                json.dumps({"restrictions": new_restrictions, "is_active": new_is_active}, ensure_ascii=False),
                ip_address, now_iso
            )
        )

        # Also mirror into host_audit_logs
        cursor.execute(
            """
            INSERT INTO host_audit_logs (
                host_admin_id, host_email, action_type, target_resource,
                details_json, reason, outcome, ip_address, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'success', ?, ?)
            """,
            (
                host_admin_id, host_email, f"moderation_{action}", f"user:{user_id}",
                json.dumps({"case_id": case_id, "previous": prev_mod_status, "new": new_mod_status}, ensure_ascii=False),
                reason, ip_address, now_iso
            )
        )

        conn.commit()

    logger.info(
        "Host Admin #%d applied '%s' on case %s (User #%d %s): %s -> %s",
        host_admin_id, action, case_id, user_id, user["email"], prev_mod_status, new_mod_status
    )

    return {
        "success": True,
        "case_id": case_id,
        "action": action,
        "user_id": user_id,
        "case": {
            "case_id": case_id,
            "status": case_status,
            "moderation_status": new_mod_status
        },
        "moderation_status": new_mod_status,
        "is_active": bool(new_is_active),
        "feature_restrictions": new_restrictions,
        "message": f"Đã áp dụng quyết định '{action}' cho hồ sơ {case_id} thành công."
    }


# -----------------------------------------------------------------------------
# 4. Appeals Workflow
# -----------------------------------------------------------------------------

def submit_user_appeal(
    user_id: int,
    user_email: str,
    appeal_reason: str,
    case_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Allows a restricted, warned, suspended or banned user to submit an appeal.
    """
    reason = (appeal_reason or "").strip()
    if len(reason) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nội dung giải trình khiếu nại phải có tối thiểu 10 ký tự."
        )

    now_iso = now_utc_iso()

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()

        # Check existing pending appeal
        cursor.execute(
            "SELECT count(*) FROM moderation_appeals WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        if cursor.fetchone()[0] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bạn đã có một đơn khiếu nại đang chờ Quản trị viên máy chủ duyệt. Vui lòng kiên nhẫn chờ phản hồi."
            )

        cursor.execute(
            """
            INSERT INTO moderation_appeals (
                user_id, user_email, case_id, appeal_reason, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (user_id, user_email, case_id, reason, now_iso, now_iso)
        )
        conn.commit()
        appeal_id = cursor.lastrowid

    return {
        "success": True,
        "appeal_id": appeal_id,
        "appeal": {
            "id": appeal_id,
            "user_id": user_id,
            "user_email": user_email,
            "case_id": case_id,
            "appeal_reason": reason,
            "status": "pending",
            "created_at": now_iso
        },
        "message": "Đơn khiếu nại đã được gửi tới Quản trị viên máy chủ. Hồ sơ sẽ được xem xét công bằng theo quy định."
    }


def list_appeals(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """List appeals for Host review."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    query = """
        SELECT a.*, u.moderation_status, u.is_active, u.account_type
        FROM moderation_appeals a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE 1=1
    """
    params: List[Any] = []
    if status:
        query += " AND a.status = ?"
        params.append(status.strip().lower())

    count_query = f"SELECT count(*) FROM ({query})"

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        total = cursor.execute(count_query, params).fetchone()[0]

        query += " ORDER BY a.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        appeals = [dict(r) for r in cursor.fetchall()]

    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "appeals": appeals
    }


def review_appeal(
    appeal_id: int,
    decision: str,
    host_admin_id: int,
    host_email: str,
    host_response: str,
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """
    Host administrator reviews and processes an appeal ('approved' or 'rejected').
    If approved: restores account access (is_active = 1, moderation_status = 'clean').
    """
    decision = (decision or "").strip().lower()
    if decision not in ("approved", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quyết định khiếu nại phải là 'approved' hoặc 'rejected'."
        )

    response_text = (host_response or "").strip()
    if len(response_text) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp phản hồi giải thích (tối thiểu 3 ký tự)."
        )

    now_iso = now_utc_iso()

    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM moderation_appeals WHERE id = ?", (appeal_id,))
        appeal_row = cursor.fetchone()
        if not appeal_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn khiếu nại.")

        appeal = dict(appeal_row)
        user_id = appeal["user_id"]

        # Update appeal
        cursor.execute(
            """
            UPDATE moderation_appeals
            SET status = ?, host_response = ?, reviewed_by_host_id = ?, reviewed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (decision, response_text, host_admin_id, now_iso, now_iso, appeal_id)
        )

        # If approved, restore user access
        if decision == "approved":
            cursor.execute(
                """
                UPDATE users
                SET moderation_status = 'clean', is_active = 1, feature_restrictions = '',
                    moderation_reason = ?, moderation_updated_at = ?
                WHERE id = ?
                """,
                (f"Khiếu nại #{appeal_id} được phê duyệt: {response_text}", now_iso, user_id)
            )

        # Record audit log
        cursor.execute(
            """
            INSERT INTO moderation_audit_logs (
                case_id, target_user_id, target_email, actor_admin_id, actor_email,
                action, reason, details_json, ip_address, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                appeal.get("case_id"), user_id, appeal["user_email"], host_admin_id, host_email,
                f"appeal_{decision}", response_text,
                json.dumps({"appeal_id": appeal_id, "decision": decision}, ensure_ascii=False),
                ip_address, now_iso
            )
        )
        conn.commit()

    return {
        "success": True,
        "appeal_id": appeal_id,
        "decision": decision,
        "user_id": user_id,
        "appeal": {
            "id": appeal_id,
            "status": decision,
            "host_response": response_text
        },
        "message": f"Đã xử lý khiếu nại #{appeal_id}: {decision}."
    }


# -----------------------------------------------------------------------------
# 5. Backend Enforcement Helpers
# -----------------------------------------------------------------------------

def enforce_user_moderation_access(
    user: Optional[Dict[str, Any]],
    required_feature: Optional[str] = None
) -> None:
    """
    Enforces moderation decisions at the API level.
    Rejects banned/suspended users and blocks restricted features.
    """
    if not user:
        return

    mod_status = (user.get("moderation_status") or "clean").lower()
    is_active = user.get("is_active", 1)

    # 1. Permanently Banned
    if mod_status == STATUS_BANNED or (mod_status == STATUS_BANNED and is_active == 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị cấm vĩnh viễn do vi phạm nghiêm trọng chính sách GARI. Bạn có thể gửi khiếu nại để Quản trị viên xem xét."
        )

    # 2. Suspended
    if mod_status == STATUS_SUSPENDED or is_active == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đang bị tạm ngưng hoạt động do vi phạm chính sách sử dụng. Vui lòng liên hệ Quản trị viên máy chủ để được hỗ trợ."
        )

    # 3. Feature Restrictions
    if mod_status == STATUS_RESTRICTED and required_feature:
        restrictions = (user.get("feature_restrictions") or "").lower()
        if required_feature.lower() in restrictions:
            feature_names = {
                RESTRICTION_UPLOAD: "tải lên hình ảnh lá chẩn đoán",
                RESTRICTION_FEEDBACK: "gửi phản hồi đóng góp",
                RESTRICTION_CHAT: "nhắn tin trò chuyện với trợ lý"
            }
            label = feature_names.get(required_feature.lower(), required_feature)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tài khoản của bạn đang bị giới hạn tính năng '{label}' do cảnh báo vi phạm chính sách."
            )
