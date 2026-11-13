# GARI 2.0 — Hệ Thống Thiết Kế Giao Diện (Design System & Tokens)

Hệ thống thiết kế giao diện chuẩn mực cho GARI AgriTech 2.0, được xây dựng dựa trên nguyên lý thiết kế nông nghiệp công nghệ cao hiện đại, tối ưu cho cả giao diện máy tính để bàn (Desktop 1440px) và thiết bị hiện trường di động (Mobile 390px).

---

## 1. Định Vị Nghệ Thuật & Bản Sắc Thương Hiệu (Art Direction)

- **Phong cách:** Công nghệ Nông nghiệp Chuyên sâu (Scientific Agricultural Intelligence).
- **Cảm giác chủ đạo:** Đáng tin cậy, khoa học, điềm tĩnh và hiệu quả.
- **Tránh xa:** Hiệu ứng gradient màu mè lạm dụng của các mẫu AI generic, các góc bo tròn quá mức (border-radius > 24px trên thẻ dữ liệu), các khối icon trang trí vô nghĩa không có giá trị thông tin.
- **Hình ảnh:** Hình ảnh nông nghiệp và bệnh học thực vật chân thực, có kiểm chứng bản quyền và xuất xứ rõ ràng.

---

## 2. Bảng Màu & Mã Định Danh Ngữ Nghĩa (Design Tokens)

### 2.1. Màu Thương Hiệu & Trạng Thái
| Tên Token | Mã Màu Hex | Ứng Dụng |
|---|---|---|
| `--primary` | `#10b981` (Emerald 500) | Nút hành động chính, viền tiêu điểm, thanh tiến trình |
| `--primary-hover` | `#059669` (Emerald 600) | Trạng thái rê chuột của nút chính |
| `--primary-subtle` | `rgba(16, 185, 129, 0.1)` | Nền thẻ nổi bật, huy hiệu trạng thái xanh |
| `--accent-sky` | `#0284c7` (Sky 600) | Thẻ báo cáo phụ, liên kết tài liệu hướng dẫn |
| `--warning` | `#f59e0b` (Amber 500) | Cảnh báo cần lưu ý, bệnh lý mức độ trung bình |
| `--danger` | `#ef4444` (Red 500) | Báo động đỏ, cảnh báo dịch hại, kiểm định lá thất bại |
| `--healthy` | `#22c55e` (Green 500) | Cây trồng khỏe mạnh, không phát hiện mầm bệnh |

### 2.2. Màu Nền & Bề Mặt (Surface Tokens)
| Tên Token | Chế độ Sáng (Light Mode) | Chế độ Tối (Dark Mode) |
|---|---|---|
| `--background` | `#f8fafc` (Slate 50) | `#090d16` (Deep Navy) |
| `--surface` | `#ffffff` (Pure White) | `#111827` (Slate 900) |
| `--surface-muted` | `#f1f5f9` (Slate 100) | `#1e293b` (Slate 800) |
| `--border` | `#e2e8f0` (Slate 200) | `#334155` (Slate 700) |
| `--text-main` | `#0f172a` (Slate 900) | `#f8fafc` (Slate 50) |
| `--text-secondary`| `#475569` (Slate 600) | `#94a3b8` (Slate 400) |
| `--text-muted` | `#94a3b8` (Slate 400) | `#64748b` (Slate 500) |

---

## 3. Hệ Thống Kiểu Chữ (Typography Scale)

Sử dụng bộ font không chân hiện đại, tối ưu hóa khả năng đọc tiếng Việt có dấu:
`font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;`

| Cấp Bậc | Kích Thước | Độ Đậm (Weight) | Khoảng Cách Dòng (Line Height) |
|---|---|---|---|
| **Display H1** | 26px - 32px | 800 (Bold) | 1.25 |
| **Heading H2** | 20px - 22px | 700 (SemiBold)| 1.35 |
| **Heading H3** | 16px - 18px | 600 | 1.4 |
| **Body Regular** | 14px | 400 | 1.6 |
| **Body Small** | 12.5px - 13px | 400 / 500 | 1.5 |
| **Caption / Pill**| 11px - 11.5px | 700 (Uppercase)| 1.2 |

---

## 4. Thành Phần Giao Diện Chuẩn (Components)

### 4.1. Huy Hiệu Trạng Thái (Pill Badges)
- `.pill-success`: Nền xanh lá nhạt, chữ xanh lá đậm.
- `.pill-warning`: Nền vàng nhạt, chữ nâu vàng.
- `.pill-danger`: Nền đỏ nhạt, chữ đỏ sẫm.
- `.pill-neutral`: Nền xám nhạt, viền trung tính.

### 4.2. Nút Bấm (Buttons)
- `.btn-primary`: Nền `--primary`, chữ trắng, bo góc 8px, hiệu ứng đổ bóng tinh tế.
- `.btn-secondary`: Nền trong suốt hoặc `--surface-muted`, viền mảnh `--border`.
- `.btn-danger`: Nền đỏ, dùng cho hành động nhạy cảm như đình chỉ tài khoản hoặc hủy gói cước.

### 4.3. Thẻ Dữ Liệu (Cards)
- Bo góc cố định: `border-radius: 12px;`
- Viền mỏng sắc nét: `1px solid var(--border);`
- Đổ bóng nhẹ: `box-shadow: 0 1px 3px rgba(0,0,0,0.05);`

### 4.4. Bộ Chọn Ngữ Cảnh Nông Trại (Context Selector)
- Tích hợp tại thanh công cụ làm việc của trang chẩn đoán.
- Phân nhóm rõ ràng giữa:
  - 🏡 **Trang trại độc lập cá nhân**
  - 🏢 **Hợp tác xã & Khối liên kết**
- Tự động co giãn khi chuyển giữa màn hình Desktop và Mobile.
