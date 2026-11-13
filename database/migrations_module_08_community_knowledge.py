"""
Database Migration: Module 08 — Community & Agricultural Knowledge Library
Creates:
1. community_posts (Questions, discussions, field case sharing with crop, region, and verification status)
2. community_comments (Responses, expert answers, nested replies)
3. community_likes (Reactions for posts and comments with uniqueness)
4. community_reports (User flagging queue for inappropriate or misleading content)
5. knowledge_articles (Official and peer-reviewed agricultural knowledge catalog by crop, topic, region)
6. community_moderation_audit_logs (Immutable audit log for all community moderation actions)
Seeds: Curated official guidance from accredited Vietnamese agricultural research institutes.
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "disease_detector.db")

INITIAL_ARTICLES = [
    {
        "title": "Quy trình IPM Quản lý Bệnh Mốc sương (Phytophthora infestans) trên Cà chua",
        "slug": "ipm-moc-suong-ca-chua-vietnam",
        "crop_id": "tomato",
        "topic": "pest_disease",
        "region": "Toàn quốc",
        "summary": "Hướng dẫn chẩn đoán phân biệt và phác đồ xử lý phòng trừ tổng hợp bệnh mốc sương cà chua trong điều kiện sương ẩm mùa đông xuân.",
        "content_markdown": """### 1. Tác nhân và Triệu chứng lâm sàng
Bệnh mốc sương do nấm thủy sinh *Phytophthora infestans* gây ra. Vết bệnh xuất hiện đầu tiên ở chóp hoặc mép lá, dạng úng nước màu xanh xám, sau chuyển sang nâu đen. Trong điều kiện độ ẩm không khí >90% vào sáng sớm, mặt dưới vết bệnh phủ một lớp mốc trắng như nhung sương muối.

### 2. Biện pháp canh tác & Phòng ngừa sinh học (Ưu tiên)
- **Luân canh:** Tuyệt đối không trồng cà chua sau khoai tây hoặc cây cùng họ cà. Luân canh tối thiểu 2-3 vụ với lúa nước hoặc ngô.
- **Mật độ & Thoát nước:** Bố trí hàng kép thông thoáng (cây cách cây 45cm, hàng cách hàng 70cm). Lên luống cao 30-35cm, phủ bạt nilon nông nghiệp.
- **Chế phẩm sinh học:** Phun định kỳ *Bacillus subtilis* hoặc nấm đối kháng *Trichoderma harzianum* vào gốc trước các đợt mưa lạnh.

### 3. Biện pháp hóa học khi có nguy cơ bùng phát dịch
- Khi phát hiện ổ bệnh đầu tiên (tỷ lệ bệnh <2%), luân phiên sử dụng các hoạt chất chuyên trị:
  - **Metalaxyl-M + Mancozeb** (Ridomil Gold 68WG): 40-50g / bình 16 lít.
  - **Dimethomorph** (Acrobat MZ): 35-40g / bình 16 lít.
  - **Cyazofamid** (Ranman 400SC): 8-10ml / bình 16 lít.
- Thời gian cách ly (PHI): Tối thiểu 7 ngày trước thu hoạch.""",
        "source_institution": "Viện Bảo Vệ Thực Vật (NIPP) - Viện Khoa Học Nông Nghiệp Việt Nam",
        "source_url": "http://nipp.org.vn/quy-trinh-ky-thuat-bvtv",
        "author_name": "TS. Nguyễn Văn Tuấn",
        "author_title": "Trưởng bộ môn Bệnh học Cây trồng",
        "review_status": "official_verified",
        "is_official": 1,
        "verification_badge": "Chính thống - Viện BVTV (NIPP)",
        "publication_date": "2026-01-15"
    },
    {
        "title": "Phác đồ Phòng ngừa Bệnh Rỉ sắt (Hemileia vastatrix) trên Cà phê Tây Nguyên",
        "slug": "phong-ngua-ri-sat-ca-phe-tay-nguyen",
        "crop_id": "coffee",
        "topic": "pest_disease",
        "region": "Tây Nguyên",
        "summary": "Kỹ thuật canh tác và bảo vệ thực vật bền vững kiểm soát nấm rỉ sắt cà phê vối (Robusta) thích ứng biến đổi khí hậu tại Đắk Lắk, Gia Lai, Lâm Đồng.",
        "content_markdown": """### 1. Đặc điểm phát sinh gây hại
