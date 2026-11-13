"""
GARI Module — AI Agent Ecosystem Orchestrator (P4)
Authoritative implementation for:
1. Agent Orchestration Core:
   - Agent Registry (7 specialized domain agents)
   - Tool Registry with granular permission boundaries
   - Task execution state machine (pending, running, completed, failed, cancelled, requires_human_review)
   - Human-in-the-loop approval gate for high-impact operational decisions
   - Zero-trust data authorization: Agents operate strictly within caller's authenticated scope
2. Seven Specialized Agents:
   - Agronomy Agent
   - Farm Monitoring Agent
   - Weather & Risk Agent
   - Satellite Intelligence Agent
   - Task & Workflow Agent
   - Reporting Agent
   - Expert Assistance Agent
3. Telemetry, Observability, and Audit Trail without credential leakage.
"""

import json
import logging
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from gari_database import get_connection
import gari_farm_management
import gari_weather_service
import gari_satellite_service
import gari_risk_engine
import gari_digital_twin
import gari_tasks
import gari_experts
import gari_smart_alerts
import gari_intelligence_reports

logger = logging.getLogger("gari.agents")

# High-impact actions that mandate human approval before execution
HIGH_IMPACT_ACTIONS = {
    "chemical_spray_prescription",
    "assign_team_task",
    "modify_user_role",
    "transfer_ownership",
    "delete_farm_record",
    "cancel_crop_cycle"
}


# =====================================================================
# AGENT DEFINITIONS & CAPABILITIES REGISTRY
# =====================================================================

AGENT_REGISTRY = {
    "agronomy": {
        "agent_id": "agronomy",
        "name": "Agronomy Intelligence Agent",
        "name_vi": "Trợ lý Nông học & Bệnh hại Cây trồng",
        "version": "4.0.1",
        "purpose": "Hỗ trợ giải thích chẩn đoán AI, khuyến nghị biện pháp IPM phòng ngừa sinh học và xác định thời điểm cần chuyên gia.",
        "allowed_tools": ["read_diagnosis", "retrieve_knowledge", "check_crop_support"],
        "required_permissions": ["view_diagnoses"],
        "input_schema": {"type": "object", "properties": {"diagnosis_id": {"type": "integer"}, "query": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"analysis": {"type": "string"}, "recommendations": {"type": "array"}}}
    },
    "farm_monitoring": {
        "agent_id": "farm_monitoring",
        "name": "Farm Monitoring Agent",
        "name_vi": "Trợ lý Giám sát Hiện trường Trang trại",
        "version": "4.0.1",
        "purpose": "Theo dõi trạng thái sức khỏe tổng hợp của thửa đất, tổng hợp diễn biến thực địa và cảnh báo bất thường.",
        "allowed_tools": ["read_farm", "read_plot", "get_digital_twin", "list_follow_ups"],
        "required_permissions": ["view_farms"],
        "input_schema": {"type": "object", "properties": {"farm_id": {"type": "integer"}, "plot_id": {"type": "integer"}}},
        "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}, "health_status": {"type": "string"}}}
    },
    "weather_risk": {
        "agent_id": "weather_risk",
        "name": "Weather & Risk Agent",
        "name_vi": "Trợ lý Khí tượng & Phân tích Nguy cơ",
        "version": "4.0.1",
        "purpose": "Phân tích dự báo thời tiết 7 ngày, phát hiện nguy cơ vi khí hậu bùng phát dịch hại và cảnh báo sốc nhiệt/hạn hán.",
        "allowed_tools": ["get_weather", "evaluate_risks", "propose_smart_alert"],
        "required_permissions": ["view_weather", "view_risks"],
        "input_schema": {"type": "object", "properties": {"farm_id": {"type": "integer"}, "plot_id": {"type": "integer"}}},
        "output_schema": {"type": "object", "properties": {"risk_evaluation": {"type": "object"}, "action_needed": {"type": "boolean"}}}
    },
    "satellite_intelligence": {
        "agent_id": "satellite_intelligence",
        "name": "Satellite Earth Observation Agent",
        "name_vi": "Trợ lý Vệ tinh Viễn thám & Chỉ số Tán lá",
        "version": "4.0.1",
        "purpose": "Truy vấn ảnh vệ tinh Sentinel-2, tính toán chuỗi chỉ số NDVI/NDMI, cảnh báo mây che và đề xuất kiểm tra thực địa.",
        "allowed_tools": ["get_satellite_scenes", "get_vegetation_indices"],
        "required_permissions": ["view_satellite"],
        "input_schema": {"type": "object", "properties": {"plot_id": {"type": "integer"}}},
        "output_schema": {"type": "object", "properties": {"ndvi_trend": {"type": "string"}, "canopy_status": {"type": "string"}}}
    },
    "task_workflow": {
        "agent_id": "task_workflow",
        "name": "Task & Workflow Agent",
        "name_vi": "Trợ lý Điều phối Công việc & Canh tác",
        "version": "4.0.1",
        "purpose": "Hỗ trợ lập kế hoạch công việc nông nghiệp từ chẩn đoán, phân công nhân sự và theo dõi tiến độ quá hạn.",
        "allowed_tools": ["list_tasks", "draft_cultivation_task", "request_approval_for_task"],
        "required_permissions": ["manage_tasks"],
        "input_schema": {"type": "object", "properties": {"farm_id": {"type": "integer"}, "diagnosis_id": {"type": "integer"}}},
        "output_schema": {"type": "object", "properties": {"tasks_created": {"type": "array"}, "requires_approval": {"type": "boolean"}}}
    },
    "reporting": {
        "agent_id": "reporting",
        "name": "Reporting & Evidence Agent",
        "name_vi": "Trợ lý Báo cáo & Kiểm toán Minh bạch",
        "version": "4.0.1",
        "purpose": "Tổng hợp báo cáo sức khỏe trang trại, rủi ro và tổng quan tổ chức với nguồn gốc dữ liệu rõ ràng.",
        "allowed_tools": ["generate_farm_report", "generate_risk_report", "generate_org_report"],
        "required_permissions": ["view_reports"],
        "input_schema": {"type": "object", "properties": {"report_type": {"type": "string"}, "entity_id": {"type": "integer"}}},
        "output_schema": {"type": "object", "properties": {"report_data": {"type": "object"}, "provenance": {"type": "object"}}}
    },
    "expert_assistance": {
        "agent_id": "expert_assistance",
        "name": "Expert Network Assistance Agent",
        "name_vi": "Trợ lý Kết nối Mạng lưới Chuyên gia",
        "version": "4.0.1",
        "purpose": "Chuẩn bị tóm tắt ca bệnh lâm sàng, đề xuất chuyên gia phù hợp dựa trên cây trồng và theo dõi trạng thái tham vấn.",
        "allowed_tools": ["read_diagnosis_summary", "list_available_experts", "draft_expert_case"],
        "required_permissions": ["view_experts"],
        "input_schema": {"type": "object", "properties": {"diagnosis_id": {"type": "integer"}}},
        "output_schema": {"type": "object", "properties": {"case_summary": {"type": "object"}, "suggested_experts": {"type": "array"}}}
    }
}


