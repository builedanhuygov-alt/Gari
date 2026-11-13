"""
GARI Module 06 — Cultivation Tasks & Smart Crop Calendar Engine
Authoritative service layer for farm tasks, crop calendar, recurring jobs,
RBAC authorization, diagnosis linking, activity logging, and observable reminders.
"""

import sqlite3
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
import logging
import json

from gari_database import get_connection

logger = logging.getLogger("gari.tasks")

# Standard date format
DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"

VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
VALID_RECURRENCE_RULES = {"none", "daily", "weekly", "biweekly", "monthly"}
VALID_TASK_TYPES = {
    "fertilizing", "watering", "spraying", "scouting",
    "pruning", "harvesting", "treatment", "routine", "planting"
}


# ---------------------------------------------------------------------------
# Helper: Activity Logging
# ---------------------------------------------------------------------------

def log_task_activity(
    task_id: int,
    actor_user_id: Optional[int],
    action: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    notes: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None
) -> None:
    """Log an audit entry for a task change."""
    try:
        if conn is not None:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO task_activities (
                    task_id, actor_user_id, action, old_value, new_value, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (task_id, actor_user_id, action, old_value, new_value, notes))
        else:
            with get_connection() as c:
                cursor = c.cursor()
                cursor.execute("""
                    INSERT INTO task_activities (
                        task_id, actor_user_id, action, old_value, new_value, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (task_id, actor_user_id, action, old_value, new_value, notes))
                c.commit()
    except Exception as e:
        logger.error(f"Error logging task activity for task {task_id}: {e}")


def get_task_activities(task_id: int) -> List[Dict[str, Any]]:
    """Retrieve full audit history for a task."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, u.full_name as actor_name, u.email as actor_email
            FROM task_activities a
            LEFT JOIN users u ON a.actor_user_id = u.id
            WHERE a.task_id = ?
            ORDER BY a.created_at ASC, a.id ASC
        """, (task_id,))
        return [dict(r) for r in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Helper: User Org & Role Resolution
# ---------------------------------------------------------------------------

def get_user_org_membership(user_id: int, org_id: int) -> Optional[Dict[str, Any]]:
    """Check user's membership and role in an organization."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # 1. Check if user is owner of the organization
        cursor.execute("SELECT owner_id, name FROM organizations WHERE id = ?", (org_id,))
        org = cursor.fetchone()
        if org and org["owner_id"] == user_id:
            return {"role": "owner", "org_id": org_id, "is_owner": True, "org_name": org["name"]}

        # 2. Check organization_members table
        cursor.execute("""
            SELECT role FROM organization_members
            WHERE organization_id = ? AND user_id = ?
        """, (org_id, user_id))
        mem = cursor.fetchone()
        if mem:
            return {"role": mem["role"], "org_id": org_id, "is_owner": False, "org_name": org["name"] if org else ""}

    return None


def verify_task_permission(
    task: Dict[str, Any],
    user_id: int,
    action: str  # 'view', 'update', 'complete', 'delete', 'assign'
) -> Tuple[bool, str]:
    """
    Check if user_id is authorized to perform action on task.
    Returns (is_allowed, error_message).
    """
    org_id = task.get("organization_id")

    # 1. Personal task (no org)
    if not org_id:
        if task.get("user_id") == user_id or task.get("assignee_user_id") == user_id:
            return True, ""
        return False, "Bạn không có quyền truy cập công việc cá nhân này."

    # 2. Organization-scoped task
    mem = get_user_org_membership(user_id, org_id)
    if not mem:
        return False, "Bạn không thuộc tổ chức sở hữu công việc này."

    role = mem.get("role", "viewer")

    # Owner, Admin, Farm Manager have full access
    if role in ("owner", "admin", "farm_manager"):
        return True, ""

    # Agronomist can view, update, complete, and assign tasks, and delete their own created tasks
    if role == "agronomist":
        if action in ("view", "update", "complete", "assign"):
            return True, ""
        if action == "delete" and task.get("creator_user_id") == user_id:
            return True, ""
        return False, "Kỹ sư nông học chỉ có thể xóa công việc do chính mình tạo."

    # Field Worker: can view, complete, and update status of assigned tasks
    if role == "field_worker":
        if action == "view":
            return True, ""
        if action == "complete" or action == "update":
            # Can update status or notes if assigned or created
            if task.get("assignee_user_id") == user_id or task.get("creator_user_id") == user_id:
                return True, ""
            return False, "Công nhân hiện trường chỉ có thể cập nhật công việc được phân công cho mình."
        if action in ("delete", "assign"):
            return False, "Công nhân hiện trường không có quyền phân công lại hoặc xóa công việc."

    # Viewer: read-only
    if role == "viewer":
        if action == "view":
            return True, ""
        return False, "Tài khoản người xem (Viewer) chỉ có quyền đọc dữ liệu."

    return False, "Không đủ quyền thực hiện thao tác."


# ---------------------------------------------------------------------------
# Core Operations: Create Task
# ---------------------------------------------------------------------------

def create_task(
    data: Dict[str, Any],
    creator_user_id: int,
    org_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a cultivation task manually or from a diagnosis.
    Enforces hierarchy validation, diagnosis linking, and activity logging.
    """
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Tiêu đề công việc là bắt buộc.")

    # Due date parsing and validation
    due_date = data.get("due_date")
    if not due_date:
        due_date = datetime.now(timezone.utc).strftime(DATE_FMT)
    else:
        # Standardize YYYY-MM-DD
        due_date = str(due_date)[:10]

    farm_id = data.get("farm_id")
    plot_id = data.get("plot_id")
    cycle_id = data.get("cycle_id") or data.get("crop_cycle_id")
    plant_id = data.get("plant_id")
    diagnosis_id = data.get("diagnosis_id")
    crop_id = data.get("crop_id") or "Tomato"
    if isinstance(crop_id, dict):
        crop_id = crop_id.get("id") or crop_id.get("name_vi") or "Tomato"

    priority = (data.get("priority") or "medium").lower()
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    status = (data.get("status") or "pending").lower()
    if status not in VALID_STATUSES:
        status = "pending"

    task_type = (data.get("task_type") or "routine").lower()
    if task_type not in VALID_TASK_TYPES:
        task_type = "routine"

    recurrence_rule = (data.get("recurrence_rule") or "none").lower()
    if recurrence_rule not in VALID_RECURRENCE_RULES:
        recurrence_rule = "none"

    recurrence_interval = int(data.get("recurrence_interval") or 1)
    description = (data.get("description") or "").strip()
    notes = (data.get("notes") or "").strip()

    # Scope resolution: if farm belongs to an organization, inherit org_id
    with get_connection() as conn:
        cursor = conn.cursor()

        if farm_id:
            cursor.execute("SELECT id, organization_id, user_id FROM farms WHERE id = ?", (farm_id,))
            farm_row = cursor.fetchone()
            if farm_row and farm_row["organization_id"]:
                org_id = farm_row["organization_id"]

        # Validate hierarchy relationships
        if farm_id and plot_id:
            cursor.execute("SELECT id FROM farm_plots WHERE id = ? AND farm_id = ?", (plot_id, farm_id))
            if not cursor.fetchone():
                raise ValueError(f"Lô canh tác #{plot_id} không thuộc Nông trại #{farm_id}.")

        # Assignee resolution and membership check
        assignee_user_id = data.get("assignee_user_id") or creator_user_id
        if org_id and assignee_user_id != creator_user_id:
            mem = get_user_org_membership(assignee_user_id, org_id)
            if not mem:
                raise ValueError(f"Người được phân công (User #{assignee_user_id}) không thuộc tổ chức này.")

        # Diagnosis linking validation
        if diagnosis_id:
            cursor.execute("SELECT id, crop_id, predicted_disease, disease_name_vi, severity, confidence FROM diagnoses WHERE id = ?", (diagnosis_id,))
            diag = cursor.fetchone()
            if diag:
                if not data.get("crop_id") and diag["crop_id"]:
                    crop_id = diag["crop_id"]
                if not data.get("description"):
                    disease_name = diag["disease_name_vi"] or diag["predicted_disease"]
                    conf = diag["confidence"] or 0.0
                    description = f"Nhiệm vụ điều trị phát sinh từ chẩn đoán AI #{diagnosis_id}: {disease_name} (Độ tin cậy: {conf*100:.1f}%)."
                task_type = "treatment"

        cursor.execute("""
            INSERT INTO cultivation_tasks (
                user_id, organization_id, farm_id, plot_id, crop_id,
                title, description, due_date, priority, status, task_type,
                creator_user_id, assignee_user_id, notes,
                diagnosis_id, cycle_id, crop_cycle_id, plant_id,
                recurrence_rule, recurrence_interval, reminder_status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            creator_user_id, org_id, farm_id, plot_id, crop_id,
            title, description, due_date, priority, status, task_type,
            creator_user_id, assignee_user_id, notes,
            diagnosis_id, cycle_id, cycle_id, plant_id,
            recurrence_rule, recurrence_interval
        ))
        conn.commit()
        task_id = cursor.lastrowid

    # Log activity
    log_task_activity(
        task_id=task_id,
        actor_user_id=creator_user_id,
        action="created",
        new_value=status,
        notes=f"Tạo công việc: '{title}'. Hạn: {due_date}. Ưu tiên: {priority}."
    )

    if assignee_user_id != creator_user_id:
        log_task_activity(
            task_id=task_id,
            actor_user_id=creator_user_id,
            action="assigned",
            new_value=str(assignee_user_id),
            notes=f"Phân công cho người dùng #{assignee_user_id}."
        )

    return get_task(task_id, user_id=creator_user_id)


def create_task_from_diagnosis(
    diagnosis_id: int,
    user_id: int,
    custom_title: Optional[str] = None,
    due_date: Optional[str] = None,
    priority: Optional[str] = None,
    notes: Optional[str] = None,
    assignee_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a connected treatment or scouting task directly from an AI leaf diagnosis.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM diagnoses WHERE id = ?", (diagnosis_id,))
        diag = cursor.fetchone()
        if not diag:
            raise ValueError(f"Không tìm thấy chẩn đoán #{diagnosis_id}.")
        diag = dict(diag)

    disease_name = diag.get("disease_name_vi") or diag.get("predicted_disease") or "Bệnh lá"
    crop_name = diag.get("crop_name") or diag.get("crop_id") or "Cây trồng"
    confidence = diag.get("confidence") or 0.0

    task_title = custom_title or f"Phòng trừ {disease_name} trên {crop_name}"
    task_priority = priority or ("urgent" if (diag.get("severity") or "").upper() in ("HIGH", "CRITICAL") or confidence > 0.85 else "high")
    task_due_date = due_date or (datetime.now(timezone.utc) + timedelta(days=2)).strftime(DATE_FMT)

    task_payload = {
        "title": task_title,
        "description": f"Công việc xử lý bệnh cây tự động đề xuất từ kết quả chẩn đoán AI #{diagnosis_id} ({disease_name}, độ tin cậy {confidence*100:.1f}%).",
        "crop_id": diag.get("crop_id") or "Tomato",
        "farm_id": diag.get("farm_id"),
        "plot_id": diag.get("plot_id") or diag.get("farm_plot_id"),
        "cycle_id": diag.get("crop_cycle_id"),
        "plant_id": diag.get("plant_id"),
        "diagnosis_id": diagnosis_id,
        "priority": task_priority,
        "task_type": "treatment",
        "due_date": task_due_date,
        "notes": notes or diag.get("user_notes") or "",
        "assignee_user_id": assignee_user_id or user_id,
        "organization_id": diag.get("organization_id")
    }

    return create_task(task_payload, creator_user_id=user_id, org_id=diag.get("organization_id"))


# ---------------------------------------------------------------------------
# Core Operations: Get, Update, Complete, Delete
# ---------------------------------------------------------------------------

def get_task(task_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieve task details with joined entity names and activity count."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*,
                   f.name as farm_name,
                   p.plot_name,
                   u_creator.full_name as creator_name,
                   u_creator.email as creator_email,
                   u_assignee.full_name as assignee_name,
                   u_assignee.email as assignee_email,
                   d.disease_name_vi as diagnosis_disease_vi,
                   d.predicted_disease as diagnosis_disease,
                   d.confidence as diagnosis_confidence
            FROM cultivation_tasks t
            LEFT JOIN farms f ON t.farm_id = f.id
            LEFT JOIN farm_plots p ON t.plot_id = p.id
            LEFT JOIN users u_creator ON t.creator_user_id = u_creator.id
            LEFT JOIN users u_assignee ON t.assignee_user_id = u_assignee.id
            LEFT JOIN diagnoses d ON t.diagnosis_id = d.id
            WHERE t.id = ?
        """, (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        task = dict(row)

        if user_id is not None:
            allowed, msg = verify_task_permission(task, user_id, action="view")
            if not allowed:
                return None

        # Attach activity history
        cursor.execute("""
            SELECT a.*, u.full_name as actor_name
            FROM task_activities a
            LEFT JOIN users u ON a.actor_user_id = u.id
            WHERE a.task_id = ?
            ORDER BY a.created_at ASC
        """, (task_id,))
        task["activities"] = [dict(r) for r in cursor.fetchall()]
        return task


def update_task(
    task_id: int,
    data: Dict[str, Any],
    user_id: int
) -> Dict[str, Any]:
    """
    Update task with RBAC permission enforcement and activity audit logging.
    """
    task = get_task(task_id, user_id=user_id)
    if not task:
        raise ValueError(f"Không tìm thấy công việc #{task_id} hoặc bạn không có quyền truy cập.")

    allowed, err = verify_task_permission(task, user_id, action="update")
    if not allowed:
        raise PermissionError(err)

    org_id = task.get("organization_id")
    updates = []
    params = []

    # Check reassignment permission
    if "assignee_user_id" in data and data["assignee_user_id"] != task.get("assignee_user_id"):
        assign_allowed, assign_err = verify_task_permission(task, user_id, action="assign")
        if not assign_allowed:
            raise PermissionError(assign_err)

        new_assignee = data["assignee_user_id"]
        if org_id and new_assignee:
            if not get_user_org_membership(new_assignee, org_id):
                raise ValueError(f"Người dùng #{new_assignee} không thuộc tổ chức.")

        updates.append("assignee_user_id = ?")
        params.append(new_assignee)
        log_task_activity(
            task_id=task_id,
            actor_user_id=user_id,
            action="assigned",
            old_value=str(task.get("assignee_user_id")),
            new_value=str(new_assignee),
            notes=f"Thay đổi người phụ trách sang User #{new_assignee}."
        )

    # Status change
    if "status" in data and data["status"] != task.get("status"):
        new_status = data["status"].lower()
        if new_status in VALID_STATUSES:
            updates.append("status = ?")
            params.append(new_status)
            if new_status == "completed" and not task.get("completed_at"):
                updates.append("completed_at = CURRENT_TIMESTAMP")
                updates.append("completed_by_user_id = ?")
                params.append(user_id)
            log_task_activity(
                task_id=task_id,
                actor_user_id=user_id,
                action="status_changed",
                old_value=task.get("status"),
                new_value=new_status,
                notes=f"Chuyển trạng thái từ '{task.get('status')}' sang '{new_status}'."
            )

    # Due date change
    if "due_date" in data and data["due_date"] != task.get("due_date"):
        new_due = str(data["due_date"])[:10]
        updates.append("due_date = ?")
        params.append(new_due)
        log_task_activity(
            task_id=task_id,
            actor_user_id=user_id,
            action="rescheduled",
            old_value=task.get("due_date"),
            new_value=new_due,
            notes=f"Đổi hạn chót từ {task.get('due_date')} sang {new_due}."
        )

    # Generic updatable fields
    for field in ("title", "description", "priority", "task_type", "notes", "crop_id", "recurrence_rule", "recurrence_interval"):
        if field in data and data[field] != task.get(field):
            updates.append(f"{field} = ?")
            params.append(data[field])

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(task_id)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE cultivation_tasks
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            conn.commit()

    return get_task(task_id, user_id=user_id)


def complete_task(
    task_id: int,
    user_id: int,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Mark a task as completed. If recurring, automatically schedule the next occurrence.
    """
    task = get_task(task_id, user_id=user_id)
    if not task:
        raise ValueError(f"Không tìm thấy công việc #{task_id}.")

    allowed, err = verify_task_permission(task, user_id, action="complete")
    if not allowed:
        raise PermissionError(err)

    now_iso = datetime.now(timezone.utc).strftime(DATETIME_FMT)
    existing_notes = task.get("notes") or ""
    combined_notes = f"{existing_notes}\n[Hoàn thành lúc {now_iso}]: {notes}".strip() if notes else existing_notes

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE cultivation_tasks
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                completed_by_user_id = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (user_id, combined_notes, task_id))
        conn.commit()

    log_task_activity(
        task_id=task_id,
        actor_user_id=user_id,
        action="completed",
        old_value=task.get("status"),
        new_value="completed",
        notes=notes or "Đã đánh dấu hoàn thành công việc."
    )

    # Handle recurrence: auto-create next task occurrence
    recurrence = task.get("recurrence_rule") or "none"
    if recurrence in ("daily", "weekly", "biweekly", "monthly"):
        try:
            curr_due = datetime.strptime(str(task.get("due_date"))[:10], DATE_FMT).date()
        except Exception:
            curr_due = datetime.now(timezone.utc).date()

        interval = task.get("recurrence_interval") or 1
        if recurrence == "daily":
            next_date = curr_due + timedelta(days=interval)
        elif recurrence == "weekly":
            next_date = curr_due + timedelta(weeks=interval)
        elif recurrence == "biweekly":
            next_date = curr_due + timedelta(weeks=2 * interval)
        elif recurrence == "monthly":
            next_date = curr_due + timedelta(days=30 * interval)
        else:
            next_date = curr_due + timedelta(days=7)

        next_due_str = next_date.strftime(DATE_FMT)

        next_task_payload = {
            "title": task["title"],
            "description": task.get("description"),
            "due_date": next_due_str,
            "priority": task.get("priority", "medium"),
            "status": "pending",
            "task_type": task.get("task_type", "routine"),
            "crop_id": task.get("crop_id"),
            "farm_id": task.get("farm_id"),
            "plot_id": task.get("plot_id"),
            "cycle_id": task.get("cycle_id") or task.get("crop_cycle_id"),
            "plant_id": task.get("plant_id"),
            "assignee_user_id": task.get("assignee_user_id"),
            "recurrence_rule": recurrence,
            "recurrence_interval": interval,
            "notes": f"Tự động tạo theo chu kỳ ({recurrence}) từ công việc #{task_id}."
        }

        next_task = create_task(
            next_task_payload,
            creator_user_id=user_id,
            org_id=task.get("organization_id")
        )

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE cultivation_tasks SET parent_task_id = ? WHERE id = ?", (task_id, next_task["id"]))
            conn.commit()

        log_task_activity(
            task_id=next_task["id"],
            actor_user_id=user_id,
            action="recurring_created",
            new_value="pending",
            notes=f"Được tự động sinh theo chu kỳ lặp ({recurrence}) từ công việc #{task_id}."
        )

    return get_task(task_id, user_id=user_id)


def delete_task(task_id: int, user_id: int) -> bool:
    """Delete a task after verifying authorization."""
    task = get_task(task_id, user_id=user_id)
    if not task:
        return False

    allowed, err = verify_task_permission(task, user_id, action="delete")
    if not allowed:
        raise PermissionError(err)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM task_activities WHERE task_id = ?", (task_id,))
        cursor.execute("DELETE FROM cultivation_tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Listing, Filtering & Calendar Views
# ---------------------------------------------------------------------------

def list_tasks(
    user_id: int,
    view: str = "all",  # 'all', 'today', 'upcoming', 'overdue', 'completed'
    farm_id: Optional[int] = None,
    plot_id: Optional[int] = None,
    cycle_id: Optional[int] = None,
    plant_id: Optional[int] = None,
    crop_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[int] = None,
    org_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 200
) -> Dict[str, Any]:
    """
    List tasks matching query filters and return category counts.
    Enforces tenant boundaries and personal vs organization scopes.
    """
    today_str = datetime.now(timezone.utc).strftime(DATE_FMT)

    with get_connection() as conn:
        cursor = conn.cursor()

        # Build scope condition
        base_where = []
        base_params: List[Any] = []

        if org_id is not None:
            # Check user membership
            mem = get_user_org_membership(user_id, org_id)
            if not mem:
                return {"total": 0, "tasks": [], "counts": {"total": 0, "today": 0, "upcoming": 0, "overdue": 0, "completed": 0}}
            base_where.append("t.organization_id = ?")
            base_params.append(org_id)
        else:
            # Personal tasks + org tasks user belongs to
            base_where.append("""(
                t.user_id = ?
                OR t.assignee_user_id = ?
                OR t.organization_id IN (
                    SELECT organization_id FROM organization_members WHERE user_id = ?
                )
                OR t.organization_id IN (
                    SELECT id FROM organizations WHERE owner_id = ?
                )
            )""")
            base_params.extend([user_id, user_id, user_id, user_id])

        # Filters
        query_where = list(base_where)
        query_params = list(base_params)

        if farm_id is not None:
            query_where.append("t.farm_id = ?")
            query_params.append(farm_id)
        if plot_id is not None:
            query_where.append("t.plot_id = ?")
            query_params.append(plot_id)
        if cycle_id is not None:
            query_where.append("(t.cycle_id = ? OR t.crop_cycle_id = ?)")
            query_params.extend([cycle_id, cycle_id])
        if plant_id is not None:
            query_where.append("t.plant_id = ?")
            query_params.append(plant_id)
        if crop_id is not None and crop_id != "all":
            query_where.append("LOWER(t.crop_id) = LOWER(?)")
            query_params.append(crop_id)
        if priority is not None:
            query_where.append("t.priority = ?")
            query_params.append(priority)
        if assignee_id is not None:
            query_where.append("t.assignee_user_id = ?")
            query_params.append(assignee_id)
        if date_from is not None:
            query_where.append("t.due_date >= ?")
            query_params.append(date_from[:10])
        if date_to is not None:
            query_where.append("t.due_date <= ?")
            query_params.append(date_to[:10])

        # View-based filtering
        if view == "today":
            query_where.append("t.due_date = ? AND t.status != 'completed'")
            query_params.append(today_str)
        elif view == "upcoming":
            query_where.append("t.due_date > ? AND t.status != 'completed'")
            query_params.append(today_str)
        elif view == "overdue":
            query_where.append("t.due_date < ? AND t.status != 'completed'")
            query_params.append(today_str)
        elif view == "completed":
            query_where.append("t.status = 'completed'")
        elif status is not None:
            query_where.append("t.status = ?")
            query_params.append(status)

        where_clause = " AND ".join(query_where)
        query = f"""
            SELECT t.*,
                   f.name as farm_name,
                   p.plot_name,
                   u_creator.full_name as creator_name,
                   u_assignee.full_name as assignee_name,
                   d.disease_name_vi as diagnosis_disease_vi,
                   d.predicted_disease as diagnosis_disease
            FROM cultivation_tasks t
            LEFT JOIN farms f ON t.farm_id = f.id
            LEFT JOIN farm_plots p ON t.plot_id = p.id
            LEFT JOIN users u_creator ON t.creator_user_id = u_creator.id
            LEFT JOIN users u_assignee ON t.assignee_user_id = u_assignee.id
            LEFT JOIN diagnoses d ON t.diagnosis_id = d.id
            WHERE {where_clause}
            ORDER BY
                CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END ASC,
                t.due_date ASC,
                CASE t.priority
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END ASC,
                t.id DESC
            LIMIT ?
        """
        query_params.append(limit)
        cursor.execute(query, query_params)
        tasks = [dict(r) for r in cursor.fetchall()]

        # Compute counts for views
        base_clause = " AND ".join(base_where)
        count_query = f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN t.due_date = '{today_str}' AND t.status != 'completed' THEN 1 ELSE 0 END) as today,
                SUM(CASE WHEN t.due_date > '{today_str}' AND t.status != 'completed' THEN 1 ELSE 0 END) as upcoming,
                SUM(CASE WHEN t.due_date < '{today_str}' AND t.status != 'completed' THEN 1 ELSE 0 END) as overdue,
                SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM cultivation_tasks t
            WHERE {base_clause}
        """
        cursor.execute(count_query, base_params)
        row = cursor.fetchone()
        counts = {
            "total": (row["total"] or 0) if row else 0,
            "today": (row["today"] or 0) if row else 0,
            "upcoming": (row["upcoming"] or 0) if row else 0,
            "overdue": (row["overdue"] or 0) if row else 0,
            "completed": (row["completed"] or 0) if row else 0
        }

        return {
            "success": True,
            "total": len(tasks),
            "counts": counts,
            "tasks": tasks
        }


# ---------------------------------------------------------------------------
# Task Reminders Engine
# ---------------------------------------------------------------------------

def process_task_reminders(
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
    lookahead_days: int = 1
) -> Dict[str, Any]:
    """
    Find tasks approaching due date that need reminders.
    Creates in-app notifications and updates reminder_status.
    Prevents duplicate notifications.
    """
    cutoff_date = (datetime.now(timezone.utc) + timedelta(days=lookahead_days)).strftime(DATE_FMT)

    reminders_sent = []
    reminders_failed = []

    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT t.*, u.id as recipient_id, u.email as recipient_email
            FROM cultivation_tasks t
            LEFT JOIN users u ON COALESCE(t.assignee_user_id, t.user_id) = u.id
            WHERE t.status != 'completed'
              AND (t.reminder_status = 'pending' OR t.reminder_status IS NULL)
              AND t.due_date <= ?
        """
        params: List[Any] = [cutoff_date]

        if org_id is not None:
            query += " AND t.organization_id = ?"
            params.append(org_id)
        elif user_id is not None:
            query += " AND (t.user_id = ? OR t.assignee_user_id = ?)"
            params.extend([user_id, user_id])

        cursor.execute(query, params)
        eligible_tasks = [dict(r) for r in cursor.fetchall()]

        for t in eligible_tasks:
            recipient_id = t.get("recipient_id") or t.get("assignee_user_id") or t.get("user_id")
            if not recipient_id:
                # Cannot deliver reminder without recipient
                cursor.execute("""
                    UPDATE cultivation_tasks
                    SET reminder_status = 'failed', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (t["id"],))
                reminders_failed.append({"task_id": t["id"], "reason": "Thiếu thông tin người nhận."})
                continue

            # Create in-app notification in notifications table
            title = f"Nhắc việc: {t['title']}"
            priority_label = "Khẩn cấp" if t.get("priority") == "urgent" else ("Cao" if t.get("priority") == "high" else "Bình thường")
            message = f"Công việc canh tác '{t['title']}' đến hạn vào {t['due_date']} (Ưu tiên: {priority_label}). Vui lòng kiểm tra và xử lý!"
            notif_type = "warning" if t.get("priority") in ("high", "urgent") else "info"

            try:
                cursor.execute("""
                    INSERT INTO notifications (
                        user_id, title, message, notification_type, is_read, target_url, created_at
                    ) VALUES (?, ?, ?, ?, 0, '/calendar', CURRENT_TIMESTAMP)
                """, (recipient_id, title, message, notif_type))

                # Update task reminder status
                cursor.execute("""
                    UPDATE cultivation_tasks
                    SET reminder_status = 'sent',
                        reminder_sent_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (t["id"],))

                log_task_activity(
                    task_id=t["id"],
                    actor_user_id=None,
                    action="reminder_sent",
                    new_value="sent",
                    notes=f"Đã phát thông báo nhắc việc tới User #{recipient_id}.",
                    conn=conn
                )

                reminders_sent.append({
                    "task_id": t["id"],
                    "recipient_user_id": recipient_id,
                    "title": t["title"],
                    "due_date": t["due_date"]
                })
            except Exception as e:
                logger.error(f"Failed to create notification for task {t['id']}: {e}")
                cursor.execute("""
                    UPDATE cultivation_tasks
                    SET reminder_status = 'failed', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (t["id"],))
                reminders_failed.append({"task_id": t["id"], "reason": str(e)})

        conn.commit()

    return {
        "success": True,
        "processed_count": len(eligible_tasks),
        "sent_count": len(reminders_sent),
        "failed_count": len(reminders_failed),
        "reminders_sent": reminders_sent,
        "reminders_failed": reminders_failed
    }
