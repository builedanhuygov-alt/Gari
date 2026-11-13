# BÁO CÁO TRIỂN KHAI HỆ SINH THÁI AI AGENTS — GARI P4
## GARI AgriTech AI Lab — Autonomous Multi-Agent Agricultural Intelligence Platform

- **Chủ trì kỹ thuật:** Ban Kiến trúc Sáng tạo AI & Trí tuệ Tự hành GARI
- **Thời điểm nghiệm thu:** 10/11/2026
- **Trạng thái thực thi:** `COMPLETED AND TESTED`
- **Kết quả kiểm thử tự động:** **12/12 Test Scenarios Passed (100%)**
- **Điểm truy cập giao diện:** `https://gari-team.vercel.app/frontend2/agents.html`
- **Tập tin lõi:** `gari_agent_orchestrator.py`, `tests/test_p4_agent_ecosystem.py`, `frontend2/agents.html`

---

## 1. TỔNG QUAN HỆ SINH THÁI AI AGENTS (ARCHITECTURE OVERVIEW)

Giai đoạn P4 nâng cấp GARI từ một công cụ nhận diện bệnh lá đơn thuần thành một **Hệ sinh thái Đa Trợ lý Nông nghiệp Tự hành (Autonomous Multi-Agent System)**. Hệ thống bao gồm 3 trụ cột kỹ thuật:

```
+---------------------------------------------------------------------------------------------------------+
|                                    GARI P4 AGENT ORCHESTRATION ARCHITECTURE                             |
+---------------------------------------------------------------------------------------------------------+
|  [Frontend2 SaaS Shell: agents.html]                                                                    |
|    |-- Bảng điều khiển 7 Trợ lý chuyên trách (Interactive Console)                                     |
|    |-- Cổng phê duyệt con người (Human-in-the-Loop Approval Modal)                                      |
|    \-- Nhật ký kiểm toán minh bạch khử mã bí mật (Sanitized Telemetry Audit)                            |
+---------------------------------------------------------------------------------------------------------+
                                                     |
                                                     v (Scoped JWT Auth)
+---------------------------------------------------------------------------------------------------------+
|  [Agent Orchestrator Core: gari_agent_orchestrator.py]                                                  |
|    |-- Agent Registry (Quản lý 7 Agent: metadata, schemas, permissions)                                |
|    |-- Tool Registry & Zero-Trust Sandbox (Chặn đứng mọi truy cập chéo tenant)                          |
|    |-- State Machine: [pending] -> [running] -> [completed / requires_human_review / failed]            |
|    \-- Secret Sanitizer (Khử đệ quy token, password, secret trước khi lưu DB)                           |
+---------------------------------------------------------------------------------------------------------+
                                                     |
         +-------------------+-----------------------+-----------------------+-------------------+
         |                   |                       |                       |                   |
         v                   v                       v                       v                   v
   [1. Agronomy]     [2. Monitoring]         [3. Weather/Risk]      [4. Satellite]      [5. Task/Workflow]
   (Chẩn đoán lá)   (Digital Twin 5 tầng)   (Open-Meteo & Rủi ro)  (Sentinel-2 NDVI)  (Phê duyệt thuốc BVTV)
         |                   |
         +---------+---------+
                   |
         +---------+---------+
         |                   |
         v                   v
   [6. Reporting]     [7. Expert Assistance]
   (Kiểm toán xuất)   (Kết nối mạng lưới chuyên gia)
+---------------------------------------------------------------------------------------------------------+
|  [Persistence & Audit Layer]                                                                            |
|    |-- agent_executions: Lưu toàn bộ lịch sử chạy, latency_ms, tool calls                              |
|    \-- agent_approval_requests: Hàng đợi phê duyệt cho người quản lý trang trại / hợp tác xã            |
+---------------------------------------------------------------------------------------------------------+
```

---

## 2. CHI TIẾT 7 TRỢ LÝ AI CHUYÊN TRÁCH (7 SPECIALIZED AGENTS)

| Agent ID | Tên Trợ lý Tiếng Việt | Phiên bản | Công cụ cho phép (Allowed Tools) | Cơ chế kiểm soát an toàn |
|---|---|---|---|---|
| `agronomy` | **Trợ lý Nông học & Lâm sàng** | v4.0.1 | `read_diagnosis`, `retrieve_knowledge`, `check_crop_support` | Chỉ đọc chẩn đoán thuộc sở hữu người dùng; giải thích kèm mức tin cậy |
| `farm_monitoring` | **Trợ lý Giám sát Nông trại & Digital Twin** | v4.0.1 | `read_farm`, `get_digital_twin`, `list_smart_alerts` | Kiểm tra quyền thành viên nông trại; tổng hợp 5 tầng dữ liệu |
| `weather_risk` | **Trợ lý Dự báo & Cửa sổ Thời tiết** | v4.0.1 | `get_weather`, `evaluate_risks` | Phân biệt minh bạch giữa quan trắc Open-Meteo và dự báo 7 ngày |
| `satellite_intelligence` | **Trợ lý Viễn thám & Tán lá Vệ tinh** | v4.0.1 | `get_satellite_indices` | Công khai trạng thái che phủ mây; báo cáo trung thực nếu chưa có tọa độ |
| `task_workflow` | **Trợ lý Điều phối Canh tác & Giao việc** | v4.0.1 | `list_tasks`, `create_task`, `request_approval` | **Bắt buộc Human-in-the-Loop** khi kê đơn thuốc BVTV hoặc giao việc |
| `reporting` | **Trợ lý Báo cáo & Kiểm toán Toàn vẹn** | v4.0.1 | `generate_farm_report`, `generate_risk_report` | Cung cấp đầy đủ provenance nguồn dữ liệu và dấu thời gian UTC |
| `expert_assistance` | **Trợ lý Kết nối Mạng lưới Chuyên gia** | v4.0.1 | `read_diagnosis_summary`, `list_experts` | Bắt buộc đính kèm disclaimer: *Chuyên gia chưa tiếp nhận ca bệnh* |

