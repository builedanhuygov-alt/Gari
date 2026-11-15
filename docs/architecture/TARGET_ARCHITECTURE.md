# GARI 3.0 — TARGET ARCHITECTURE & ROADMAP

## 1. MỤC TIÊU THIẾT KẾ KIẾN TRÚC MỤC TIÊU

Kiến trúc mục tiêu GARI 3.0 hướng tới việc khép kín chu trình trí tuệ nông nghiệp thực địa:

> **Thấu hiểu Nông trại (Understand the Farm) → Quan sát Cây trồng (Observe the Crop) → Phát hiện Vấn đề (Detect the Problem) → Giải thích Nguy cơ (Explain the Risk) → Khuyến nghị Hành động (Recommend an Action) → Ghi nhận Kết quả (Record the Outcome) → Tối ưu Trí tuệ AI (Improve the Intelligence).**

```
┌────────────────────────────────────────────────────────────────────────┐
│                          GARI 3.0 ECOSYSTEM                            │
└────────────────────────────────────────────────────────────────────────┘
                                    │
       ┌────────────────────────────┴───────────────────────────┐
       ▼                                                        ▼
[NÔNG HỘ & HỢP TÁC XÃ]                                   [CHUYÊN GIA NÔNG NGHIỆP]
  • Quản lý đa nông trại (GPS, Cao độ)                     • Thẩm định nhãn thực địa (Field Lab)
  • Lịch canh tác vi khí hậu thích ứng                    • Xem xét chẩn đoán AI sai lệch
  • Chẩn đoán bệnh lá AI & Grad-CAM                       • Đóng góp phác đồ điều trị IPM
                                    │
       ┌────────────────────────────┴───────────────────────────┐
       ▼                                                        ▼
[AI INFERENCE ROUTER]                                    [DATASET GOVERNANCE]
  • Primary: Windows Local AI Worker                       • Phiên bản hóa Dataset (V1, V2...)
  • Fallback: Cloud AI Worker (Serverless CPU/GPU)          • Tách biệt Train/Val/Test chống Leakage
  • Circuit Breaker & Retry Idempotency                    • Kiểm định phân bố lớp bệnh
```

---

## 2. NGUYÊN TẮC KIẾN TRÚC MỤC TIÊU (CORE PRINCIPLES)

1. **Độc lập Nông trại (Strict Multi-Farm Isolation):**
   - Mỗi khu vườn có ID riêng biệt (`farm_id`). Mọi truy vấn công việc, bản đồ, rủi ro và thời tiết đều bắt buộc có ràng buộc `user_id` và `farm_id`. Không dùng chung lịch hoặc trộn lẫn dữ liệu giữa hai khu vườn.
2. **Suy luận AI Thực tế (Honest AI Inference):**
   - Không giả lập kết quả chẩn đoán. Phải chạy qua mô hình kiểm tra lá (`is_leaf`) trước khi phân loại bệnh. Độ tin cậy (Confidence) phải được hiệu chuẩn thực tế.
3. **Thích ứng Thời tiết Chủ động (Weather-Adaptive Intelligence):**
   - Lịch canh tác liên tục nhận tín hiệu quan trắc và dự báo 7 ngày từ Open-Meteo theo tọa độ khu vườn để đưa ra khuyến cáo dời lịch tưới hoặc hoãn phun thuốc.
4. **Vòng lặp Cải tiến Mô hình (Continuous Feedback Loop):**
   - Phản hồi của người dùng về kết quả chẩn đoán không được tự động chuyển thành ground truth mà phải đi qua hàng đợi thẩm định của chuyên gia trong Field Lab trước khi đưa vào tập dữ liệu huấn luyện mới.
