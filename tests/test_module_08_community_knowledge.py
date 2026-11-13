"""
GARI Module 08 — Community & Agricultural Knowledge Test Suite
Verifies:
1. Farmer creates question post with crop, region, and content.
2. Post retrieval accurately reflects author credentials & verified expert badge.
3. Commenting & nested replies with is_expert_answer = 1 for agronomists.
4. Idempotent toggle of likes/reactions for posts and comments.
5. Distinguishing official/reviewed guidance from community chatter (review_status enforcement).
6. User reporting of misleading advice (community_reports).
7. Auto-flagging content when report threshold reached (>= 2 reports).
8. Host Admin reviews moderation report, hides content, and audits in community_moderation_audit_logs.
9. Knowledge article search & filtering by crop, topic, region with official citations.
10. Permission gating: unauthorized non-admin/non-expert blocked from publishing knowledge articles.
"""

import unittest
import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
import sqlite3
import uuid

from api_server import app
from gari_database import get_connection

client = TestClient(app)


def _create_user(name_prefix="User", account_type="farmer"):
    unique_id = uuid.uuid4().hex[:8]
    email = f"{name_prefix.lower()}_{unique_id}@example.com"
    pwd = "Password123!"
    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": pwd,
        "confirm_password": pwd,
        "full_name": f"{name_prefix} {unique_id}",
        "account_type": account_type
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    user = data.get("user", {})
    return user, token, {"Authorization": f"Bearer {token}"}


def _create_host_admin():
    user, token, headers = _create_user("HostAdmin", account_type="admin")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_host_admin = 1, is_admin = 1 WHERE id = ?", (user["id"],))
        conn.commit()
    return user, token, headers


def _create_verified_expert(name_prefix="Agronomist"):
    user, token, headers = _create_user(name_prefix, account_type="expert")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_expert = 1, is_host_admin = 0 WHERE id = ?", (user["id"],))
        cursor.execute("""
            INSERT OR REPLACE INTO expert_profiles (
                user_id, full_name, display_title, institution, degree, specialization,
                primary_crops_json, farming_regions_json, status, is_active, rating, cases_resolved_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, 5.0, 0)
        """, (
            user["id"],
            user["full_name"],
            "Kỹ sư Bảo vệ Thực vật",
            "Viện BVTV Quốc Gia",
            "Thạc sĩ",
            "Bệnh học cây trồng nhiệt đới",
            '["tomato", "coffee", "rice"]',
            '["Tây Nguyên", "Đồng bằng Sông Cửu Long"]'
        ))
        conn.commit()
    return user, token, headers


