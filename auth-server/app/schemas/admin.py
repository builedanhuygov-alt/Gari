"""
GARI Auth Server 1.0 — Administrative Schemas
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from datetime import datetime
from typing import List, Optional
from app.schemas.auth import UserResponse


class AdminBootstrapRequest(BaseModel):
    bootstrap_token: str = Field(..., min_length=16, description="One-time secret token configured on server")
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=100)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class AdminUpdateStatusRequest(BaseModel):
    is_active: bool


class AdminUpdateRoleRequest(BaseModel):
    account_type: str = Field(..., description="Allowed: farmer, expert, enterprise, admin")

    @field_validator("account_type")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"farmer", "expert", "enterprise", "admin"}
        clean = v.strip().lower()
        if clean not in allowed:
            raise ValueError(f"Vai trò không hợp lệ. Cho phép: {', '.join(allowed)}")
        return clean


class AdminUserDetailResponse(UserResponse):
    active_sessions_count: int = 0


class AdminUserListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    users: List[UserResponse]


class SecurityEventResponse(BaseModel):
    id: int
    event_type: str
    user_id: Optional[int]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    sanitized_metadata: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    registered_farmers: int
    capacity_limit: int
    capacity_remaining: int
    registration_open: bool
    active_sessions: int
