"""
Схемы Pydantic для кандидатов CRM.
"""

import math
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Short (вложенные) схемы для связанных сущностей
# ---------------------------------------------------------------------------


class StageShort(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None = None
    sort_order: int

    model_config = {"from_attributes": True}


class TagShort(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None = None

    model_config = {"from_attributes": True}


class DepartmentShort(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class UserShort(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Фильтры
# ---------------------------------------------------------------------------


class CandidateFilters(BaseModel):
    """Фильтры для списка кандидатов."""

    stage_id: uuid.UUID | None = None
    responsible_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    avito_account_id: uuid.UUID | None = None
    tag_ids: list[uuid.UUID] | None = None
    has_new_message: bool | None = None
    only_unread: bool | None = None
    search: str | None = None
    location: str | None = None
    vacancy: str | None = None
    vacancy_id: uuid.UUID | None = None
    due_date_from: date | None = None
    due_date_to: date | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None
    last_message_from: datetime | None = None


# ---------------------------------------------------------------------------
# Ответы
# ---------------------------------------------------------------------------


class CandidateResponse(BaseModel):
    """Полный ответ по кандидату."""

    id: uuid.UUID
    name: str | None
    phone: str | None = None  # расшифрованный — только при праве view_phone
    vacancy: str | None
    vacancy_id: uuid.UUID | None = None
    location: str | None
    stage: StageShort | None
    department: DepartmentShort | None
    responsible: UserShort | None
    tags: list[TagShort] = Field(default_factory=list)
    comment: str | None
    due_date: date | None
    has_new_message: bool
    last_message: str | None = None
    last_message_at: datetime | None = None
    unread_count: int = 0
    source: str | None
    avito_account_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CandidateListResponse(BaseModel):
    """Ответ списка кандидатов с пагинацией."""

    items: list[CandidateResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(
        cls,
        items: list[CandidateResponse],
        total: int,
        page: int,
        page_size: int,
    ) -> "CandidateListResponse":
        pages = max(1, math.ceil(total / page_size)) if page_size > 0 else 1
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


# ---------------------------------------------------------------------------
# Мутации
# ---------------------------------------------------------------------------


class CandidateCreate(BaseModel):
    """Создание нового кандидата."""

    full_name: str = Field(..., max_length=255, description="ФИО кандидата")
    phone: str | None = Field(None, max_length=20, description="Номер телефона (будет зашифрован)")
    stage_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = Field(None, description="ID ответственного пользователя")
    avito_account_id: uuid.UUID | None = None
    source: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, description="Комментарий / заметки")
    tag_ids: list[uuid.UUID] = Field(default_factory=list)


class CandidateEdit(BaseModel):
    """Поля для редактирования кандидата (PATCH — все опциональны)."""

    stage_id: uuid.UUID | None = None
    responsible_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    comment: str | None = None
    due_date: date | None = None
    vacancy: str | None = None
    vacancy_id: uuid.UUID | None = None


class BulkEditRequest(BaseModel):
    """Массовое обновление по списку ID."""

    candidate_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)
    edit: CandidateEdit


class BulkEditByFiltersRequest(BaseModel):
    """Массовое обновление по фильтрам."""

    filters: CandidateFilters
    edit: CandidateEdit


class BulkEditResponse(BaseModel):
    """Результат массового обновления."""

    updated: int
    message: str
