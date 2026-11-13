"""
GARI Auth Server 1.0 — Authentication Request & Response Schemas
"""
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from datetime import datetime
from typing import Optional


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="Minimum 8 characters")
    full_name: str = Field(..., min_length=2, max_length=100)

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


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    account_type: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    success: bool = True
    message: str = "Đăng nhập thành công."
    user: UserResponse
    csrf_token: Optional[str] = None


class MessageResponse(BaseModel):
    success: bool = True
    message: str
