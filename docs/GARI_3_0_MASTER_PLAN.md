# GARI 3.0 — MASTER IMPLEMENTATION PLAN
## Core Scope | Stabilize First | Competition Priority

**Project:** GARI AgriTech AI Platform  
**Repository:** `D:\leaf-diseases-detector-main`  
**GitHub:** `https://github.com/builedanhuygov-alt/Gari`  
**Branch:** `gari-2.0-redesign`  
**Vercel project:** `gari-team` (Account: `dhuyhk123-7041`, Team: `bui11`, Project ID: `prj_WSNxryEdSCGbZQ5yBbQMzdjbvE1Y`)  
**Production domain:** `https://gari-team.vercel.app`  

---

## 1. PRODUCT SCOPE & STRATEGY

GARI 3.0 Core phục vụ 2 nhóm người dùng mục tiêu:
1. **Nông hộ cá thể (Individual Farmers):** Chẩn đoán bệnh lá qua ảnh AI thời gian thực, quản lý lịch canh tác vi khí hậu theo vị trí địa lý, nhận cảnh báo dịch hại và hướng dẫn kỹ thuật nông nghiệp an toàn IPM.
2. **Hợp tác xã & Doanh nghiệp Nông nghiệp (Cooperatives & Agri-Enterprises):** Quản lý tập trung đa nông trại, phân vùng cây trồng, thẩm định dữ liệu thực địa (Field Lab) và theo dõi chất lượng mô hình AI.

**Ưu tiên cao nhất:** Hoàn thiện sản phẩm phục vụ cuộc thi KHKT, đảm bảo mọi luồng hoạt động thực tế, không dùng dữ liệu giả lập, có thể trình diễn và nghiệm thu bằng dữ liệu thực.

### Phân tầng tính năng:
- **Core P0 (Độ tin cậy nền tảng):**
  - E00: Project Baseline & Source Audit.
  - E01: Authentication & Account Integrity (Đăng ký, Đăng nhập, Session HttpOnly, CSRF, Đồng bộ Hồ sơ).
  - E02: Quota, VIP Trial & Voucher Management (Hạn mức 5 lượt/ngày, Voucher `Gari-THPTNHD1` dùng thử 7 ngày, Transaction an toàn).
  - E03: Hybrid AI Inference Platform (Windows Local Worker primary, Cloud Worker fallback, Inference Router failover, Model Preloading).
  - E04: Diagnosis History & AI Feedback Loop (Lưu chẩn đoán chuẩn hóa, phản hồi sai số thực tế).
- **Core P1 (Trí tuệ Nông nghiệp Cá nhân hóa):**
  - E05: Farm Profile & Multi-Farm Foundation (Hồ sơ vườn độc lập, đa vườn, cách ly dữ liệu triệt để).
  - E06: Farm Digital Map & Local Weather Integration (Bản đồ số, tích hợp Open-Meteo theo tọa độ GPS và cao độ thực tế).
  - E07: Personalized Smart Calendar & Early Warning System (Lập lịch mùa vụ 7 cây trồng chủ lực, cảnh báo mưa/ẩm thích ứng tự động).
  - E08: Field Lab & Dataset Governance (Thu thập ảnh thực địa, quy trình thẩm định mẫu, chống rò rỉ dữ liệu dataset).
  - E09: AI Model Intelligence Center (Quản lý phiên bản model, ma trận đánh giá, giám sát độ trễ và lỗi suy luận).
  - E10: Competition Demo & Presentation Mode (Môi trường demo độc lập, kịch bản thuyết trình KHKT).
- **Hoãn triển khai (Explicitly Deferred):**
  - Tự động hóa tưới tiêu thông minh bằng van IoT.
  - Sàn giao dịch thương mại nông sản (Marketplace).
  - Hệ thống truy xuất nguồn gốc QR thương phẩm.
  - Hệ thống kế toán tài chính hoàn chỉnh cho HTX.

---

## 2. STATUS TRACKING DASHBOARD

| Epic | Tên Epic | Mức ưu tiên | Trạng thái hiện tại | Phụ thuộc |
|---|---|---|---|---|
| **E00** | **Project Baseline & Source Audit** | **P0** | **AUDITED (READY FOR REVIEW)** | None |
| **E01** | **Authentication & Account Integrity** | **P0** | **READY (PENDING GATE E00)** | E00 |
| **E02** | **Quota, VIP Trial & Voucher** | **P0** | **READY** | E01 |
| **E03** | **Hybrid AI Inference Platform** | **P0** | **READY** | E00, E01, E02 |
| **E04** | **Diagnosis History & AI Feedback** | **P0/P1** | **READY** | E01, E02, E03 |
| **E05** | **Farm Profile & Multi-Farm Foundation** | **P1** | **IMPLEMENTED BASELINE** | E01, E00 |
| **E06** | **Farm Digital Map & Local Weather** | **P1** | **IMPLEMENTED BASELINE** | E05 |
| **E07** | **Personalized Smart Calendar & Warning** | **P1** | **IMPLEMENTED BASELINE** | E05, E06 |
| **E08** | **Field Lab & Dataset Governance** | **P1** | **NOT_STARTED** | E01, E03, E04 |
| **E09** | **AI Model Intelligence Center** | **P1** | **NOT_STARTED** | E03, E04, E08 |
| **E10** | **Competition Demo & Presentation Mode** | **P1** | **NOT_STARTED** | E01–E09 |