class TestModule08CommunityKnowledge(unittest.TestCase):

    def setUp(self):
        self.farmer, self.farmer_token, self.farmer_headers = _create_user("Farmer08", account_type="farmer")
        self.expert, self.expert_token, self.expert_headers = _create_verified_expert("Expert08")
        self.host, self.host_token, self.host_headers = _create_host_admin()

    def test_01_create_community_question_post(self):
        """1. Farmer creates question post with crop, region, and content."""
        payload = {
            "title": "Hỏi về hiện tượng lá tiêu vàng xoăn đọt ở Gia Lai",
            "content": "Vườn tiêu 2 năm tuổi của tôi bị vàng từ đọt non xuống, có rệp sáp trắng quanh gốc. Xin kinh nghiệm xử lý sinh học an toàn.",
            "crop_id": "pepper",
            "region": "Tây Nguyên",
            "post_type": "question"
        }
        resp = client.post("/api/community/posts", json=payload, headers=self.farmer_headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data.get("success"))
        post = data.get("post")
        self.assertIsNotNone(post)
        self.assertEqual(post["title"], payload["title"])
        self.assertEqual(post["crop_id"], "pepper")
        self.assertEqual(post["region"], "Tây Nguyên")
        self.assertEqual(post["review_status"], "community_unverified")
        self.assertEqual(post["is_official_guidance"], 0)

    def test_02_post_retrieval_with_expert_credentials(self):
        """2. Post retrieval accurately reflects author credentials & verified expert badge."""
        payload = {
            "title": "Khuyến cáo phòng trừ sâu đục thân lúa vụ Đông Xuân",
            "content": "Bà con nông dân khu vực ĐBSCL cần chú ý thời điểm ngắt lứa sâu đục thân hai chấm khi bướm rộ 5-7 ngày.",
            "crop_id": "rice",
            "region": "Đồng bằng Sông Cửu Long",
            "post_type": "discussion"
        }
        create_resp = client.post("/api/community/posts", json=payload, headers=self.expert_headers)
        self.assertEqual(create_resp.status_code, 200, create_resp.text)
        post_id = create_resp.json()["post"]["id"]

        get_resp = client.get(f"/api/community/posts/{post_id}", headers=self.farmer_headers)
        self.assertEqual(get_resp.status_code, 200, get_resp.text)
        post = get_resp.json()["post"]
        self.assertEqual(post["id"], post_id)
        self.assertEqual(post["author_is_expert"], 1)
        self.assertEqual(post["author_expert_title"], "Kỹ sư Bảo vệ Thực vật")
        self.assertEqual(post["author_institution"], "Viện BVTV Quốc Gia")
        self.assertEqual(post["review_status"], "expert_reviewed")

    def test_03_comment_and_nested_reply_with_expert_badge(self):
        """3. Commenting & nested replies with is_expert_answer = 1 for agronomists."""
        # Create a post
        p_res = client.post("/api/community/posts", json={
            "title": "Bệnh thán thư trên ớt mùa mưa",
            "content": "Trái ớt bị đốm lõm tròn đồng tâm, xin biện pháp can thiệp gấp.",
            "crop_id": "chili",
            "region": "Miền Trung"
        }, headers=self.farmer_headers).json()
        post_id = p_res["post"]["id"]

        # Farmer asks clarification
        c1_resp = client.post(f"/api/community/posts/{post_id}/comments", json={
            "content": "Tôi đã phun Booc-đô nhưng trời mưa nhiều quá bị trôi."
        }, headers=self.farmer_headers)
        self.assertEqual(c1_resp.status_code, 200, c1_resp.text)
        c1 = c1_resp.json()["comment"]
        self.assertEqual(c1["is_expert_answer"], 0)

        # Expert replies with prescription
        c2_resp = client.post(f"/api/community/posts/{post_id}/comments", json={
            "content": "Nên phối hợp Azoxystrobin + Difenoconazole và chất bám dính sinh học, phun lúc tạnh ráo buổi sáng sớm.",
            "parent_comment_id": c1["id"]
        }, headers=self.expert_headers)
        self.assertEqual(c2_resp.status_code, 200, c2_resp.text)
        c2 = c2_resp.json()["comment"]
        self.assertEqual(c2["is_expert_answer"], 1)
        self.assertEqual(c2["parent_comment_id"], c1["id"])

        # Fetch comments list
        list_resp = client.get(f"/api/community/posts/{post_id}/comments")
        self.assertEqual(list_resp.status_code, 200)
        comments = list_resp.json()["comments"]
        self.assertEqual(len(comments), 2)
        expert_c = next(c for c in comments if c["id"] == c2["id"])
        self.assertEqual(expert_c["author_is_expert"], 1)

    def test_04_idempotent_like_reactions(self):
        """4. Idempotent toggle of likes/reactions for posts and comments."""
        p_res = client.post("/api/community/posts", json={
            "title": "Chia sẻ kinh nghiệm ủ phân hữu cơ vi sinh từ vỏ cà phê",
            "content": "Sử dụng chế phẩm Trichoderma ủ cùng vỏ trấu cà phê 45 ngày phân giải rất tốt.",
            "crop_id": "coffee"
        }, headers=self.farmer_headers).json()
        post_id = p_res["post"]["id"]

        # Like post
        like_resp1 = client.post(f"/api/community/posts/{post_id}/like", headers=self.farmer_headers)
        self.assertEqual(like_resp1.status_code, 200)
        self.assertTrue(like_resp1.json()["liked"])
        self.assertEqual(like_resp1.json()["likes_count"], 1)

        # Unlike post (toggle)
        like_resp2 = client.post(f"/api/community/posts/{post_id}/like", headers=self.farmer_headers)
        self.assertEqual(like_resp2.status_code, 200)
        self.assertFalse(like_resp2.json()["liked"])
        self.assertEqual(like_resp2.json()["likes_count"], 0)

    def test_05_review_status_and_official_guidance_distinction(self):
        """5. Distinguishing official/reviewed guidance from community chatter (review_status enforcement)."""
        # Farmer tries to claim official guidance
        resp_farmer = client.post("/api/community/posts", json={
            "title": "Mẹo dân gian trị bệnh vàng lá rụng hoa",
            "content": "Tưới nước muối pha loãng vào gốc tiêu mỗi tuần một lần.",
            "is_official_guidance": True
        }, headers=self.farmer_headers)
        post_farmer = resp_farmer.json()["post"]
        # Must be sanitized to community_unverified and is_official_guidance = 0
        self.assertEqual(post_farmer["is_official_guidance"], 0)
        self.assertEqual(post_farmer["review_status"], "community_unverified")

        # Host Admin publishes official guidance
        resp_host = client.post("/api/community/posts", json={
            "title": "Quy chuẩn Quốc gia QCVN về phòng trừ rầy nâu hại lúa",
            "content": "Văn bản hướng dẫn kỹ thuật phòng trừ rầy nâu của Cục Trồng trọt và Bảo vệ Thực vật.",
            "crop_id": "rice",
            "is_official_guidance": True
        }, headers=self.host_headers)
        self.assertEqual(resp_host.status_code, 200)
        post_host = resp_host.json()["post"]
        self.assertEqual(post_host["is_official_guidance"], 1)
        self.assertEqual(post_host["review_status"], "official_verified")

    def test_06_report_misleading_content(self):
        """6. User reporting of misleading advice (community_reports)."""
        # Create unverified suspicious post
        p_res = client.post("/api/community/posts", json={
            "title": "Thuốc hóa học cấm trôi nổi",
            "content": "Tôi có bán thuốc diệt cỏ lưu dẫn cực mạnh không nhãn mác, ai cần liên hệ.",
            "crop_id": "rice"
        }, headers=self.farmer_headers).json()
        post_id = p_res["post"]["id"]

        reporter, _, reporter_headers = _create_user("Reporter1")
        report_resp = client.post("/api/community/reports", json={
            "target_type": "post",
            "target_id": post_id,
            "reason_category": "inappropriate_content",
            "reason_details": "Rao bán hóa chất BVTV cấm không rõ nguồn gốc gây nguy hại môi trường."
        }, headers=reporter_headers)
        self.assertEqual(report_resp.status_code, 200, report_resp.text)
        report = report_resp.json()["report"]
        self.assertEqual(report["target_id"], post_id)
        self.assertEqual(report["status"], "pending")

    def test_07_auto_flagging_on_report_threshold(self):
        """7. Auto-flagging content when report threshold reached (>= 2 reports)."""
        p_res = client.post("/api/community/posts", json={
            "title": "Chia sẻ thông tin sai lệch về bệnh sầu riêng",
            "content": "Cạo sạch vỏ thân cây sầu riêng rồi bôi dầu hỏa để trị xì mủ Phytophthora.",
            "crop_id": "durian"
        }, headers=self.farmer_headers).json()
        post_id = p_res["post"]["id"]

        user_a, _, h_a = _create_user("AuditorA")
        user_b, _, h_b = _create_user("AuditorB")

        # Report 1
        client.post("/api/community/reports", json={
            "target_type": "post",
            "target_id": post_id,
            "reason_category": "misleading_advice",
            "reason_details": "Cách làm này làm chết cây ngay lập tức."
        }, headers=h_a)

        # Check post still active
        p_mid = client.get(f"/api/community/posts/{post_id}").json()["post"]
        self.assertEqual(p_mid["status"], "active")

        # Report 2 -> Triggers auto-flag threshold
        client.post("/api/community/reports", json={
            "target_type": "post",
            "target_id": post_id,
            "reason_category": "misleading_advice",
            "reason_details": "Báo cáo nội dung nguy hại đến cây trồng."
        }, headers=h_b)

        p_flagged = client.get(f"/api/community/posts/{post_id}").json()["post"]
        self.assertEqual(p_flagged["status"], "flagged")
        self.assertGreaterEqual(p_flagged["reports_count"], 2)

    def test_08_host_moderation_review_and_audit_logging(self):
        """8. Host Admin reviews moderation report, hides content, and audits in community_moderation_audit_logs."""
        # Create spam post
        p_res = client.post("/api/community/posts", json={
            "title": "Spam quảng cáo cờ bạc",
            "content": "Nhà cái uy tín số 1 Việt Nam nạp rút nhanh chóng.",
            "crop_id": "corn"
        }, headers=self.farmer_headers).json()
        post_id = p_res["post"]["id"]

        reporter, _, r_headers = _create_user("ReporterSpam")
        r_res = client.post("/api/community/reports", json={
            "target_type": "post",
            "target_id": post_id,
            "reason_category": "spam_advertising",
            "reason_details": "Spam quảng cáo cờ bạc vào diễn đàn nông nghiệp."
        }, headers=r_headers).json()
        report_id = r_res["report"]["id"]

        # Host reviews and executes 'hide_content'
        rev_resp = client.post(f"/api/host/community/reports/{report_id}/review", json={
            "action": "hide_content",
            "review_notes": "Xác nhận vi phạm tiêu chuẩn cộng đồng, ẩn bài viết và ghi nhận cảnh cáo."
        }, headers=self.host_headers)
        self.assertEqual(rev_resp.status_code, 200, rev_resp.text)

        # Normal user (not author, not host) cannot view hidden post
        anon_get = client.get(f"/api/community/posts/{post_id}", headers=r_headers)
        self.assertEqual(anon_get.status_code, 403)

        # Check community_moderation_audit_logs and host_audit_logs
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM community_moderation_audit_logs WHERE target_id = ?", (post_id,))
            audit_comm = cursor.fetchone()
            self.assertIsNotNone(audit_comm)
            self.assertEqual(audit_comm["action"], "hide_content")

            cursor.execute("SELECT * FROM host_audit_logs WHERE target_resource = ?", (f"community_report:{report_id}",))
            audit_host = cursor.fetchone()
            self.assertIsNotNone(audit_host)
            self.assertEqual(audit_host["action_type"], "COMMUNITY_MODERATION")

    def test_09_knowledge_article_search_and_official_citations(self):
        """9. Knowledge article search & filtering by crop, topic, region with official citations."""
        resp = client.get("/api/knowledge/articles?crop_id=coffee&topic=pest_disease")
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertTrue(data.get("success"))
        articles = data.get("articles", [])
        self.assertGreaterEqual(len(articles), 1)

        art = articles[0]
        self.assertEqual(art["crop_id"], "coffee")
        self.assertIn("WASI", art["source_institution"])
        self.assertEqual(art["review_status"], "official_verified")
        self.assertIsNotNone(art["publication_date"])

        # Fetch detail by slug
        slug = art["slug"]
        detail_resp = client.get(f"/api/knowledge/articles/{slug}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["article"]["title"], art["title"])

    def test_10_permission_gating_knowledge_articles(self):
        """10. Permission gating: unauthorized non-admin/non-expert blocked from publishing knowledge articles."""
        article_payload = {
            "title": "Hướng dẫn kỹ thuật thâm canh cà phê bền vững",
            "summary": "Tài liệu đào tạo khuyến nông cho vùng Tây Nguyên.",
            "content_markdown": "### Quy trình tưới nước tiết kiệm và bón phân theo giai đoạn phân hóa mầm hoa.",
            "crop_id": "coffee",
            "source_institution": "Viện WASI",
            "author_name": "TS. Nguyễn Văn A",
            "publication_date": "2025-01-10"
        }

        # Regular farmer blocked with 403 Forbidden
        farmer_post = client.post("/api/knowledge/articles", json=article_payload, headers=self.farmer_headers)
        self.assertEqual(farmer_post.status_code, 403)

        # Host Admin allowed
        host_post = client.post("/api/knowledge/articles", json=article_payload, headers=self.host_headers)
        self.assertEqual(host_post.status_code, 200, host_post.text)
        self.assertTrue(host_post.json()["success"])
        self.assertEqual(host_post.json()["article"]["title"], article_payload["title"])


if __name__ == "__main__":
    unittest.main()
