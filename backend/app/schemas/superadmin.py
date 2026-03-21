"""
Pydantic схемы для SuperAdmin API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Пользователи организации ────────────────────────────────────────────────

class OrgUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgUserRoleUpdate(BaseModel):
    role: str = Field(..., pattern=r"^(owner|admin|manager)$")


# ─── Рассылки ─────────────────────────────────────────────────────────────────

class MailingSummary(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    org_name: str | None
    status: str
    total_recipients: int
    sent_count: int
    created_at: datetime


class MailingDetail(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    org_name: str | None
    status: str
    total_recipients: int
    sent_count: int
    failed_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    # Прогресс из Redis
    progress: dict | None = None


class MailingRecipient(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID | None
    status: str
    sent_at: datetime | None
    error: str | None


class MailingListResponse(BaseModel):
    items: list[MailingSummary]
    total: int
    page: int
    pages: int


class MailingRecipientsResponse(BaseModel):
    items: list[MailingRecipient]
    total: int
    page: int
    pages: int


# ─── Ошибки ───────────────────────────────────────────────────────────────────

class ErrorSummary(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID | None
    org_name: str | None
    source: str
    layer: str
    handler: str
    error_type: str
    error_message: str
    resolved: bool
    created_at: datetime


class ErrorDetail(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID | None
    org_name: str | None
    user_id: uuid.UUID | None
    source: str
    layer: str
    handler: str
    request_method: str | None
    request_path: str | None
    request_id: str | None
    error_type: str
    error_message: str
    stack_trace: str | None
    job_type: str | None
    job_id: uuid.UUID | None
    status_code: int | None
    resolved: bool
    resolved_by: uuid.UUID | None
    resolved_at: datetime | None
    note: str | None
    created_at: datetime


class ErrorListResponse(BaseModel):
    items: list[ErrorSummary]
    total: int
    unresolved_count: int


class ErrorResolveRequest(BaseModel):
    note: str | None = None


class ErrorBulkResolveRequest(BaseModel):
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)


# ─── Статистика ───────────────────────────────────────────────────────────────

class OrgStats(BaseModel):
    total: int
    active: int
    suspended: int
    expired: int


class UserStats(BaseModel):
    total: int


class MailingStats(BaseModel):
    today_started: int
    running_now: int
    total: int


class WebhookStats(BaseModel):
    last_hour_count: int


class ErrorStats(BaseModel):
    today_count: int
    unresolved_count: int


class SuperAdminStats(BaseModel):
    organizations: OrgStats
    users: UserStats
    mailings: MailingStats
    webhooks: WebhookStats
    errors: ErrorStats


# ─── Аудит ────────────────────────────────────────────────────────────────────

class AuditLogItem(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID | None
    user_full_name: str | None
    user_role: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    entity_display: str | None
    human_readable: str
    details: dict
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    items: list[AuditLogItem]
    total: int
    page: int
    pages: int