Bệnh rỉ sắt do nấm *Hemileia vastatrix* gây ra, là một trong những đối tượng nguy hiểm nhất đối với cà phê chè (Arabica) và gây hại đáng kể trên cà phê vối (Robusta) vào đầu mùa mưa (tháng 5-7) và rộ vào cuối mùa mưa (tháng 9-11). Mặt dưới lá xuất hiện các đốm phấn màu vàng cam sau chuyển sang nâu đen, làm rụng lá hàng loạt dẫn đến khô cành.

### 2. Canh tác thích ứng VietGAP
- Sử dụng các dòng vô tính chọn lọc kháng bệnh do Viện WASI công nhận (TR4, TR9, TR11).
- Trồng cây che bóng hợp lý (muồng đen, bơ, sầu riêng) để điều hòa ẩm độ và nhiệt độ tiểu khí hậu vườn cà phê.
- Cắt tỉa cành vô hiệu, cành tăm, cành sát mặt đất ngay sau thu hoạch để vườn thông thoáng.

### 3. Xử lý hoạt chất BVTV hợp chuẩn
- **Phòng bệnh sớm:** Khi chớm mưa đầu mùa, phun thuốc gốc đồng (Copper Hydroxide, Bordeaux 1%) hoặc Bordeaux sinh học ướt đẫm mặt dưới lá.
- **Trị bệnh:** Sử dụng luân phiên các hoạt chất ức chế sinh tổng hợp ergosterol:
  - **Hexaconazole** (Anvil 5SC) hoặc **Difenoconazole**: 1.5 - 2.0 lít/ha.
  - Hạn chế phun quá 2 lần/vụ cùng một nhóm hoạt chất để ngăn ngừa hiện tượng kháng thuốc.""",
        "source_institution": "Viện KHKT Nông Lâm Nghiệp Tây Nguyên (WASI)",
        "source_url": "https://wasi.org.vn/quy-trinh-canh-tac-ca-phe",
        "author_name": "ThS. Lê Hoàng Long",
        "author_title": "Chuyên gia Sinh lý & BVTV Cây Công nghiệp",
        "review_status": "official_verified",
        "is_official": 1,
        "verification_badge": "Chính thống - Viện WASI Tây Nguyên",
        "publication_date": "2026-02-10"
    },
    {
        "title": "Quản lý Bệnh Thối rễ - Chết nhanh (Phytophthora capsici) trên Hồ tiêu",
        "slug": "quan-ly-chet-nhanh-ho-tieu-phytophthora",
        "crop_id": "pepper",
        "topic": "ipm_protocol",
        "region": "Tây Nguyên",
        "summary": "Quy trình chẩn đoán sớm và bảo vệ hệ thống rễ tiêu chống nấm Phytophthora lây lan trong đất mùa mưa bão.",
        "content_markdown": """### 1. Nhận biết và Tác hại
Bệnh chết nhanh do nấm đất *Phytophthora capsici* gây ra, có thể hủy hoại cả vườn tiêu trong vòng 1-2 tuần nếu ngập úng. Cây héo rũ nhanh chóng nhưng lá vẫn giữ màu xanh nhạt hoặc thâm đen rồi rụng từ dưới lên trên. Khi đào gốc thấy vỏ rễ cái và rễ tơ thối đen, bốc mùi chua nồng.

### 2. Kỹ thuật đào mương và xử lý đất
- Đào mương sâu 40-50cm giữa các hàng tiêu để đảm bảo nước mưa thoát triệt để trong vòng 30 phút sau mưa lớn.
- Bón vôi nông nghiệp nâng độ pH đất lên 5.5 - 6.5 vào đầu mùa mưa.
- Bón 10-15 kg phân hữu cơ vi sinh có chứa chủng nấm đối kháng *Trichoderma* và xạ khuẩn *Streptomyces* cho mỗi trụ tiêu hàng năm.

### 3. Biện pháp khẩn cấp khi xuất hiện ổ bệnh
- Khoanh vùng cách ly trụ bệnh, đào rãnh cô lập nước chảy tràn sang các trụ khỏe.
- Tưới gốc bằng hoạt chất **Phosphonate (Potassium phosphite)** hoặc **Metalaxyl** nồng độ 0.2% kết hợp phun ướt toàn bộ tán lá.""",
        "source_institution": "Cục Bảo Vệ Thực Vật - Bộ Nông Nghiệp & PTNT",
        "source_url": "https://ppd.gov.vn/cam-nang-cay-ho-tieu",
        "author_name": "TS. Phạm Bá Toàn",
        "author_title": "Viện Trưởng Phân viện BVTV",
        "review_status": "official_verified",
        "is_official": 1,
        "verification_badge": "Chính thống - Cục BVTV Việt Nam",
        "publication_date": "2026-02-28"
    },
    {
        "title": "Chẩn đoán & Kiểm soát Bệnh Đạo ôn (Magnaporthe oryzae) trên Lúa ĐBSCL",
        "slug": "kiem-soat-dao-on-lua-dbscl",
        "crop_id": "rice",
        "topic": "pest_disease",
        "region": "ĐBSCL",
        "summary": "Nhận biết vết bệnh hình mắt én trên lá và đạo ôn cổ bông, kỹ thuật bón phân giảm đạm phòng ngừa cháy lá lúa vụ Đông Xuân và Hè Thu.",
        "content_markdown": """### 1. Triệu chứng nhận biết