---

## 3. CƠ CHẾ BẢO MẬT & KIỂM SOÁT CON NGƯỜI (HUMAN-IN-THE-LOOP & ZERO-TRUST)

### 3.1. Cổng Phê duyệt Con người (Human-in-the-Loop Gate)
Các hành động vận hành nhạy cảm sau đây **tuyệt đối không được phép tự hành**:
1. Kê đơn phun thuốc bảo vệ thực vật hóa học (`chemical_spray_prescription`).
2. Phân công nhiệm vụ cho nhân sự khác trong tổ chức (`assign_team_task`).
3. Chỉnh sửa vai trò và phân quyền thành viên (`modify_user_role`).
4. Chuyển giao quyền sở hữu tài sản nông trại (`transfer_ownership`).
5. Xóa bỏ hồ sơ dữ liệu nông trại (`delete_farm_record`).

Khi kích hoạt, Agent tự động:
- Chuyển trạng thái sang `requires_human_review`.
- Lưu một bản ghi vào bảng `agent_approval_requests` kèm chi tiết đề xuất.
- Đợi người quản trị đăng nhập vào `frontend2/agents.html` bấm **"Chấp thuận" (Approve)** hoặc **"Từ chối" (Reject)** kèm ghi chú xác nhận.

### 3.2. Cô lập Dữ liệu Tuyệt đối (Zero-Trust Caller Scoping)
- Mỗi công cụ trong `AgentToolbox` đều yêu cầu `user_id` của phiên gọi.
- Người dùng B không thể yêu cầu Agent đọc hồ sơ bệnh, thời tiết nội bộ, hay dữ liệu nông trại của Người dùng A. Mọi vi phạm đều bị chặn ngay lập tức tại tầng Python với ngoại lệ `PermissionError` (HTTP 403 Forbidden).

### 3.3. Khử Mã Bí mật Trong Nhật ký (Telemetry Secret Scrubbing)
Hàm `sanitize_payload()` quét đệ quy mọi đối tượng JSON trước khi lưu vào bảng `agent_executions`. Toàn bộ các trường nhạy cảm chứa các từ khóa (`token`, `password`, `secret`, `authorization`, `bearer`, `cookie`) đều được thay thế tự động bằng giá trị danh định `[REDACTED_SECRET]`.

---

## 4. KẾT QUẢ KIỂM THỬ TỰ ĐỘNG HÓA P4 (`test_p4_agent_ecosystem.py`)

Bộ kiểm thử gồm 12 kịch bản khắt khe đã được thực thi và vượt qua 100%:

```
======================================================================
 GARI PHASE P4 — AUTOMATED AGENT ECOSYSTEM VERIFICATION
======================================================================
[PASS] 01. Agent Registry Discovery: 7 specialized agents discovered with schemas.
[PASS] 02. Own Diagnosis Access: Agronomy agent correlates user's own diagnosis.
[PASS] 03. Other User Diagnosis Blocked: Zero-trust blocks Tenant B (HTTP 403).
[PASS] 04. Farm Access Boundary: Farm Monitoring enforces ownership perimeter (HTTP 403).
[PASS] 05. Weather Forecast Provenance: Distinguishes Open-Meteo observations vs forecast.
[PASS] 06. Satellite Cloudy Masking: Honest disclosure of no-geometry or cloud-mask.
[PASS] 07. Transparent Risk Explanation: 5-vector breakdown without black-box scores.
[PASS] 08. Task Assignment & Permissions: Task & Workflow generates actionable plan.
[PASS] 09. Report Provenance: Reporting agent details exact data lineage and timestamp.
[PASS] 10. Expert Matching Disclaimer: Enforces unconfirmed consultation disclaimer.
[PASS] 11. Human Approval Gate: High-impact actions pause for human review and resolve.
[PASS] 12. Telemetry Secret Scrubbing: Redacts JWT/passwords in DB logs; safe error recovery.
----------------------------------------------------------------------
Ran 12 tests in 2.121s -> ALL 12 TESTS PASSED (100% OK)
======================================================================
```

---

## 5. TRẢI NGHIỆM GIAO DIỆN NGƯỜI DÙNG FRONTEND2

- **Trang điều khiển:** `frontend2/agents.html` đã được xây dựng và tích hợp hoàn chỉnh vào SaaS Shell.
- **Thanh menu điều hướng:** Mục *"Trợ lý AI Nông nghiệp"* được thêm vào thanh sidebar của toàn bộ người dùng nông hộ và doanh nghiệp.
- **Thành phần giao diện nổi bật:**
  - Lưới chọn 7 thẻ Trợ lý AI kèm danh mục công cụ cho phép.
  - Form nhập tham số động (Dynamic Context Inputs) phù hợp theo schema của từng Agent.
  - Bảng cảnh báo nổi bật khi có yêu cầu phê duyệt con người đang chờ xử lý (Human-in-the-Loop Queue).
  - Khung hiển thị bằng chứng nguồn gốc dữ liệu (Provenance) và nhật ký gọi công cụ (Tool Calls Audit).