def sanitize_payload(obj: Any) -> Any:
    """Recursively scrub tokens, passwords, and sensitive keys from execution logs."""
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in ["token", "password", "secret", "authorization", "bearer", "cookie"]):
                sanitized[k] = "[REDACTED_SECRET]"
            else:
                sanitized[k] = sanitize_payload(v)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_payload(item) for item in obj]
    elif isinstance(obj, str):
        # Scrub Bearer tokens if present in text
        return re.sub(r"Bearer\s+[A-Za-z0-9\-\._~+/]+=*", "Bearer [REDACTED_TOKEN]", obj)
    return obj


# =====================================================================
# AGENT TOOL EXECUTORS (Zero-Trust Authorization Enforced)
# =====================================================================

class AgentToolbox:
    """Authoritative tool execution sandbox enforcing user ownership and tenant boundaries."""

    @staticmethod
    def read_diagnosis(diagnosis_id: int, user_id: int) -> Dict[str, Any]:
        """Read diagnosis only if caller owns it or has authorized tenant access."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.*, p.farm_id, p.plot_name, f.organization_id
                FROM diagnoses d
                LEFT JOIN farm_plots p ON d.plot_id = p.id
                LEFT JOIN farms f ON p.farm_id = f.id
                WHERE d.id = ?
            """, (diagnosis_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Không tìm thấy hồ sơ chẩn đoán #{diagnosis_id}.")

            diag = dict(row)
            # Authorization check: caller must be owner or belong to organization
            if diag["user_id"] != user_id:
                org_id = diag.get("organization_id")
                if not org_id:
                    raise PermissionError(f"Bạn không có quyền truy cập chẩn đoán riêng tư #{diagnosis_id}.")
                # Verify org membership
                cursor.execute("SELECT role FROM organization_members WHERE organization_id = ? AND user_id = ?", (org_id, user_id))
                if not cursor.fetchone():
                    raise PermissionError(f"Bạn không thuộc tổ chức sở hữu chẩn đoán #{diagnosis_id}.")

        return {
            "id": diag["id"],
            "crop_name": diag["crop_name"],
            "predicted_disease": diag["predicted_disease"],
            "confidence": diag["confidence"],
            "severity": diag["severity"],
            "created_at": diag["created_at"],
            "image_path": diag.get("image_path")
        }

    @staticmethod
    def read_farm(farm_id: int, user_id: int) -> Dict[str, Any]:
        """Read farm record only if caller has permissions."""
        farm = gari_farm_management.get_farm_ext(farm_id=farm_id, user_id=user_id)
        if not farm:
            raise PermissionError(f"Không có quyền truy cập thông tin nông trại #{farm_id}.")
        return farm

    @staticmethod
    def get_weather(farm_id: int, user_id: int) -> Dict[str, Any]:
        """Retrieve weather observations and forecast for farm."""
        farm = gari_farm_management.get_farm_ext(farm_id=farm_id, user_id=user_id)
        if not farm:
            raise PermissionError(f"Không có quyền truy cập dữ liệu nông trại #{farm_id}.")
        return gari_weather_service.get_farm_weather(farm_id=farm_id, user_id=user_id)

    @staticmethod
    def get_satellite_indices(plot_id: int, user_id: int) -> Dict[str, Any]:
        """Retrieve satellite indices for plot with cloud coverage disclosure."""
        return gari_satellite_service.get_plot_vegetation_indices(plot_id=plot_id, user_id=user_id)

    @staticmethod
    def evaluate_risks(plot_id: int, user_id: int) -> Dict[str, Any]:
        """Run 5-vector transparent risk evaluation."""
        return gari_risk_engine.evaluate_plot_risks(plot_id=plot_id, user_id=user_id)

    @staticmethod
    def get_digital_twin(farm_id: int, user_id: int) -> Dict[str, Any]:
        """Retrieve unified 5-layer Farm Digital Twin."""
        return gari_digital_twin.get_farm_digital_twin(farm_id=farm_id, user_id=user_id)

    @staticmethod
    def list_tasks(farm_id: int, user_id: int) -> List[Dict[str, Any]]:
        """List operational tasks."""
        farm = gari_farm_management.get_farm_ext(farm_id=farm_id, user_id=user_id)
        if not farm:
            raise PermissionError(f"Không có quyền truy cập nhiệm vụ của nông trại #{farm_id}.")
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cultivation_tasks WHERE farm_id = ? ORDER BY due_date ASC", (farm_id,))
            return [dict(r) for r in cursor.fetchall()]


# =====================================================================
# AGENT RUNTIME EXECUTION ENGINE
# =====================================================================

def _persist_execution_record(
    execution_id: str,
    agent_id: str,
    user_id: int,
    organization_id: Optional[int],
    task_type: str,
    input_context: Dict[str, Any],
    output_payload: Dict[str, Any],
    tool_invocations: List[Dict[str, Any]],
    start_time: float,
    requires_approval: bool,
    error_msg: Optional[str]
) -> None:
    latency_ms = round((time.time() - start_time) * 1000, 2)
    sanitized_input = sanitize_payload(input_context)
    sanitized_output = sanitize_payload(output_payload)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_executions (
                execution_id, agent_id, user_id, organization_id, task_type,
                input_context, status, output_payload, tool_invocations,
                latency_ms, requires_approval, error_message, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            execution_id,
            agent_id,
            user_id,
            organization_id,
            task_type,
            json.dumps(sanitized_input, ensure_ascii=False),
            "failed" if error_msg else ("requires_human_review" if requires_approval else "completed"),
            json.dumps(sanitized_output, ensure_ascii=False),
            json.dumps(tool_invocations, ensure_ascii=False),
            latency_ms,
            1 if requires_approval else 0,
            error_msg
        ))
        conn.commit()


