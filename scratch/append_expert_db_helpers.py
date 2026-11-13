import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('gari_database.py', 'r', encoding='utf-8') as f:
    content = f.read()

expert_helpers = '''

# -----------------------------------------------------------------------------
# GARI EXPERT NETWORK & NOTIFICATION REPOSITORY HELPERS
# -----------------------------------------------------------------------------

def create_expert_application(data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        primary_crops = data.get("primary_crops", [])
        if isinstance(primary_crops, list):
            primary_crops_json = json.dumps(primary_crops, ensure_ascii=False)
        else:
            primary_crops_json = str(primary_crops)

        regions = data.get("farming_regions", [])
        if isinstance(regions, list):
            regions_json = json.dumps(regions, ensure_ascii=False)
        else:
            regions_json = str(regions)

        cursor.execute("""
            INSERT INTO expert_applications (
                user_id, full_name, email, phone, institution, degree,
                specialization, primary_crops_json, farming_regions_json,
                bio, certificate_url, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted')
        """, (
            user_id,
            data.get("full_name", "").strip(),
            data.get("email", "").strip(),
            data.get("phone", "").strip(),
            data.get("institution", "").strip(),
            data.get("degree", "").strip(),
            data.get("specialization", "").strip(),
            primary_crops_json,
            regions_json,
            data.get("bio", "").strip(),
            data.get("certificate_url", "").strip()
        ))
        conn.commit()
        app_id = cursor.lastrowid
        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        return dict(cursor.fetchone())


def list_expert_applications(status: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM expert_applications WHERE status = ? ORDER BY id DESC", (status,))
        else:
            cursor.execute("SELECT * FROM expert_applications ORDER BY id DESC")
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["primary_crops"] = json.loads(d.get("primary_crops_json") or "[]")
            except Exception:
                d["primary_crops"] = []
            try:
                d["farming_regions"] = json.loads(d.get("farming_regions_json") or "[]")
            except Exception:
                d["farming_regions"] = []
            rows.append(d)
        return rows


def get_expert_application(app_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["primary_crops"] = json.loads(d.get("primary_crops_json") or "[]")
        except Exception:
            d["primary_crops"] = []
        try:
            d["farming_regions"] = json.loads(d.get("farming_regions_json") or "[]")
        except Exception:
            d["farming_regions"] = []
        return d


def review_expert_application(app_id: int, action: str, host_id: int, reason: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_applications WHERE id = ?", (app_id,))
        row = cursor.fetchone()
        if not row:
            return None
        app = dict(row)
        user_id = app["user_id"]

        if action == "approve":
            cursor.execute("""
                UPDATE expert_applications
                SET status = 'approved', reviewed_by_host_id = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (host_id, app_id))

            # Grant user expert role and is_expert flag
            cursor.execute("""
                UPDATE users
                SET is_expert = 1, account_type = 'Chuyên gia', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (user_id,))

            # Create or update expert profile
            cursor.execute("""
                INSERT INTO expert_profiles (
                    user_id, full_name, display_title, institution, degree,
                    specialization, primary_crops_json, farming_regions_json,
                    bio, verification_status, verified_by_host_id, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_title = excluded.display_title,
                    institution = excluded.institution,
                    degree = excluded.degree,
                    specialization = excluded.specialization,
                    primary_crops_json = excluded.primary_crops_json,
                    farming_regions_json = excluded.farming_regions_json,
                    bio = excluded.bio,
                    verification_status = 'approved',
                    verified_by_host_id = excluded.verified_by_host_id,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                user_id,
                app["full_name"],
                f"Chuyên gia Nông học ({app['degree']})",
                app["institution"],
                app["degree"],
                app["specialization"],
                app["primary_crops_json"],
                app["farming_regions_json"],
                app["bio"],
                host_id
            ))

            # Notify user
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Chúc mừng! Hồ sơ Chuyên gia đã được duyệt',
                        'Bạn đã được cấp quyền Chuyên gia Nông học chính thức trên GARI AI Lab. Hãy truy cập Expert Portal để tiếp nhận các ca chẩn đoán thực địa.',
                        'success', '/frontend2/expert-portal.html')
            """, (user_id,))

        elif action == "reject":
            cursor.execute("""
                UPDATE expert_applications
                SET status = 'rejected', rejection_reason = ?, reviewed_by_host_id = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (reason or "Hồ sơ xác minh chưa đủ điều kiện theo quy định của ban quản trị.", host_id, app_id))

            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Thông báo về hồ sơ đăng ký Chuyên gia',
                        ?, 'warning', '/frontend2/support.html')
            """, (user_id, f"Hồ sơ đăng ký chuyên gia của bạn chưa được phê duyệt. Lý do: {reason or 'Cần bổ sung thêm văn bằng chứng chỉ.'}"))

        conn.commit()
        return get_expert_application(app_id)


def list_expert_profiles(active_only: bool = True) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT ep.*, u.email, u.phone FROM expert_profiles ep JOIN users u ON ep.user_id = u.id WHERE ep.is_active = 1 ORDER BY ep.cases_resolved_count DESC")
        else:
            cursor.execute("SELECT ep.*, u.email, u.phone FROM expert_profiles ep JOIN users u ON ep.user_id = u.id ORDER BY ep.id DESC")
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["primary_crops"] = json.loads(d.get("primary_crops_json") or "[]")
            except Exception:
                d["primary_crops"] = []
            try:
                d["farming_regions"] = json.loads(d.get("farming_regions_json") or "[]")
            except Exception:
                d["farming_regions"] = []
            rows.append(d)
        return rows


def get_expert_profile(user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ep.*, u.email, u.phone FROM expert_profiles ep JOIN users u ON ep.user_id = u.id WHERE ep.user_id = ?", (user_id,))
        r = cursor.fetchone()
        if not r:
            return None
        d = dict(r)
        try:
            d["primary_crops"] = json.loads(d.get("primary_crops_json") or "[]")
        except Exception:
            d["primary_crops"] = []
        try:
            d["farming_regions"] = json.loads(d.get("farming_regions_json") or "[]")
        except Exception:
            d["farming_regions"] = []
        return d


def list_expert_cases_for_expert(expert_user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        # Returns cases assigned to this expert OR unassigned cases that need review
        if status:
            cursor.execute("""
                SELECT ec.*, u.full_name as farmer_account_name, u.email as farmer_email
                FROM expert_cases ec
                JOIN users u ON ec.user_id = u.id
                WHERE (ec.assigned_expert_id = ? OR ec.assigned_expert_id IS NULL)
                  AND ec.status = ?
                ORDER BY ec.id DESC
            """, (expert_user_id, status))
        else:
            cursor.execute("""
                SELECT ec.*, u.full_name as farmer_account_name, u.email as farmer_email
                FROM expert_cases ec
                JOIN users u ON ec.user_id = u.id
                WHERE ec.assigned_expert_id = ? OR ec.assigned_expert_id IS NULL
                ORDER BY ec.id DESC
            """, (expert_user_id,))
        return [dict(r) for r in cursor.fetchall()]


def claim_expert_case(case_id: int, expert_user_id: int, expert_name: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        case = dict(row)
        if case.get("assigned_expert_id") and case.get("assigned_expert_id") != expert_user_id:
            return None # Already assigned to another expert

        cursor.execute("""
            UPDATE expert_cases
            SET assigned_expert_id = ?, assigned_expert = ?, status = 'under_review', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (expert_user_id, expert_name, case_id))

        cursor.execute("""
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message)
            VALUES (?, ?, 'system', 'Hệ thống GARI', ?)
        """, (case_id, expert_user_id, f"Chuyên gia {expert_name} đã tiếp nhận hồ sơ chẩn đoán này."))

        # Notify farmer
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, target_url)
            VALUES (?, 'Chuyên gia đã tiếp nhận ca chẩn đoán',
                    ?, 'info', '/frontend2/support.html')
        """, (case["user_id"], f"Chuyên gia {expert_name} đã tiếp nhận ca bệnh {case.get('crop_name', 'cây trồng')} (#{case_id}) của bạn."))

        conn.commit()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        return dict(cursor.fetchone())


def add_expert_case_message(case_id: int, sender_user_id: int, sender_role: str, sender_name: str, message: str, attachments: Optional[List[str]] = None, is_internal_note: bool = False) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        att_json = json.dumps(attachments, ensure_ascii=False) if attachments else None
        cursor.execute("""
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message, attachments_json, is_internal_note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (case_id, sender_user_id, sender_role, sender_name, message.strip(), att_json, 1 if is_internal_note else 0))

        # Update case status if expert replied
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        case = dict(cursor.fetchone())

        if sender_role == "expert":
            new_status = "answered"
            cursor.execute("UPDATE expert_cases SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, case_id))
            # Notify farmer
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Chuyên gia nông học đã gửi tư vấn mới',
                        ?, 'success', '/frontend2/support.html')
            """, (case["user_id"], f"Chuyên gia {sender_name} đã phản hồi cho ca bệnh #{case_id} ({case.get('crop_name', 'Cây trồng')})."))
        elif sender_role == "farmer":
            new_status = "under_review"
            cursor.execute("UPDATE expert_cases SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_status, case_id))
            if case.get("assigned_expert_id"):
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                    VALUES (?, 'Nông dân đã gửi tin nhắn bổ sung',
                            ?, 'info', '/frontend2/expert-portal.html')
                """, (case["assigned_expert_id"], f"Nông dân {sender_name} đã gửi câu hỏi bổ sung cho hồ sơ #{case_id}."))

        conn.commit()
        msg_id = cursor.lastrowid
        cursor.execute("SELECT * FROM expert_case_messages WHERE id = ?", (msg_id,))
        return dict(cursor.fetchone())


def get_expert_case_messages(case_id: int, include_internal: bool = False) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if include_internal:
            cursor.execute("SELECT * FROM expert_case_messages WHERE case_id = ? ORDER BY id ASC", (case_id,))
        else:
            cursor.execute("SELECT * FROM expert_case_messages WHERE case_id = ? AND is_internal_note = 0 ORDER BY id ASC", (case_id,))
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            try:
                d["attachments"] = json.loads(d.get("attachments_json") or "[]")
            except Exception:
                d["attachments"] = []
            rows.append(d)
        return rows


def resolve_expert_case(case_id: int, expert_user_id: int, resolution_notes: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        if not row:
            return None
        case = dict(row)

        cursor.execute("""
            UPDATE expert_cases
            SET status = 'resolved', resolution_notes = ?, resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (resolution_notes.strip(), case_id))

        cursor.execute("""
            UPDATE expert_profiles
            SET cases_resolved_count = cases_resolved_count + 1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (expert_user_id,))

        cursor.execute("""
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message)
            VALUES (?, ?, 'system', 'Hệ thống GARI', ?)
        """, (case_id, expert_user_id, f"Ca bệnh đã được Chuyên gia đánh dấu giải quyết hoàn tất: {resolution_notes}"))

        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, target_url)
            VALUES (?, 'Hồ sơ tư vấn chuyên gia đã hoàn tất',
                    ?, 'success', '/frontend2/support.html')
        """, (case["user_id"], f"Hồ sơ #{case_id} đã được chuyên gia kết luận giải quyết."))

        conn.commit()
        cursor.execute("SELECT * FROM expert_cases WHERE id = ?", (case_id,))
        return dict(cursor.fetchone())


def create_notification(user_id: int, title: str, message: str, notification_type: str = 'info', target_url: Optional[str] = None) -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, notification_type, target_url)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, title.strip(), message.strip(), notification_type, target_url))
        conn.commit()
        nid = cursor.lastrowid
        cursor.execute("SELECT * FROM notifications WHERE id = ?", (nid,))
        return dict(cursor.fetchone())


def list_user_notifications(user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        return [dict(r) for r in cursor.fetchall()]


def mark_notification_read(notif_id: int, user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, user_id))
        conn.commit()
        return cursor.rowcount > 0


def mark_all_notifications_read(user_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
        conn.commit()
        return cursor.rowcount
'''

if "def create_expert_application" not in content:
    content += expert_helpers
    with open('gari_database.py', 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    print("Appended expert network helpers to gari_database.py successfully!")
else:
    print("Expert network helpers already present in gari_database.py")
