"""
Pydantic схемы для рассылок.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MailingByPhonesRequest(BaseModel):
    phones: list[str] = Field(..., min_length=1, description="Список номеров телефонов")
    message_text: str = Field(..., min_length=1)
    scheduled_at: datetime | None = None
    rate_limit_ms: int = Field(default=1000, ge=200, le=60000)


class MailingCreateRequest(BaseModel):
    """Создать рассылку по критериям фильтрации кандидатов."""

    name: str = Field(default="", max_length=255)
    message_text: str = Field(..., min_length=1)
    avito_account_id: uuid.UUID | None = None
    candidate_filters: dict = Field(
        default_factory=dict,
        description="Фильтры кандидатов (те же что в /candidates)",
    )
    scheduled_at: datetime | None = None
    rate_limit_ms: int = Field(default=1000, ge=200, le=60000)


class MailingByIdsRequest(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    file_url: str | None = None
    scheduled_at: datetime | None = None
    rate_limit_ms: int = Field(default=1000, ge=200, le=60000)


class MailingByFiltersRequest(BaseModel):
    filters: dict = Field(default_factory=dict)
    message: str = Field(..., min_length=1)
    file_url: str | None = None
    scheduled_at: datetime | None = None
    rate_limit_ms: int = Field(default=1000, ge=200, le=60000)


class MailingProgressResponse(BaseModel):
    sent: int = 0
    failed: int = 0
    total: int = 0
    percent: float = 0.0


class MailingJobResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    status: str
    message: str
    file_url: str | None
    criteria: dict
    scheduled_at: datetime | None
    rate_limit_ms: int
    total: int
    sent: int
    failed: int
    skipped: int
    started_at: datetime | None
    paused_at: datetime | None
    finished_at: datetime | None
    arq_job_id: str | None
    created_at: datetime
    progress: MailingProgressResponse | None = None

    model_config = {"from_attributes": True}


class MailingRecipientResponse(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    status: str
    attempt_count: int
    last_attempt_at: datetime | None
    sent_at: datetime | None
    error_code: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


class MailingRecipientsPage(BaseModel):
    items: list[MailingRecipientResponse]
    total: int
    page: int
    page_size: int