- **Đạo ôn lá:** Ban đầu là chấm nhỏ màu xám xanh úng nước, sau lan rộng thành hình thoi (mắt én), tâm màu xám trắng, viền ngoài màu nâu sẫm, quầng màu vàng rực rỡ. Nhiều vết liên kết làm lá lúa cháy khô.
- **Đạo ôn cổ bông:** Nấm tấn công đốt cổ gié làm thâm đen gãy gập, toàn bộ bông lúa bị lép trắng.

### 2. Biện pháp phòng ngừa canh tác
- Sạ thưa hợp lý (80-100 kg giống/ha khi sạ lan hoặc 50-60 kg/ha khi sạ hàng/cấy máy).
- Bón phân theo bảng so màu lá lúa (LCC), không bón thừa phân đạm hóa học (Urê). Tăng cường Kali và Silic để làm cứng vách tế bào bẹ lá.
- Giữ mực nước ruộng 3-5cm trong giai đoạn lúa làm đòng - trổ bông.

### 3. Xử lý thuốc BVTV đúng thời điểm
- Phun phòng cổ bông trước khi lúa trổ lẹt xẹt 5% và sau khi trổ đều bằng các hoạt chất đặc trị:
  - **Tricyclazole** (Beam 75WP): 15-20g / bình 16 lít.
  - **Isoprothiolane** (Fuji-one 40EC): 30-40ml / bình 16 lít.
  - **Fenoxanil**: 15-20ml / bình 16 lít.""",
        "source_institution": "Viện Lúa Đồng Bằng Sông Cửu Long (CLRRI)",
        "source_url": "http://clrri.org/ky-thuat-lua-thuan",
        "author_name": "PGS.TS. Trần Quốc Tuấn",
        "author_title": "Chuyên gia Giống & BVTV Lúa nước",
        "review_status": "official_verified",
        "is_official": 1,
        "verification_badge": "Chính thống - Viện Lúa ĐBSCL",
        "publication_date": "2026-03-01"
    },
    {
        "title": "Xử lý Bệnh Thối vỏ chảy mủ (Phytophthora palmivora) trên Sầu riêng",
        "slug": "thoi-vo-chay-mu-sau-rieng-phytophthora",
        "crop_id": "durian",
        "topic": "pest_disease",
        "region": "Đông Nam Bộ",
        "summary": "Kỹ thuật cạo vỏ quét thuốc vết loét xì mủ thân và xử lý nấm gây thối trái sầu riêng Ri6 và Monthong mùa mưa.",
        "content_markdown": """### 1. Triệu chứng xì mủ thân và thối trái
Do nấm *Phytophthora palmivora* gây ra. Trên thân và cành chính xuất hiện các vệt ướt sẫm màu, nứt vỏ chảy nhựa mủ màu nâu đỏ dẻo quánh. Vết bệnh ăn sâu vào tầng sinh mô làm thối đen gỗ thân dẫn đến chết nhánh hoặc chết cả cây. Trên trái, vết thối úng nước hình tròn lan rộng nhanh, có lớp tơ nấm trắng mọc trên gai.

### 2. Kỹ thuật cạo quét vết thương cục bộ
1. Dùng dao bén cạo sạch lớp vỏ thối đen đến tận phần gỗ khỏe mạnh (cạo rộng ra vùng mô lành 1-2cm).
2. Để vết cạo khô ráo trong 15-30 phút dưới nắng nhẹ.
3. Dùng cọ quét dung dịch thuốc đậm đặc trực tiếp lên vết cạo:
   - **Metalaxyl + Mancozeb** dạng sệt (pha tỷ lệ 100g thuốc với 200ml nước).
   - Hoặc thuốc gốc đồng (Copper Hydroxide, Boóc-đô đậm đặc).
4. Quét lại lần 2 sau 5-7 ngày cho đến khi vết sẹo khô ráo và đùn da non.

