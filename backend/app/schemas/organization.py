"""
Pydantic схемы для организаций.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrgSummary(BaseModel):
    """Краткая сводка организации для списка SuperAdmin."""

    id: uuid.UUID
    name: str
    slug: str
    access_status: str
    subscription_until: datetime | None
    users_count: int
    avito_accounts_count: int
    created_at: datetime
    suspended_reason: str | None = None

    model_config = {"from_attributes": True}


class OrgDetail(BaseModel):
    """Полные данные организации."""

    id: uuid.UUID
    name: str
    slug: str
    access_status: str
    subscription_until: datetime | None
    settings: dict
    max_users: int
    max_avito_accounts: int
    suspended_at: datetime | None
    suspended_by: uuid.UUID | None
    suspend_reason: str | None
    created_at: datetime
    updated_at: datetime

    # Статистика
    users_count: int = 0
    avito_accounts_count: int = 0
    candidates_count: int = 0
    mailings_count: int = 0

    model_config = {"from_attributes": True}


class OrgCreate(BaseModel):
    """Создание организации через SuperAdmin."""

    name: str = Field(..., min_length=2, max_length=255)
    slug: str | None = Field(None, min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    max_users: int = Field(default=50, ge=1, le=10000)
    max_avito_accounts: int = Field(default=5, ge=1, le=100)
    subscription_until: datetime | None = None
    owner_email: str | None = None


class OrgUpdate(BaseModel):
    """Обновление настроек организации."""

    name: str | None = Field(None, min_length=2, max_length=255)
    max_users: int | None = Field(None, ge=1, le=10000)
    max_avito_accounts: int | None = Field(None, ge=1, le=100)
    settings: dict | None = None
    subscription_until: datetime | None = None


class OrgSuspendRequest(BaseModel):
    """Запрос на приостановку организации."""

    reason: str = Field(..., min_length=3, max_length=1000)


class OrgSubscriptionUpdate(BaseModel):
    """Обновление подписки организации."""

    subscription_until: datetime | None


class OrgListResponse(BaseModel):
    """Постраничный список организаций."""

    items: list[OrgSummary]
    total: int
    page: int
    pages: int


class ImpersonateResponse(BaseModel):
    """Ответ на запрос impersonation."""

    access_token: str
    expires_in: int = 3600
