"""
Pydantic схемы для проверки самозанятых.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SelfEmployedCheckRequest(BaseModel):
    """Запрос проверки одного ИНН."""

    inn: str = Field(..., min_length=10, max_length=12, pattern=r"^\d{10,12}$")


class SelfEmployedCheckResponse(BaseModel):
    """Результат проверки самозанятого."""

    inn: str
    # 'active' | 'inactive' | 'not_found' | 'unknown'
    status: str
    checked_at: datetime


class SelfEmployedHistoryItem(BaseModel):
    """Запись из истории проверок."""

    id: uuid.UUID
    inn: str
    status: str | None
    checked_by: uuid.UUID | None
    checked_at: datetime

    model_config = {"from_attributes": True}


class SelfEmployedHistoryResponse(BaseModel):
    """Постраничная история проверок."""

    items: list[SelfEmployedHistoryItem]
    total: int
    page: int
    pages: int


class SelfEmployedBulkRequest(BaseModel):
    """Запрос массовой проверки ИНН."""

    inns: list[str] = Field(..., min_length=1, max_length=100)

    @field_validator("inns")
    @classmethod
    def validate_inns(cls, v: list[str]) -> list[str]:
        for inn in v:
            if not inn.isdigit() or len(inn) not in (10, 12):
                raise ValueError(f"Некорректный ИНН: {inn}")
        return v


class SelfEmployedBulkResponse(BaseModel):
    """Ответ на запрос массовой проверки."""

    job_id: str
    total: int