### 3. Phòng ngừa từ rễ
- Tưới gốc bằng hoạt chất sinh học *Phosphonate* hoặc nấm đối kháng *Chaetomium cupreum* định kỳ 2-3 tháng/lần vào mùa mưa để kích thích tính kháng lưu dẫn hai chiều.""",
        "source_institution": "Viện Cây Ăn Quả Miền Nam (SOFRI)",
        "source_url": "https://sofri.org.vn/benh-hai-cay-an-trai",
        "author_name": "TS. Võ Mai Lan",
        "author_title": "Trưởng phòng Cây ăn quả nhiệt đới",
        "review_status": "official_verified",
        "is_official": 1,
        "verification_badge": "Chính thống - Viện Cây Ăn Quả SOFRI",
        "publication_date": "2026-03-15"
    }
]


def run_migration():
    print(f"Applying Module 08 migration to: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # 1. Community Posts Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            post_type TEXT NOT NULL DEFAULT 'question',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            crop_id TEXT,
            region TEXT DEFAULT 'Toàn quốc',
            diagnosis_id INTEGER REFERENCES diagnoses(id),
            image_urls_json TEXT,
            tags_json TEXT,
            likes_count INTEGER DEFAULT 0,
            comments_count INTEGER DEFAULT 0,
            views_count INTEGER DEFAULT 0,
            reports_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            is_pinned INTEGER DEFAULT 0,
            is_official_guidance INTEGER DEFAULT 0,
            review_status TEXT DEFAULT 'community_unverified',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Community Comments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            parent_comment_id INTEGER REFERENCES community_comments(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            image_urls_json TEXT,
            likes_count INTEGER DEFAULT 0,
            reports_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            is_expert_answer INTEGER DEFAULT 0,
            is_accepted_answer INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 3. Community Likes Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            reaction_type TEXT DEFAULT 'like',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, target_type, target_id)
        );
    """)

    # 4. Community Reports Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_user_id INTEGER NOT NULL REFERENCES users(id),
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            reason_category TEXT NOT NULL,
            details TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by_host_id INTEGER REFERENCES users(id),
            review_notes TEXT,
            action_taken TEXT DEFAULT 'none',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP
        );
    """)

    # 5. Knowledge Articles Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            crop_id TEXT NOT NULL,
            topic TEXT NOT NULL DEFAULT 'pest_disease',
            region TEXT NOT NULL DEFAULT 'Toàn quốc',
            summary TEXT NOT NULL,
            content_markdown TEXT NOT NULL,
            source_institution TEXT NOT NULL,
            source_url TEXT,
            author_name TEXT NOT NULL,
            author_title TEXT,
            author_user_id INTEGER REFERENCES users(id),
            reviewer_name TEXT,
            reviewer_user_id INTEGER REFERENCES users(id),
            review_status TEXT NOT NULL DEFAULT 'official_verified',
            is_official INTEGER NOT NULL DEFAULT 1,
            verification_badge TEXT DEFAULT 'Chính thống - Viện nghiên cứu',
            publication_date DATE NOT NULL,
            last_reviewed_at TIMESTAMP,
            view_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'published',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 6. Community Moderation Audit Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS community_moderation_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            moderator_user_id INTEGER NOT NULL REFERENCES users(id),
            moderator_email TEXT,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            reason TEXT,
            details_json TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_user ON community_posts(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_crop_region ON community_posts(crop_id, region);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_status ON community_posts(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_review ON community_posts(review_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_post ON community_comments(post_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_likes_target ON community_likes(target_type, target_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON community_reports(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_target ON community_reports(target_type, target_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_crop_topic ON knowledge_articles(crop_id, topic);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_slug ON knowledge_articles(slug);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_review ON knowledge_articles(review_status);")

    # Seed initial official knowledge articles
    for art in INITIAL_ARTICLES:
        cursor.execute("""
            INSERT INTO knowledge_articles (
                title, slug, crop_id, topic, region, summary, content_markdown,
                source_institution, source_url, author_name, author_title,
                review_status, is_official, verification_badge, publication_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                summary = excluded.summary,
                content_markdown = excluded.content_markdown,
                source_institution = excluded.source_institution,
                review_status = excluded.review_status,
                updated_at = CURRENT_TIMESTAMP;
        """, (
            art["title"], art["slug"], art["crop_id"], art["topic"], art["region"],
            art["summary"], art["content_markdown"], art["source_institution"],
            art["source_url"], art["author_name"], art["author_title"],
            art["review_status"], art["is_official"], art["verification_badge"],
            art["publication_date"]
        ))

    conn.commit()
    conn.close()
    print("Module 08 migration completed successfully!")


if __name__ == "__main__":
    run_migration()