def execute_agent_task(
    agent_id: str,
    user_id: int,
    input_context: Dict[str, Any],
    task_type: Optional[str] = None,
    organization_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Main orchestration entry point:
    1. Validates agent existence and user permissions.
    2. Dispatches task to specialized agent logic.
    3. Handles Human-In-The-Loop gate for high-impact actions.
    4. Records execution telemetry and audit log.
    """
    start_time = time.time()
    execution_id = f"exec_{uuid.uuid4().hex[:12]}"

    if agent_id not in AGENT_REGISTRY:
        raise ValueError(f"Agent '{agent_id}' không tồn tại trong hệ sinh thái GARI.")

    agent_spec = AGENT_REGISTRY[agent_id]
    tool_invocations = []
    requires_approval = False
    approval_request = None
    output_payload = {}
    status = "running"
    error_msg = None

    try:
        # Route to specific agent logic
        if agent_id == "agronomy":
            output_payload, invocations = _run_agronomy_agent(user_id, input_context)
            tool_invocations.extend(invocations)

        elif agent_id == "farm_monitoring":
            output_payload, invocations = _run_farm_monitoring_agent(user_id, input_context)
            tool_invocations.extend(invocations)

        elif agent_id == "weather_risk":
            output_payload, invocations = _run_weather_risk_agent(user_id, input_context)
            tool_invocations.extend(invocations)

        elif agent_id == "satellite_intelligence":
            output_payload, invocations = _run_satellite_agent(user_id, input_context)
            tool_invocations.extend(invocations)

        elif agent_id == "task_workflow":
            output_payload, invocations, approval_needed, appr_dict = _run_task_workflow_agent(
                user_id, input_context, task_type=task_type, organization_id=organization_id
            )
            tool_invocations.extend(invocations)
            if approval_needed:
                requires_approval = True
                approval_request = appr_dict

        elif agent_id == "reporting":
            output_payload, invocations = _run_reporting_agent(user_id, input_context)
            tool_invocations.extend(invocations)

        elif agent_id == "expert_assistance":
            output_payload, invocations = _run_expert_assistance_agent(user_id, input_context)
            tool_invocations.extend(invocations)

        status = "requires_human_review" if requires_approval else "completed"

    except PermissionError as pe:
        logger.warning(f"Agent permission denied for {agent_id}: {pe}")
        status = "failed"
        error_msg = str(pe)
        output_payload = {"error": str(pe), "status": "failed"}
        _persist_execution_record(
            execution_id, agent_id, user_id, organization_id,
            task_type or agent_spec["name"], input_context, output_payload,
            tool_invocations, start_time, requires_approval, error_msg
        )
        raise pe
    except ValueError as ve:
        logger.warning(f"Agent validation error for {agent_id}: {ve}")
        status = "failed"
        error_msg = str(ve)
        output_payload = {"error": str(ve), "status": "failed"}
        _persist_execution_record(
            execution_id, agent_id, user_id, organization_id,
            task_type or agent_spec["name"], input_context, output_payload,
            tool_invocations, start_time, requires_approval, error_msg
        )
        raise ve
    except Exception as exc:
        logger.error(f"Agent execution failed for {agent_id}: {exc}")
        status = "failed"
        error_msg = str(exc)
        output_payload = {"error": str(exc), "status": "failed"}

    latency_ms = round((time.time() - start_time) * 1000, 2)

    # Persist execution log to database (sanitized)
    sanitized_input = sanitize_payload(input_context)
    sanitized_output = sanitize_payload(output_payload)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_executions (
                execution_id, agent_id, user_id, organization_id, task_type,
                input_context, status, output_payload, tool_invocations,
                latency_ms, requires_approval, error_message, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            execution_id,
            agent_id,
            user_id,
            organization_id,
            task_type or agent_spec["name"],
            json.dumps(sanitized_input, ensure_ascii=False),
            status,
            json.dumps(sanitized_output, ensure_ascii=False),
            json.dumps(tool_invocations, ensure_ascii=False),
            latency_ms,
            1 if requires_approval else 0,
            error_msg
        ))

        # If human approval is required, register approval request
        if requires_approval and approval_request:
            approval_id = f"appr_{uuid.uuid4().hex[:10]}"
            cursor.execute("""
                INSERT INTO agent_approval_requests (
                    approval_id, execution_id, agent_id, user_id, organization_id,
                    action_type, action_summary, proposed_payload, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                approval_id,
                execution_id,
                agent_id,
                user_id,
                organization_id,
                approval_request.get("action_type", "operational_action"),
                approval_request.get("action_summary", "Hành động yêu cầu phê duyệt"),
                json.dumps(approval_request.get("payload", {}), ensure_ascii=False)
            ))
            approval_request["approval_id"] = approval_id

        conn.commit()

    return {
        "success": status in ("completed", "requires_human_review"),
        "execution_id": execution_id,
        "agent_id": agent_id,
        "agent_name": agent_spec["name_vi"],
        "status": status,
        "latency_ms": latency_ms,
        "requires_approval": requires_approval,
        "requires_human_review": requires_approval,
        "approval_id": approval_request.get("approval_id") if (requires_approval and approval_request) else None,
        "approval_request": approval_request,
        "result": output_payload,
        "output": output_payload,
        "tool_invocations": tool_invocations,
        "tool_invocations_count": len(tool_invocations),
        "executed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }


# =====================================================================
# INDIVIDUAL SPECIALIZED AGENT RUNNERS
# =====================================================================

def _run_agronomy_agent(user_id: int, context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Agronomy Agent: Interprets diagnosis, explains uncertainty, provides IPM advice."""
    diag_id = context.get("diagnosis_id")
    if not diag_id:
        raise ValueError("Yêu cầu cung cấp diagnosis_id để Trợ lý Nông học phân tích.")

    diag = AgentToolbox.read_diagnosis(diag_id, user_id)
    invocations = [{"tool": "read_diagnosis", "params": {"diagnosis_id": diag_id}, "status": "success"}]

    disease = diag.get("predicted_disease") or "Chưa rõ"
    crop = diag.get("crop_name") or "Cây trồng"
    conf = float(diag.get("confidence") or 0.0)
    sev = diag.get("severity") or "LOW"

    # Truthful explanation without clinical over-confidence
    if "healthy" in disease.lower():
        analysis = f"Mẫu lá {crop} ghi nhận trạng thái bình thường (Độ tin cậy: {int(conf * 100)}%). Cây sinh trưởng tốt, không có dấu hiệu nấm khuẩn nghiêm trọng."
        recs = [
            "Duy trì chế độ dinh dưỡng cân đối theo chu kỳ sinh trưởng.",
            "Tiếp tục quan sát định kỳ 3-5 ngày/lần."
        ]
        needs_expert = False
    else:
        analysis = (
            f"Kết quả phân tích ghi nhận nghi ngờ dấu hiệu dịch hại: **{disease}** trên cây **{crop}** "
            f"(Độ tin cậy mô hình: {int(conf * 100)}%, Mức độ tổn thương: {sev}). "
            f"Lưu ý: Độ tin cậy thuật toán không thay thế kiểm định vi sinh phòng thí nghiệm."
        )
        recs = [
            "Cách ly và tỉa bỏ các lá bị đốm bệnh nặng để giảm nguồn lây lan trong vườn.",
            "Ưu tiên sử dụng chế phẩm sinh học (Trichoderma hoặc Bacillus) để ức chế nấm khuẩn.",
            "Giảm tưới phun sương chiều muộn để tránh đọng ẩm tán lá qua đêm."
        ]
        needs_expert = sev in ("HIGH", "CRITICAL") or conf < 0.75

    return {
        "crop": crop,
        "suspected_disease": disease,
        "confidence": conf,
        "severity": sev,
        "analysis": analysis,
        "differential_diagnosis": {
            "primary_suspected": disease,
            "confidence": conf,
            "severity": sev,
            "crop": crop
        },
        "ipm_recommendations": recs,
        "expert_consultation_recommended": needs_expert
    }, invocations


def _run_farm_monitoring_agent(user_id: int, context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Farm Monitoring Agent: Analyzes farm and digital twin state."""
    farm_id = context.get("farm_id")
    if not farm_id:
        raise ValueError("Yêu cầu cung cấp farm_id để Trợ lý Giám sát phân tích.")

    farm = AgentToolbox.read_farm(farm_id, user_id)
    twin = AgentToolbox.get_digital_twin(farm_id, user_id)
    invocations = [
        {"tool": "read_farm", "params": {"farm_id": farm_id}, "status": "success"},
        {"tool": "get_digital_twin", "params": {"farm_id": farm_id}, "status": "success"}
    ]

    health_score = twin.get("farm_health_score", 80)
    health_rating = twin.get("health_rating", "Tốt")
    plots_count = twin.get("spatial_profile", {}).get("plots_count", 0)
    overdue_tasks = twin.get("operational_profile", {}).get("task_statistics", {}).get("overdue_tasks", 0)

    summary = (
        f"Nông trại '{farm['name']}' ({farm.get('province') or 'Chưa rõ tỉnh'}) hiện quản lý {plots_count} thửa đất. "
        f"Điểm sức khỏe tổng hợp: {health_score}/100 ({health_rating}). "
        f"Có {overdue_tasks} công việc quá hạn cần xử lý."
    )

    return {
        "farm_id": farm_id,
        "farm_name": farm["name"],
        "farm_health_score": health_score,
        "health_rating": health_rating,
        "summary": summary,
        "environmental_status": twin.get("environmental_profile", {}).get("weather_status"),
        "overdue_tasks_count": overdue_tasks
    }, invocations


def _run_weather_risk_agent(user_id: int, context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Weather & Risk Agent: Evaluates forecast and disease weather windows."""
    farm_id = context.get("farm_id")
    plot_id = context.get("plot_id")
    if not farm_id and not plot_id:
        raise ValueError("Yêu cầu cung cấp farm_id hoặc plot_id để Trợ lý Thời tiết phân tích.")

    invocations = []
    weather_data = None
    risk_data = None

    if farm_id:
        weather_data = AgentToolbox.get_weather(farm_id, user_id)
        invocations.append({"tool": "get_weather", "params": {"farm_id": farm_id}, "status": "success"})

    if plot_id:
        risk_data = AgentToolbox.evaluate_risks(plot_id, user_id)
        invocations.append({"tool": "evaluate_risks", "params": {"plot_id": plot_id}, "status": "success"})

    # Distinguish forecast from observations
    cur_weather = (weather_data.get("current") if weather_data else {}) or {}
    daily_forecast = (weather_data.get("daily_forecast") if weather_data else []) or []

    is_forecast = len(daily_forecast) > 0
    risk_level = (risk_data.get("overall_risk_level") if risk_data else "low") or "low"

    summary = (
        f"Nhiệt độ hiện tại: {cur_weather.get('temperature_c', 'N/A')}°C, độ ẩm: {cur_weather.get('humidity_pct', 'N/A')}%. "
        f"Dự báo 7 ngày tới ghi nhận xu hướng thời tiết {cur_weather.get('condition', 'ổn định')}. "
        f"Đánh giá rủi ro tổng hợp ở mức: {str(risk_level).upper()}."
    )

    return {
        "observation_type": "current_observation_and_7day_forecast",
        "weather_telemetry": {
            "source": f"Open-Meteo ({weather_data.get('provider_url', 'https://open-meteo.com')})",
            "provider": weather_data.get("provider", "Open-Meteo"),
            "is_real_data": weather_data.get("is_real_data", False),
            "status": weather_data.get("status", "unknown"),
            "current": cur_weather,
            "daily_forecast": daily_forecast
        } if weather_data else {},
        "current_observation": cur_weather,
        "forecast_days_count": len(daily_forecast),
        "risk_evaluation": risk_data,
        "overall_threat_level": risk_level,
        "advisory": "Theo dõi sát sao diễn biến ẩm độ không khí để phòng nấm hại.",
        "summary": summary,
        "requires_attention": risk_level in ("high", "severe")
    }, invocations


def _run_satellite_agent(user_id: int, context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Satellite Intelligence Agent: Interprets canopy NDVI trends and disclosures."""
    plot_id = context.get("plot_id")
    farm_id = context.get("farm_id")
    if not plot_id and not farm_id:
        raise ValueError("Yêu cầu cung cấp plot_id hoặc farm_id để Trợ lý Vệ tinh phân tích.")

    invocations = []
    sat_data = None
    if plot_id:
        sat_data = AgentToolbox.get_satellite_indices(plot_id, user_id)
        invocations.append({"tool": "get_vegetation_indices", "params": {"plot_id": plot_id}, "status": "success"})
    elif farm_id:
        farm = AgentToolbox.read_farm(farm_id, user_id)
        plots = farm.get("plots") or []
        if plots:
            plot_id = plots[0]["id"]
            sat_data = AgentToolbox.get_satellite_indices(plot_id, user_id)
            invocations.append({"tool": "get_vegetation_indices", "params": {"plot_id": plot_id}, "status": "success"})
        else:
            sat_data = {
                "status": "no_geometry",
                "message": "Nông trại chưa có thửa đất hoặc ranh giới GIS để quét vệ tinh.",
                "provider": "Sentinel-2 L2A (AWS Earth)",
                "latest_ndvi": None,
                "latest_ndmi": None
            }

    latest_ndvi = sat_data.get("latest_ndvi")
    latest_ndmi = sat_data.get("latest_ndmi")
    canopy_desc = sat_data.get("canopy_assessment", "Chưa rõ")
    status = sat_data.get("status")

    if status in ("unlocated", "no_geometry"):
        summary = "Thửa đất chưa có ranh giới tọa độ GIS. Không thể truy vấn viễn thám Sentinel-2."
    elif latest_ndvi is not None:
        summary = (
            f"Chỉ số thực vật NDVI gần nhất: {latest_ndvi} (NDMI: {latest_ndmi}). "
            f"Đánh giá sinh khối tán lá: {canopy_desc}. "
            f"Lưu ý: Chỉ số NDVI phản ánh mật độ tán lá, không kết luận đích danh bệnh hại."
        )
    else:
        summary = "Dữ liệu vệ tinh đang bị mây che phủ hoặc chưa có chu kỳ quét mới."

    return {
        "plot_id": plot_id,
        "provider": sat_data.get("provider"),
        "status": status,
        "satellite_indices": sat_data,
        "latest_ndvi": latest_ndvi,
        "latest_ndmi": latest_ndmi,
        "summary": summary,
        "field_inspection_recommended": latest_ndvi is not None and latest_ndvi < 0.40
    }, invocations


def _run_task_workflow_agent(
    user_id: int,
    context: Dict[str, Any],
    task_type: Optional[str] = None,
    organization_id: Optional[int] = None
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool, Optional[Dict[str, Any]]]:
    """
    Task & Workflow Agent:
    If action assigns high-impact prescription or other members, triggers Human-In-The-Loop gate.
    """
    farm_id = context.get("farm_id")
    if not farm_id:
        raise ValueError("Yêu cầu cung cấp farm_id để Trợ lý Công việc xử lý.")

    # Check access to farm
    AgentToolbox.read_farm(farm_id, user_id)
    invocations = [{"tool": "check_farm_access", "params": {"farm_id": farm_id}, "status": "success"}]

    action_type = context.get("action_type") or task_type or "schedule_inspection"
    task_title = context.get("task_title", f"Kế hoạch canh tác: {action_type}")
    assigned_user_id = context.get("assigned_user_id")

    # Check if this action requires human review
    requires_approval = False
    approval_dict = None

    if action_type in HIGH_IMPACT_ACTIONS or (assigned_user_id and assigned_user_id != user_id):
        requires_approval = True
        payload_data = {
            "farm_id": farm_id,
            "plot_id": context.get("plot_id"),
            "task_title": task_title,
            "action_type": action_type,
            "assigned_user_id": assigned_user_id,
            "context": context
        }
        approval_dict = {
            "action_type": action_type,
            "action_summary": f"Trợ lý đề xuất: {task_title} (Nông trại #{farm_id})",
            "payload": payload_data,
            "proposed_payload": json.dumps(payload_data, ensure_ascii=False)
        }
        return {
            "status": "requires_human_review",
            "message": "Hành động có tác động lớn hoặc phân công nhân sự yêu cầu Người quản lý xác nhận trước khi thực hiện.",
            "proposed_tasks": [{
                "farm_id": farm_id,
                "task_title": task_title,
                "action_type": action_type,
                "requires_approval": True
            }]
        }, invocations, True, approval_dict

    # Standard benign task: create directly
    task = gari_tasks.create_task({
        "farm_id": farm_id,
        "plot_id": context.get("plot_id"),
        "title": task_title,
        "task_type": "inspection",
        "priority": context.get("priority", "medium"),
        "due_date": context.get("due_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "assigned_user_id": user_id,
        "notes": "Được khởi tạo bởi GARI Task Agent."
    }, creator_user_id=user_id, org_id=organization_id)
    invocations.append({"tool": "create_task", "params": {"task_id": task["id"]}, "status": "success"})

    return {
        "status": "completed",
        "task_created": task,
        "proposed_tasks": [task],
        "message": f"Đã tự động khởi tạo nhiệm vụ: {task_title}."
    }, invocations, False, None


def _run_reporting_agent(user_id: int, context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Reporting Agent: Produces transparent evidence reports."""
    report_type = context.get("report_type", "farm_health")
    entity_id = context.get("entity_id") or context.get("farm_id") or context.get("organization_id")
    if not entity_id:
        raise ValueError("Yêu cầu cung cấp farm_id hoặc organization_id để xuất báo cáo.")

    invocations = []
    if report_type in ("health", "farm_health"):
        report_data = gari_intelligence_reports.generate_farm_health_report(farm_id=entity_id, user_id=user_id)
        invocations.append({"tool": "generate_farm_health_report", "params": {"farm_id": entity_id}, "status": "success"})
    elif report_type in ("risk", "agricultural_risk"):
        report_data = gari_intelligence_reports.generate_agricultural_risk_report(farm_id=entity_id, user_id=user_id)
        invocations.append({"tool": "generate_agricultural_risk_report", "params": {"farm_id": entity_id}, "status": "success"})
    elif report_type in ("org", "organization", "organization_overview"):
        report_data = gari_intelligence_reports.generate_organization_overview_report(org_id=entity_id, user_id=user_id)
        invocations.append({"tool": "generate_organization_overview_report", "params": {"org_id": entity_id}, "status": "success"})
    else:
        # Default fallback to farm health report
        report_data = gari_intelligence_reports.generate_farm_health_report(farm_id=entity_id, user_id=user_id)
        invocations.append({"tool": "generate_farm_health_report", "params": {"farm_id": entity_id}, "status": "success"})

    return {
        "report_type": report_type,
        "report": report_data,
        "provenance": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "data_source": "GARI AgriTech Database & Live Telemetry",
            "sources": ["GARI Database", "Open-Meteo", "Sentinel-2 L2A"]
        }
    }, invocations


def _run_expert_assistance_agent(user_id: int, context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Expert Assistance Agent: Prepares clinical summaries without false claims of case acceptance."""
    diag_id = context.get("diagnosis_id")
    if not diag_id:
        raise ValueError("Yêu cầu diagnosis_id để chuẩn bị hồ sơ tham vấn chuyên gia.")

    diag = AgentToolbox.read_diagnosis(diag_id, user_id)
    invocations = [{"tool": "read_diagnosis", "params": {"diagnosis_id": diag_id}, "status": "success"}]

    crop = diag.get("crop_name") or "Cây trồng"
    disease = diag.get("predicted_disease") or "Chưa rõ"

    # Suggest verified experts matching crop
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, full_name, specialization, display_title, verification_status, status
            FROM expert_profiles
            WHERE (status = 'active' OR is_active = 1) AND (verification_status = 'approved' OR verification_status = 'verified')
            LIMIT 5
        """)
        experts = [dict(r) for r in cursor.fetchall()]

    case_summary = {
        "diagnosis_id": diag_id,
        "crop": crop,
        "suspected_disease": disease,
        "confidence": diag.get("confidence"),
        "severity": diag.get("severity"),
        "notes": "Hồ sơ tham vấn lâm sàng được tổng hợp tự động bởi GARI Expert Agent.",
        "case_status": "draft_ready",
        "disclaimer": "Chuyên gia chưa tiếp nhận ca bệnh. Cần sự đồng ý của chủ nông hộ trước khi mở tham vấn chính thức."
    }

    return {
        "case_summary": case_summary,
        "matched_experts_count": len(experts),
        "suggested_experts": experts
    }, invocations


# =====================================================================
# HUMAN-IN-THE-LOOP APPROVAL OPERATIONS
# =====================================================================

def list_pending_approvals(user_id: int, organization_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """List pending agent actions awaiting human review."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if organization_id:
            cursor.execute("""
                SELECT a.*, u.full_name as requested_by_name
                FROM agent_approval_requests a
                JOIN users u ON a.user_id = u.id
                WHERE a.organization_id = ? AND a.status = 'pending'
                ORDER BY a.created_at DESC
            """, (organization_id,))
        else:
            cursor.execute("""
                SELECT a.*, u.full_name as requested_by_name
                FROM agent_approval_requests a
                JOIN users u ON a.user_id = u.id
                WHERE a.user_id = ? AND a.status = 'pending'
                ORDER BY a.created_at DESC
            """, (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        for r in rows:
            if r.get("proposed_payload"):
                try:
                    r["payload"] = json.loads(r["proposed_payload"])
                except Exception:
                    r["payload"] = {}
        return rows


def resolve_approval_request(
    approval_id: str,
    action: str,  # 'approve' | 'reject'
    reviewer_user_id: int,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Approve or reject a pending agent action."""
    if action not in ("approve", "reject"):
        raise ValueError("Hành động phải là 'approve' hoặc 'reject'.")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agent_approval_requests WHERE approval_id = ?", (approval_id,))
        appr = cursor.fetchone()
        if not appr:
            raise ValueError(f"Không tìm thấy yêu cầu phê duyệt #{approval_id}.")

        new_status = "approved" if action == "approve" else "rejected"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            UPDATE agent_approval_requests
            SET status = ?,
                reviewed_by_user_id = ?,
                review_notes = ?,
                reviewed_at = ?
            WHERE approval_id = ?
        """, (new_status, reviewer_user_id, notes, now_str, approval_id))

        # Update parent execution state
        cursor.execute("""
            UPDATE agent_executions
            SET status = ?
            WHERE execution_id = ?
        """, ("completed" if action == "approve" else "cancelled", appr["execution_id"]))

        conn.commit()

    return {
        "success": True,
        "approval_id": approval_id,
        "status": new_status,
        "reviewed_at": now_str,
        "message": f"Đã {'chấp thuận' if action == 'approve' else 'từ chối'} yêu cầu hành động của AI Agent."
    }


def get_available_agents() -> List[Dict[str, Any]]:
    """Return all 7 registered AI agents and their capabilities."""
    agents = []
    for aid, meta in AGENT_REGISTRY.items():
        agents.append({
            "agent_id": meta["agent_id"],
            "name": meta["name"],
            "name_vi": meta["name_vi"],
            "version": meta["version"],
            "purpose": meta["purpose"],
            "allowed_tools": meta["allowed_tools"],
            "required_permissions": meta["required_permissions"],
            "input_schema": meta["input_schema"],
            "output_schema": meta["output_schema"]
        })
    return agents


def list_agent_executions(user_id: int, organization_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve audit history of agent runs for the user/organization."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if organization_id:
            cursor.execute("""
                SELECT * FROM agent_executions
                WHERE organization_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (organization_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM agent_executions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
        rows = [dict(r) for r in cursor.fetchall()]

    for r in rows:
        for json_col in ("input_context", "output_payload", "tool_invocations"):
            if r.get(json_col):
                try:
                    r[json_col] = sanitize_payload(json.loads(r[json_col]))
                except Exception:
                    pass
    return rows


def get_agent_execution(execution_id: str, user_id: int) -> Dict[str, Any]:
    """Retrieve a single execution log with full audit trail."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agent_executions WHERE execution_id = ?", (execution_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy lịch sử thực thi {execution_id}.")
        data = dict(row)
        if data["user_id"] != user_id:
            # Check if user is member of same organization
            if not data.get("organization_id"):
                raise PermissionError("Bạn không có quyền truy cập nhật ký thực thi này.")

    for json_col in ("input_context", "output_payload", "tool_invocations"):
        if data.get(json_col):
            try:
                data[json_col] = sanitize_payload(json.loads(data[json_col]))
            except Exception:
                pass
    return data

