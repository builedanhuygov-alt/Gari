"""
GARI Auth Server 1.0 — User Profile Endpoints
"""
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserResponse
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/v1/profile", tags=["Profile"])


class UpdateProfileRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)


@router.get("", response_model=UserResponse)
def get_profile(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)


@router.put("", response_model=UserResponse)
def update_profile(
    req: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user.full_name = req.full_name.strip()
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
