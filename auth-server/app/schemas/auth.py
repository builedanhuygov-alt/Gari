"""
GARI Auth Server 1.0 — Authentication Request & Response Schemas
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from datetime import datetime
from typing import Optional


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Minimum 8 characters")
    full_name: Optional[str] = Field(default=None, max_length=100)
    name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("full_name", mode="before")
    @classmethod
    def clean_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @property
    def resolved_name(self) -> str:
        val = (self.full_name or self.name or "").strip()
        return val if len(val) >= 2 else "Nông dân Gari"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    remember_me: bool = Field(default=False)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class UserSubscription(BaseModel):
    plan_id: str = "free"
    plan_name: str = "Cá nhân Free"
    is_vip: bool = False
    is_trial: bool = False
    daily_quota: int = 5
    activated_at: Optional[str] = None
    expires_at: Optional[str] = None
    days_left: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    account_type: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    subscription: Optional[UserSubscription] = None
    vip_trial: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    success: bool = True
    message: str = "Đăng nhập thành công."
    user: UserResponse
    csrf_token: Optional[str] = None


class MessageResponse(BaseModel):
    success: bool = True
    message: str
