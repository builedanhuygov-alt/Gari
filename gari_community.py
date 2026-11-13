"""
GARI Module 08 — Community & Agricultural Knowledge Library Service Layer
Authoritative implementation for:
1. Community posts, discussions, and crop diagnosis case sharing.
2. Verified expert badges and accurate author accreditation.
3. Comments, threaded replies, and expert answers.
4. Likes and reaction toggle mechanics.
5. Inappropriate and misleading advice reporting queue.
6. Moderator review workflows, content masking, and immutable audit logging.
7. Peer-reviewed and official agricultural knowledge repository with crop, topic, and regional filtering.
8. Strict protection against fabricated sources or unverified guidance masquerading as official science.
"""

import sqlite3
import json
import logging
import re
from datetime import datetime, timezone
import uuid
from typing import Dict, Any, List, Optional, Tuple, Union

from gari_database import get_connection
import gari_auth
from gari_auth import record_host_audit
import gari_moderation

logger = logging.getLogger("gari.community")

VALID_POST_TYPES = {"question", "discussion", "case_share", "guide"}
VALID_REPORT_REASONS = {
    "misleading_advice": "Lời khuyên kỹ thuật sai lệch / nguy hại",
    "inappropriate_content": "Nội dung phản cảm, vi phạm văn hóa",
    "spam_advertising": "Quảng cáo rác, bán hàng không kiểm định",
    "harassment": "Xúc phạm, quấy rối thành viên khác",
    "non_agricultural": "Nội dung hoàn toàn không liên quan đến nông nghiệp",
    "fake_expert": "Giả mạo cán bộ khuyến nông hoặc chuyên gia BVTV"
}
VALID_MODERATION_ACTIONS = {"dismiss", "hide_content", "remove_content", "warn_user", "restrict_user"}
VALID_REVIEW_STATUSES = {"official_verified", "expert_reviewed", "community_unverified"}


# ---------------------------------------------------------------------------
# Helper: Audit Logging for Community Moderation
# ---------------------------------------------------------------------------

