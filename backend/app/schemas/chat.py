"""
Схемы Pydantic для чата.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageResponse(BaseModel):
    """Сообщение чата."""

    id: uuid.UUID
    chat_id: str
    candidate_id: uuid.UUID
    author_type: str  # 'account' | 'candidate' | 'system'
    message_type: str  # 'text' | 'image' | 'file' | 'link'
    content: str | None
    avito_message_id: str | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatListItem(BaseModel):
    """Элемент списка чатов (агрегированные данные)."""

    candidate_id: uuid.UUID
    chat_id: str
    candidate_name: str | None
    last_message: str | None
    last_message_at: datetime | None
    unread_count: int
    is_blocked: bool

    model_config = {"from_attributes": True}


class ChatListResponse(BaseModel):
    """Список чатов с пагинацией."""

    items: list[ChatListItem]
    total: int
    page: int
    page_size: int
    pages: int


class ChatMessagesResponse(BaseModel):
    """История сообщений с cursor-пагинацией."""

    items: list[ChatMessageResponse]
    next_cursor: str | None = None
    has_more: bool = False


class MarkReadRequest(BaseModel):
    """Запрос на отметку чата прочитанным."""

    pass  # тело пустое, действие по candidate_id из URL


class FilterOptionsResponse(BaseModel):
    """Значения для выпадающих списков фильтров."""

    stages: list[dict]
    tags: list[dict]
    departments: list[dict]
    responsible_users: list[dict]
    avito_accounts: list[dict]


# ---------------------------------------------------------------------------
# Send message
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    """Запрос отправки сообщения кандидату."""

    text: str = Field(..., min_length=1, max_length=4096)
    attachments: list[str] | None = Field(
        default=None,
        description="Список URL или base64-строк вложений (опционально)",
    )


# ---------------------------------------------------------------------------
# Fast answers
# ---------------------------------------------------------------------------


class FastAnswerCreate(BaseModel):
    """Создать быстрый ответ."""

    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1)
    sort_order: int = Field(default=0, ge=0)


class FastAnswerUpdate(BaseModel):
    """Обновить быстрый ответ (все поля опциональны)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    text: str | None = Field(default=None, min_length=1)
    sort_order: int | None = Field(default=None, ge=0)


class FastAnswerResponse(BaseModel):
    """Быстрый ответ."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    text: str
    sort_order: int
    created_at: datetime


class FastAnswerReorderItem(BaseModel):
    id: uuid.UUID
    sort_order: int = Field(..., ge=0)


class FastAnswerReorderRequest(BaseModel):
    items: list[FastAnswerReorderItem] = Field(..., min_length=1)
