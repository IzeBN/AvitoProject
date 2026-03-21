"""
Схемы Pydantic для настроек организации: этапы, теги, отделы, права.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pipeline Stages
# ---------------------------------------------------------------------------


class StageCreate(BaseModel):
    name: str = Field(..., max_length=255)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int = Field(default=0, ge=0)
    is_default: bool = False


class StageUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int | None = Field(None, ge=0)
    is_default: bool | None = None


class StageResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    color: str | None
    sort_order: int
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StageReorderItem(BaseModel):
    id: uuid.UUID
    sort_order: int = Field(..., ge=0)


class StageReorderRequest(BaseModel):
    stages: list[StageReorderItem] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


class TagCreate(BaseModel):
    name: str = Field(..., max_length=100)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class TagUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class TagResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    color: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------


class DepartmentCreate(BaseModel):
    name: str = Field(..., max_length=255)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


class PermissionsMatrixResponse(BaseModel):
    """Матрица прав: {role: {permission_key: bool}}."""

    matrix: dict[str, dict[str, bool]]


class PermissionsUpdateRequest(BaseModel):
    """Обновление прав для конкретной роли."""

    role: str = Field(..., pattern=r"^(owner|admin|manager)$")
    permissions: list[str] = Field(
        ...,
        description="Список кодов прав которые нужно ВЫДАТЬ роли. "
        "Остальные права будут ОТОЗВАНЫ (полная замена).",
    )