def log_community_moderation_audit(
    moderator_user_id: int,
    moderator_email: str,
    target_type: str,
    target_id: int,
    action: str,
    reason: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: str = "0.0.0.0",
    conn: Optional[sqlite3.Connection] = None
) -> None:
    """Log an immutable audit entry for a moderation action in community."""
    details_str = json.dumps(details, ensure_ascii=False) if details else None
    try:
        if conn is not None:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO community_moderation_audit_logs (
                    moderator_user_id, moderator_email, target_type, target_id,
                    action, reason, details_json, ip_address, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (moderator_user_id, moderator_email, target_type, target_id, action, reason, details_str, ip_address))
        else:
            with get_connection() as c:
                cursor = c.cursor()
                cursor.execute("""
                    INSERT INTO community_moderation_audit_logs (
                        moderator_user_id, moderator_email, target_type, target_id,
                        action, reason, details_json, ip_address, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (moderator_user_id, moderator_email, target_type, target_id, action, reason, details_str, ip_address))
                c.commit()
    except Exception as e:
        logger.error(f"Error logging community moderation audit: {e}")


# ---------------------------------------------------------------------------
# 1. Community Posts & Questions
# ---------------------------------------------------------------------------

def create_post(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new community discussion post or agricultural question.
    Accurately tags author credentials and verified expert status.
    """
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()

    if len(title) < 5:
        raise ValueError("Tiêu đề bài viết phải có tối thiểu 5 ký tự.")
    if len(content) < 10:
        raise ValueError("Nội dung bài viết phải có tối thiểu 10 ký tự.")

    post_type = (data.get("post_type") or "question").lower().strip()
    if post_type not in VALID_POST_TYPES:
        post_type = "question"

    crop_id = (data.get("crop_id") or "").strip().lower() or None
    region = (data.get("region") or "Toàn quốc").strip()
    diagnosis_id = data.get("diagnosis_id")

    image_urls = data.get("image_urls") or data.get("images") or []
    image_urls_json = json.dumps(image_urls if isinstance(image_urls, list) else [image_urls], ensure_ascii=False)

    tags = data.get("tags") or []
    tags_json = json.dumps(tags if isinstance(tags, list) else [tags], ensure_ascii=False)

    # Check user account details
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, full_name, email, is_expert, is_host_admin, account_type FROM users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
        if not u:
            raise ValueError("Không tìm thấy thông tin người dùng.")
        user_info = dict(u)

        # Check moderation restrictions
        cursor.execute("SELECT * FROM moderation_cases WHERE user_id = ? AND status = 'restricted' LIMIT 1", (user_id,))
        if cursor.fetchone():
            raise PermissionError("Tài khoản của bạn đang bị giới hạn quyền đăng bài do vi phạm tiêu chuẩn cộng đồng.")

        # Determine official/review status
        # ONLY Host Admin or Verified Experts can author official agricultural guides!
        is_official = 0
        review_status = "community_unverified"

        if user_info.get("is_host_admin"):
            if data.get("is_official_guidance"):
                is_official = 1
                review_status = "official_verified"
        elif user_info.get("is_expert"):
            review_status = "expert_reviewed"

        # Automated moderation pre-scan for spam/harassment
        combined_text = f"{title} {content}"
        violation = gari_moderation.scan_content_text(combined_text)
        initial_status = "active"
        if violation and violation.get("severity") in ("high", "critical"):
            initial_status = "flagged"

        cursor.execute("""
            INSERT INTO community_posts (
                user_id, post_type, title, content, crop_id, region,
                diagnosis_id, image_urls_json, tags_json, status,
                is_official_guidance, review_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            user_id, post_type, title, content, crop_id, region,
            diagnosis_id, image_urls_json, tags_json, initial_status,
            is_official, review_status
        ))
        conn.commit()
        post_id = cursor.lastrowid

        # If flagged during auto-scan, record an automated report
        if initial_status == "flagged":
            cursor.execute("""
                INSERT INTO community_reports (
                    reporter_user_id, target_type, target_id, reason_category, details, status
                ) VALUES (?, 'post', ?, ?, ?, 'pending')
            """, (user_id, post_id, violation.get("category", "spam_advertising"), f"[Hệ thống tự động phát hiện]: {violation.get('reason')}"))
            conn.commit()

    return get_post(post_id, viewer_user_id=user_id)


def get_post(post_id: int, viewer_user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Retrieve full post details including author metadata, expert credentials, and like status.
    Atomically increments views count.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Increment view count
        cursor.execute("UPDATE community_posts SET views_count = views_count + 1 WHERE id = ?", (post_id,))
        conn.commit()

        cursor.execute("""
            SELECT p.*,
                   u.full_name as author_name,
                   u.email as author_email,
                   u.account_type as author_account_type,
                   u.is_expert as author_is_expert,
                   ep.display_title as expert_title,
                   ep.institution as expert_institution,
                   ep.rating as expert_rating
            FROM community_posts p
            JOIN users u ON p.user_id = u.id
            LEFT JOIN expert_profiles ep ON u.id = ep.user_id
            WHERE p.id = ?
        """, (post_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy bài viết #{post_id}.")
        post = dict(row)

        # Enforce visibility: hidden or removed posts can only be seen by author or Host Admin
        if post["status"] in ("hidden", "removed"):
            if not viewer_user_id:
                raise PermissionError("Bài viết này đã bị ẩn bởi ban điều hành.")
            cursor.execute("SELECT is_host_admin FROM users WHERE id = ?", (viewer_user_id,))
            viewer = cursor.fetchone()
            is_host = bool(viewer and viewer[0])
            if viewer_user_id != post["user_id"] and not is_host:
                raise PermissionError("Bài viết này đã bị tạm ẩn hoặc gỡ bỏ do vi phạm quy chuẩn cộng đồng.")

        # Check liked by viewer
        is_liked = False
        if viewer_user_id:
            cursor.execute("SELECT id FROM community_likes WHERE user_id = ? AND target_type = 'post' AND target_id = ?", (viewer_user_id, post_id))
            is_liked = bool(cursor.fetchone())
        post["is_liked_by_me"] = is_liked

        # Parse JSON fields
        try:
            post["image_urls"] = json.loads(post.get("image_urls_json") or "[]")
        except Exception:
            post["image_urls"] = []

        try:
            post["tags"] = json.loads(post.get("tags_json") or "[]")
        except Exception:
            post["tags"] = []

        post["author_expert_title"] = post.get("expert_title")
        post["author_institution"] = post.get("expert_institution")

        return post


def list_posts(
    crop_id: Optional[str] = None,
    region: Optional[str] = None,
    post_type: Optional[str] = None,
    review_status: Optional[str] = None,
    search_query: Optional[str] = None,
    status: str = "active",
    limit: int = 50,
    offset: int = 0,
    viewer_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Search and list community posts with crop, region, and verification filters.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        query_parts = ["1=1"]
        params: List[Any] = []

        if status:
            query_parts.append("p.status = ?")
            params.append(status)

        if crop_id:
            query_parts.append("(p.crop_id = ? OR p.crop_id IS NULL)")
            params.append(crop_id.lower().strip())

        if region and region != "Toàn quốc":
            query_parts.append("(p.region = ? OR p.region = 'Toàn quốc')")
            params.append(region.strip())

        if post_type:
            query_parts.append("p.post_type = ?")
            params.append(post_type.lower().strip())

        if review_status:
            query_parts.append("p.review_status = ?")
            params.append(review_status.strip())

        if search_query:
            q_like = f"%{search_query.strip()}%"
            query_parts.append("(p.title LIKE ? OR p.content LIKE ? OR p.tags_json LIKE ?)")
            params.extend([q_like, q_like, q_like])

        where_clause = " AND ".join(query_parts)

        # Count total
        count_sql = f"SELECT count(*) FROM community_posts p WHERE {where_clause}"
        cursor.execute(count_sql, tuple(params))
        total = cursor.fetchone()[0]

        # Select rows
        sql = f"""
            SELECT p.*,
                   u.full_name as author_name,
                   u.email as author_email,
                   u.is_expert as author_is_expert,
                   ep.display_title as expert_title,
                   ep.institution as expert_institution
            FROM community_posts p
            JOIN users u ON p.user_id = u.id
            LEFT JOIN expert_profiles ep ON u.id = ep.user_id
            WHERE {where_clause}
            ORDER BY p.is_pinned DESC, p.created_at DESC, p.id DESC
            LIMIT ? OFFSET ?
        """
        fetch_params = list(params) + [limit, offset]
        cursor.execute(sql, tuple(fetch_params))
        rows = [dict(r) for r in cursor.fetchall()]

        # Attach like status and parsed fields
        for p in rows:
            try:
                p["image_urls"] = json.loads(p.get("image_urls_json") or "[]")
            except Exception:
                p["image_urls"] = []
            try:
                p["tags"] = json.loads(p.get("tags_json") or "[]")
            except Exception:
                p["tags"] = []

            p["author_expert_title"] = p.get("expert_title")
            p["author_institution"] = p.get("expert_institution")

            p["is_liked_by_me"] = False
            if viewer_user_id:
                cursor.execute(
                    "SELECT 1 FROM community_likes WHERE user_id = ? AND target_type = 'post' AND target_id = ?",
                    (viewer_user_id, p["id"])
                )
                p["is_liked_by_me"] = bool(cursor.fetchone())

        return {"posts": rows, "total": total, "limit": limit, "offset": offset}


def delete_post(
    post_id: int,
    user_id: int,
    is_moderator: bool = False,
    reason: Optional[str] = None,
    moderator_email: Optional[str] = None,
    ip_address: str = "0.0.0.0"
) -> bool:
    """Soft-delete a post. Allowed by author or authorized moderators."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, title FROM community_posts WHERE id = ?", (post_id,))
        p = cursor.fetchone()
        if not p:
            raise ValueError(f"Không tìm thấy bài viết #{post_id}.")

        if p["user_id"] != user_id and not is_moderator:
            raise PermissionError("Bạn không có quyền xóa bài viết này.")

        cursor.execute("UPDATE community_posts SET status = 'removed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (post_id,))
        conn.commit()

        if is_moderator and moderator_email:
            log_community_moderation_audit(
                moderator_user_id=user_id,
                moderator_email=moderator_email,
                target_type="post",
                target_id=post_id,
                action="remove_post",
                reason=reason or "Quản trị viên gỡ bỏ bài viết",
                details={"post_title": p["title"]},
                ip_address=ip_address,
                conn=conn
            )
            record_host_audit(
                host_admin_id=user_id,
                host_email=moderator_email,
                action_type="COMMUNITY_REMOVE_POST",
                target_resource=f"community_post:{post_id}",
                details={"post_id": post_id, "title": p["title"]},
                reason=reason or "Moderator removed post",
                ip_address=ip_address
            )

        return True


# ---------------------------------------------------------------------------
# 2. Reactions / Likes
# ---------------------------------------------------------------------------

def toggle_post_like(user_id: int, post_id: int, reaction_type: str = "like") -> Dict[str, Any]:
    """Toggle like/reaction on a post."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM community_posts WHERE id = ?", (post_id,))
        if not cursor.fetchone():
            raise ValueError(f"Không tìm thấy bài viết #{post_id}.")

        cursor.execute(
            "SELECT id FROM community_likes WHERE user_id = ? AND target_type = 'post' AND target_id = ?",
            (user_id, post_id)
        )
        existing = cursor.fetchone()

        if existing:
            # Unlike
            cursor.execute("DELETE FROM community_likes WHERE id = ?", (existing[0],))
            cursor.execute("UPDATE community_posts SET likes_count = MAX(0, likes_count - 1) WHERE id = ?", (post_id,))
            conn.commit()
            liked = False
        else:
            # Like
            cursor.execute(
                "INSERT INTO community_likes (user_id, target_type, target_id, reaction_type) VALUES (?, 'post', ?, ?)",
                (user_id, post_id, reaction_type)
            )
            cursor.execute("UPDATE community_posts SET likes_count = likes_count + 1 WHERE id = ?", (post_id,))
            conn.commit()
            liked = True

        cursor.execute("SELECT likes_count FROM community_posts WHERE id = ?", (post_id,))
        likes_count = cursor.fetchone()[0]

    return {"success": True, "post_id": post_id, "liked": liked, "likes_count": likes_count}


def toggle_comment_like(user_id: int, comment_id: int, reaction_type: str = "like") -> Dict[str, Any]:
    """Toggle like/reaction on a comment."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, post_id FROM community_comments WHERE id = ?", (comment_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy bình luận #{comment_id}.")

        cursor.execute(
            "SELECT id FROM community_likes WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
            (user_id, comment_id)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute("DELETE FROM community_likes WHERE id = ?", (existing[0],))
            cursor.execute("UPDATE community_comments SET likes_count = MAX(0, likes_count - 1) WHERE id = ?", (comment_id,))
            conn.commit()
            liked = False
        else:
            cursor.execute(
                "INSERT INTO community_likes (user_id, target_type, target_id, reaction_type) VALUES (?, 'comment', ?, ?)",
                (user_id, comment_id, reaction_type)
            )
            cursor.execute("UPDATE community_comments SET likes_count = likes_count + 1 WHERE id = ?", (comment_id,))
            conn.commit()
            liked = True

        cursor.execute("SELECT likes_count FROM community_comments WHERE id = ?", (comment_id,))
        likes_count = cursor.fetchone()[0]

    return {"success": True, "comment_id": comment_id, "liked": liked, "likes_count": likes_count}


# ---------------------------------------------------------------------------
# 3. Comments & Threaded Replies
# ---------------------------------------------------------------------------

def create_comment(user_id: int, post_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a comment or reply to a post.
    Marks is_expert_answer when authored by verified agronomists.
    """
    content = (data.get("content") or "").strip()
    if not content:
        raise ValueError("Nội dung phản hồi không được để trống.")

    parent_id = data.get("parent_comment_id")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Check post
        cursor.execute("SELECT id, user_id, title, status FROM community_posts WHERE id = ?", (post_id,))
        p = cursor.fetchone()
        if not p:
            raise ValueError(f"Không tìm thấy bài viết #{post_id}.")
        if p["status"] in ("hidden", "removed"):
            raise ValueError("Bài viết đã bị đóng hoặc ẩn, không thể gửi bình luận.")

        # Check user credentials
        cursor.execute("SELECT id, full_name, email, is_expert FROM users WHERE id = ?", (user_id,))
        u = cursor.fetchone()
        if not u:
            raise ValueError("Không tìm thấy người dùng.")
        is_expert = bool(u["is_expert"])

        # Check parent comment if reply
        if parent_id:
            cursor.execute("SELECT id FROM community_comments WHERE id = ? AND post_id = ?", (parent_id, post_id))
            if not cursor.fetchone():
                raise ValueError("Không tìm thấy bình luận gốc để phản hồi.")

        image_urls = data.get("image_urls") or []
        image_urls_json = json.dumps(image_urls if isinstance(image_urls, list) else [image_urls], ensure_ascii=False)

        cursor.execute("""
            INSERT INTO community_comments (
                post_id, user_id, parent_comment_id, content,
                image_urls_json, is_expert_answer, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (post_id, user_id, parent_id, content, image_urls_json, 1 if is_expert else 0))

        # Update comments_count on post
        cursor.execute("UPDATE community_posts SET comments_count = comments_count + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (post_id,))

        comment_id = cursor.lastrowid

        # Notify post owner if commenter is not post author
        if p["user_id"] != user_id:
            expert_tag = " (Chuyên gia BVTV)" if is_expert else ""
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Có phản hồi mới trên bài viết của bạn', ?, 'info', ?)
            """, (
                p["user_id"],
                f"{u['full_name']}{expert_tag} đã trả lời bài viết \"{p['title'][:40]}...\": \"{content[:60]}...\"",
                f"/frontend2/community.html?post={post_id}"
            ))

        conn.commit()

        # Fetch inserted comment with author info
        cursor.execute("""
            SELECT c.*,
                   u.full_name as author_name,
                   u.email as author_email,
                   u.is_expert as author_is_expert,
                   ep.display_title as expert_title,
                   ep.institution as expert_institution
            FROM community_comments c
            JOIN users u ON c.user_id = u.id
            LEFT JOIN expert_profiles ep ON u.id = ep.user_id
            WHERE c.id = ?
        """, (comment_id,))
        comment = dict(cursor.fetchone())
        try:
            comment["image_urls"] = json.loads(comment.get("image_urls_json") or "[]")
        except Exception:
            comment["image_urls"] = []

        return comment


def list_comments(post_id: int, viewer_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve full chronological conversation list for a post."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*,
                   u.full_name as author_name,
                   u.email as author_email,
                   u.is_expert as author_is_expert,
                   ep.display_title as expert_title,
                   ep.institution as expert_institution
            FROM community_comments c
            JOIN users u ON c.user_id = u.id
            LEFT JOIN expert_profiles ep ON u.id = ep.user_id
            WHERE c.post_id = ? AND c.status = 'active'
            ORDER BY c.created_at ASC, c.id ASC
        """, (post_id,))
        rows = [dict(r) for r in cursor.fetchall()]

        for c in rows:
            try:
                c["image_urls"] = json.loads(c.get("image_urls_json") or "[]")
            except Exception:
                c["image_urls"] = []

            c["is_liked_by_me"] = False
            if viewer_user_id:
                cursor.execute(
                    "SELECT 1 FROM community_likes WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
                    (viewer_user_id, c["id"])
                )
                c["is_liked_by_me"] = bool(cursor.fetchone())

        return rows


def delete_comment(
    comment_id: int,
    user_id: int,
    is_moderator: bool = False,
    reason: Optional[str] = None,
    moderator_email: Optional[str] = None,
    ip_address: str = "0.0.0.0"
) -> bool:
    """Soft-delete a comment."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, post_id, user_id FROM community_comments WHERE id = ?", (comment_id,))
        c = cursor.fetchone()
        if not c:
            raise ValueError(f"Không tìm thấy bình luận #{comment_id}.")

        if c["user_id"] != user_id and not is_moderator:
            raise PermissionError("Bạn không có quyền xóa bình luận này.")

        cursor.execute("UPDATE community_comments SET status = 'removed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (comment_id,))
        cursor.execute("UPDATE community_posts SET comments_count = MAX(0, comments_count - 1) WHERE id = ?", (c["post_id"],))
        conn.commit()

        if is_moderator and moderator_email:
            log_community_moderation_audit(
                moderator_user_id=user_id,
                moderator_email=moderator_email,
                target_type="comment",
                target_id=comment_id,
                action="remove_comment",
                reason=reason or "Quản trị viên xóa bình luận",
                ip_address=ip_address,
                conn=conn
            )

        return True


# ---------------------------------------------------------------------------
# 4. Inappropriate / Misleading Content Reporting & Trust Moderation
# ---------------------------------------------------------------------------

def report_content(
    reporter_user_id: int,
    target_type: str,
    target_id: int,
    reason_category: str,
    details: Optional[str] = None
) -> Dict[str, Any]:
    """
    Users report suspicious, misleading, or abusive posts or comments.
    If report count exceeds threshold, content is auto-flagged for immediate Host review.
    """
    target_type = target_type.lower().strip()
    if target_type not in ("post", "comment", "knowledge_article"):
        raise ValueError("Loại nội dung báo cáo không hợp lệ (post, comment hoặc knowledge_article).")

    if reason_category not in VALID_REPORT_REASONS:
        raise ValueError(f"Lý do báo cáo không hợp lệ. Chọn từ: {', '.join(VALID_REPORT_REASONS.keys())}")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Check target existence
        table_name = "community_posts" if target_type == "post" else ("community_comments" if target_type == "comment" else "knowledge_articles")
        cursor.execute(f"SELECT id, reports_count FROM {table_name} WHERE id = ?", (target_id,))
        target_row = cursor.fetchone()
        if not target_row:
            raise ValueError(f"Không tìm thấy mục tiêu báo cáo #{target_id}.")

        # Prevent duplicate reporting from same user
        cursor.execute(
            "SELECT id FROM community_reports WHERE reporter_user_id = ? AND target_type = ? AND target_id = ? AND status = 'pending'",
            (reporter_user_id, target_type, target_id)
        )
        if cursor.fetchone():
            raise ValueError("Bạn đã gửi báo cáo cho nội dung này rồi. Ban quản trị đang xử lý.")

        cursor.execute("""
            INSERT INTO community_reports (
                reporter_user_id, target_type, target_id, reason_category, details, status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
        """, (reporter_user_id, target_type, target_id, reason_category, (details or "").strip()))
        report_id = cursor.lastrowid

        # Increment report count on target
        new_reports_count = (target_row["reports_count"] or 0) + 1
        cursor.execute(f"UPDATE {table_name} SET reports_count = ? WHERE id = ?", (new_reports_count, target_id))

        # Auto-flag if >= 2 reports
        if new_reports_count >= 2 and target_type in ("post", "comment"):
            cursor.execute(f"UPDATE {table_name} SET status = 'flagged' WHERE id = ? AND status = 'active'", (target_id,))

        conn.commit()

        cursor.execute("SELECT * FROM community_reports WHERE id = ?", (report_id,))
        return dict(cursor.fetchone())


def list_moderation_reports(
    status: Optional[str] = "pending",
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Retrieve queue of user reports for Host Console moderation."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT r.*,
                   u.full_name as reporter_name,
                   u.email as reporter_email
            FROM community_reports r
            JOIN users u ON r.reporter_user_id = u.id
        """
        params: List[Any] = []
        if status:
            query += " WHERE r.status = ?"
            params.append(status)

        query += " ORDER BY r.created_at DESC, r.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        rows = [dict(r) for r in cursor.fetchall()]

        # Attach content snippets
        for rep in rows:
            t_type = rep["target_type"]
            t_id = rep["target_id"]
            if t_type == "post":
                cursor.execute("SELECT title, content, user_id, status FROM community_posts WHERE id = ?", (t_id,))
                post = cursor.fetchone()
                if post:
                    rep["content_snippet"] = f"[{post['title']}] {post['content'][:120]}"
                    rep["author_user_id"] = post["user_id"]
                    rep["content_status"] = post["status"]
            elif t_type == "comment":
                cursor.execute("SELECT content, user_id, status FROM community_comments WHERE id = ?", (t_id,))
                comment = cursor.fetchone()
                if comment:
                    rep["content_snippet"] = comment["content"][:120]
                    rep["author_user_id"] = comment["user_id"]
                    rep["content_status"] = comment["status"]

        return rows


def review_moderation_report(
    report_id: int,
    moderator_user_id: int,
    moderator_email: str,
    action: str,
    review_notes: str,
    ip_address: str = "0.0.0.0"
) -> Dict[str, Any]:
    """
    Host Admin or authorized moderator reviews a community violation report.
    Enforces actions: dismiss, hide_content, remove_content, warn_user, restrict_user.
    Logs immutable audit trails to prevent arbitrary censorship and maintain accountability.
    """
    action = action.lower().strip()
    if action not in VALID_MODERATION_ACTIONS:
        raise ValueError(f"Hành động xử lý vi phạm không hợp lệ. Chọn từ: {', '.join(VALID_MODERATION_ACTIONS)}")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM community_reports WHERE id = ?", (report_id,))
        rep_row = cursor.fetchone()
        if not rep_row:
            raise ValueError(f"Không tìm thấy báo cáo vi phạm #{report_id}.")
        rep = dict(rep_row)

        target_type = rep["target_type"]
        target_id = rep["target_id"]
        table_name = "community_posts" if target_type == "post" else ("community_comments" if target_type == "comment" else "knowledge_articles")

        # Determine target author
        cursor.execute(f"SELECT user_id FROM {table_name} WHERE id = ?", (target_id,))
        author_row = cursor.fetchone()
        target_author_id = author_row[0] if author_row else None

        new_report_status = "action_taken" if action != "dismiss" else "dismissed"

        # Apply target mutation
        if action == "hide_content":
            cursor.execute(f"UPDATE {table_name} SET status = 'hidden', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (target_id,))
        elif action == "remove_content":
            cursor.execute(f"UPDATE {table_name} SET status = 'removed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (target_id,))
        elif action == "dismiss":
            # Revert from flagged to active if it was flagged
            cursor.execute(f"UPDATE {table_name} SET status = 'active' WHERE id = ? AND status = 'flagged'", (target_id,))

        # Apply user action if requested
        if action in ("warn_user", "restrict_user") and target_author_id:
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, notification_type, target_url)
                VALUES (?, 'Cảnh báo vi phạm tiêu chuẩn cộng đồng GARI', ?, 'danger', '/frontend2/support.html')
            """, (
                target_author_id,
                f"Nội dung của bạn đã bị báo cáo vì lý do: {VALID_REPORT_REASONS.get(rep['reason_category'], rep['reason_category'])}. "
                f"Ghi chú BQT: {review_notes or 'Vui lòng tuân thủ quy chuẩn kỹ thuật nông học.'}"
            ))

        # Update report
        cursor.execute("""
            UPDATE community_reports
            SET status = ?,
                reviewed_by_host_id = ?,
                review_notes = ?,
                action_taken = ?,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_report_status, moderator_user_id, review_notes.strip(), action, report_id))

        conn.commit()

        # Audit log in community moderation table
        log_community_moderation_audit(
            moderator_user_id=moderator_user_id,
            moderator_email=moderator_email,
            target_type=target_type,
            target_id=target_id,
            action=action,
            reason=review_notes,
            details={"report_id": report_id, "category": rep["reason_category"], "target_author_id": target_author_id},
            ip_address=ip_address,
            conn=conn
        )

        cursor.execute("SELECT * FROM community_reports WHERE id = ?", (report_id,))
        result = dict(cursor.fetchone())

    # Audit log in global host audit logs (outside of conn context to eliminate SQLite WAL lock contention)
    try:
        record_host_audit(
            host_admin_id=moderator_user_id,
            host_email=moderator_email,
            action_type="COMMUNITY_MODERATION",
            target_resource=f"community_report:{report_id}",
            details={"report_id": report_id, "action": action, "notes": review_notes, "target": f"{target_type}:{target_id}"},
            reason=f"Xử lý báo cáo vi phạm #{report_id}: {action}",
            ip_address=ip_address
        )
    except Exception as exc:
        logger.warning(f"Failed to record host audit log for moderation: {exc}")

    return result


# ---------------------------------------------------------------------------
# 5. Peer-Reviewed Knowledge Library
# ---------------------------------------------------------------------------

def search_knowledge_articles(
    query: Optional[str] = None,
    crop_id: Optional[str] = None,
    topic: Optional[str] = None,
    region: Optional[str] = None,
    review_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Search authenticated agricultural knowledge library articles.
    Clearly indicates accredited research sources and review status.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        query_parts = ["status = 'published'"]
        params: List[Any] = []

        if crop_id:
            query_parts.append("crop_id = ?")
            params.append(crop_id.lower().strip())

        if topic:
            query_parts.append("topic = ?")
            params.append(topic.strip())

        if region and region != "Toàn quốc":
            query_parts.append("(region = ? OR region = 'Toàn quốc')")
            params.append(region.strip())

        if review_status:
            query_parts.append("review_status = ?")
            params.append(review_status.strip())

        if query:
            q_like = f"%{query.strip()}%"
            query_parts.append("(title LIKE ? OR summary LIKE ? OR content_markdown LIKE ? OR crop_id LIKE ?)")
            params.extend([q_like, q_like, q_like, q_like])

        where_clause = " AND ".join(query_parts)

        # Count
        count_sql = f"SELECT count(*) FROM knowledge_articles WHERE {where_clause}"
        cursor.execute(count_sql, tuple(params))
        total = cursor.fetchone()[0]

        sql = f"""
            SELECT * FROM knowledge_articles
            WHERE {where_clause}
            ORDER BY publication_date DESC, id DESC
            LIMIT ? OFFSET ?
        """
        fetch_params = list(params) + [limit, offset]
        cursor.execute(sql, tuple(fetch_params))
        rows = [dict(r) for r in cursor.fetchall()]

        return {"articles": rows, "total": total, "limit": limit, "offset": offset}


def get_knowledge_article(article_id_or_slug: Union[int, str]) -> Dict[str, Any]:
    """Retrieve full article by numeric ID or URL slug."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if isinstance(article_id_or_slug, int) or (isinstance(article_id_or_slug, str) and article_id_or_slug.isdigit()):
            cursor.execute("SELECT * FROM knowledge_articles WHERE id = ?", (int(article_id_or_slug),))
        else:
            cursor.execute("SELECT * FROM knowledge_articles WHERE slug = ?", (str(article_id_or_slug),))

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy cẩm nang nông học '{article_id_or_slug}'.")

        # Increment view count
        art = dict(row)
        cursor.execute("UPDATE knowledge_articles SET view_count = view_count + 1 WHERE id = ?", (art["id"],))
        conn.commit()
        art["view_count"] += 1

        return art


def create_or_update_knowledge_article(
    moderator_user: Dict[str, Any],
    data: Dict[str, Any],
    article_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Publish or edit an official agricultural guide.
    Restricted strictly to Host Admins or Verified Agronomist Experts to prevent misinformation.
    """
    is_host = bool(moderator_user.get("is_host_admin"))
    is_expert = bool(moderator_user.get("is_expert"))
    if not (is_host or is_expert):
        raise PermissionError("Chỉ Quản trị viên hệ thống hoặc Chuyên gia Nông học được kiểm duyệt mới có quyền xuất bản cẩm nang tri thức chính thống.")

    title = (data.get("title") or "").strip()
    summary = (data.get("summary") or "").strip()
    content = (data.get("content_markdown") or data.get("content") or "").strip()
    crop_id = (data.get("crop_id") or "general").strip().lower()
    topic = (data.get("topic") or "pest_disease").strip()
    region = (data.get("region") or "Toàn quốc").strip()

    if not title or not summary or not content:
        raise ValueError("Vui lòng cung cấp đầy đủ Tiêu đề, Tóm tắt và Nội dung bài viết.")

    source_inst = (data.get("source_institution") or "Viện Khoa Học Nông Nghiệp Việt Nam").strip()
    source_url = data.get("source_url")
    author_name = (data.get("author_name") or moderator_user.get("full_name") or "Ban Khoa Học GARI").strip()
    author_title = data.get("author_title") or ("Chuyên gia BVTV" if is_expert else "Quản trị viên Khoa học")

    review_status = data.get("review_status") or ("official_verified" if is_host else "expert_reviewed")
    if review_status not in VALID_REVIEW_STATUSES:
        review_status = "official_verified"

    badge = data.get("verification_badge") or (f"Chính thống - {source_inst}" if is_host else "Thẩm định bởi Chuyên gia")
    pub_date = data.get("publication_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Generate slug if creating
    slug = (data.get("slug") or "").strip().lower()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if not slug:
            slug = f"article-{int(datetime.now(timezone.utc).timestamp())}"

    with get_connection() as conn:
        cursor = conn.cursor()

        if article_id:
            cursor.execute("""
                UPDATE knowledge_articles SET
                    title = ?, crop_id = ?, topic = ?, region = ?, summary = ?,
                    content_markdown = ?, source_institution = ?, source_url = ?,
                    author_name = ?, author_title = ?, review_status = ?,
                    verification_badge = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                title, crop_id, topic, region, summary, content,
                source_inst, source_url, author_name, author_title,
                review_status, badge, article_id
            ))
            target_id = article_id
        else:
            base_slug = slug
            cursor.execute("SELECT id FROM knowledge_articles WHERE slug = ?", (slug,))
            while cursor.fetchone():
                slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
                cursor.execute("SELECT id FROM knowledge_articles WHERE slug = ?", (slug,))

            cursor.execute("""
                INSERT INTO knowledge_articles (
                    title, slug, crop_id, topic, region, summary, content_markdown,
                    source_institution, source_url, author_name, author_title,
                    author_user_id, review_status, is_official, verification_badge,
                    publication_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                title, slug, crop_id, topic, region, summary, content,
                source_inst, source_url, author_name, author_title,
                moderator_user["id"], review_status, badge, pub_date
            ))
            target_id = cursor.lastrowid

        conn.commit()

        # Audit
        log_community_moderation_audit(
            moderator_user_id=moderator_user["id"],
            moderator_email=moderator_user.get("email", ""),
            target_type="knowledge_article",
            target_id=target_id,
            action="update_article" if article_id else "publish_article",
            reason=f"Xuất bản tri thức nông học: {title}",
            details={"crop_id": crop_id, "topic": topic, "source": source_inst},
            conn=conn
        )

    return get_knowledge_article(target_id)
