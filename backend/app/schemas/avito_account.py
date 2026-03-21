"""
Pydantic схемы для Avito аккаунтов и вебхук эндпоинтов.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AvitoAccountCreate(BaseModel):
    client_id: str = Field(..., description="OAuth2 client_id (будет зашифрован)")
    client_secret: str = Field(..., description="OAuth2 client_secret (будет зашифрован)")


class AvitoAccountUpdate(BaseModel):
    """Обновление Avito аккаунта."""

    account_name: str | None = Field(default=None, max_length=255)
    department_id: uuid.UUID | None = Field(default=None)


class AvitoAccountResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str                          # account_name алиас для фронтенда
    avito_user_id: int
    avito_client_id: str | None = None
    status: str                        # 'active' | 'inactive'
    balance: float | None = None
    webhooks_active: bool = False
    unread_count: int = 0
    last_sync_at: datetime | None = None
    department_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_account(cls, account: object, webhooks_active: bool = False) -> "AvitoAccountResponse":
        from app.models.avito import AvitoAccount as _Model
        a: _Model = account  # type: ignore[assignment]
        return cls(
            id=a.id,
            org_id=a.org_id,
            name=a.account_name,
            avito_user_id=a.avito_user_id,
            status="active" if a.is_active else "inactive",
            webhooks_active=webhooks_active,
            department_id=a.department_id,
            created_at=a.created_at,
        )


class WebhookEndpointResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    account_token: str
    is_active: bool
    last_received_at: datetime | None

    model_config = {"from_attributes": True}


class WebhookSetupResponse(BaseModel):
    endpoints: list[WebhookEndpointResponse]


class BalanceResponse(BaseModel):
    bonus: int = 0
    real: int = 0
    total: int = 0
