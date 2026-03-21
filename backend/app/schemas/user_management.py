"""
Pydantic схемы для управления пользователями организации.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserInviteRequest(BaseModel):
    """Приглашение нового сотрудника по логину или email."""

    login_or_email: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., pattern=r"^(admin|manager)$")


class UserUpdateRequest(BaseModel):
    """Обновление данных сотрудника."""

    full_name: str | None = Field(None, min_length=2, max_length=255)
    role: str | None = Field(None, pattern=r"^(owner|admin|manager)$")


class UserResponse(BaseModel):
    """Данные сотрудника."""

    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Список сотрудников."""

    items: list[UserResponse]
    total: int
    page: int
    pages: int


class UserPermissionsResponse(BaseModel):
    """Текущие права пользователя."""

    granted: list[str]
    denied: list[str]


class UserPermissionsUpdate(BaseModel):
    """Установка индивидуальных прав."""

    permissions: list[dict]
    # Список {code: str, granted: bool}


class UserDepartmentsResponse(BaseModel):
    """Отделы пользователя."""

    department_ids: list[uuid.UUID]


class UserDepartmentsUpdate(BaseModel):
    """Замена списка отделов пользователя."""

    department_ids: list[uuid.UUID]


class RolePermissionsResponse(BaseModel):
    """Права роли в организации."""

    role: str
    permissions: list[str]


class RolePermissionsUpdate(BaseModel):
    """Обновление прав роли."""

    permissions: list[str]
