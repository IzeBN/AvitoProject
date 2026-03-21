"""
Схемы пользователя и профиля.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class OrgInfo(BaseModel):
    """Краткая информация об организации."""

    id: uuid.UUID
    name: str
    slug: str
    access_status: str


class UserResponse(BaseModel):
    """Публичные данные пользователя."""

    id: uuid.UUID
    org_id: uuid.UUID
    email: EmailStr
    username: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfile(BaseModel):
    """Профиль текущего пользователя с данными организации."""

    id: uuid.UUID
    org_id: uuid.UUID | None
    email: EmailStr
    username: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    organization: OrgInfo | None

    model_config = {"from_attributes": True}


class UserMeResponse(BaseModel):
    """Профиль текущего пользователя (GET /users/me)."""

    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    last_active_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserMeUpdate(BaseModel):
    """Обновление собственного профиля (PATCH /users/me)."""

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    avatar_url: str | None = Field(default=None, max_length=1024)


class ChangePasswordRequest(BaseModel):
    """Смена пароля текущего пользователя."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
