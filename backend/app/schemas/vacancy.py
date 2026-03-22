"""
Pydantic схемы для вакансий.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VacancyResponse(BaseModel):
    """Вакансия из локальной таблицы."""

    id: uuid.UUID
    org_id: uuid.UUID
    avito_account_id: uuid.UUID
    avito_item_id: int
    title: str | None
    location: str | None
    status: str
    synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VacancyUpdate(BaseModel):
    """Обновление вакансии."""

    title: str | None = Field(None, max_length=500)
    location: str | None = Field(None, max_length=255)


class VacancyListResponse(BaseModel):
    """Список вакансий с пагинацией."""

    items: list[VacancyResponse]
    total: int
    page: int
    pages: int


class VacancySyncResponse(BaseModel):
    """Результат синхронизации вакансий."""

    synced_count: int
    created: int
    updated: int
    accounts_processed: int
