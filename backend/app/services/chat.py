"""
ChatService — бизнес-логика чата.
"""

import logging
import math
import uuid

from fastapi import HTTPException, Request, status

from app.repositories.chat import ChatRepository
from app.schemas.chat import (
    ChatListResponse,
    ChatMessagesResponse,
    ChatMessageResponse,
    ChatListItem,
)
from app.services.cache import CacheService

logger = logging.getLogger(__name__)


class ChatService:
    """Сервис работы с историей переписки."""

    def __init__(
        self,
        repo: ChatRepository,
        cache: CacheService,
    ) -> None:
        self._repo = repo
        self._cache = cache

    async def get_chat_list(
        self,
        request: Request,
        page: int,
        page_size: int,
    ) -> ChatListResponse:
        """Список чатов с агрегированными данными."""
        org_id: uuid.UUID = request.state.org_id

        items_raw, total = await self._repo.get_chat_list(
            org_id=org_id, page=page, page_size=page_size
        )

        items = [ChatListItem(**item) for item in items_raw]
        pages = max(1, math.ceil(total / page_size)) if page_size > 0 else 1

        return ChatListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_messages(
        self,
        request: Request,
        candidate_id: uuid.UUID,
        limit: int = 50,
        before_cursor: str | None = None,
    ) -> ChatMessagesResponse:
        """
        История сообщений кандидата с cursor-пагинацией.
        cursor = ISO datetime строка последнего сообщения в предыдущей порции.
        """
        org_id: uuid.UUID = request.state.org_id

        # Находим chat_id по candidate_id
        from app.models.chat import ChatMetadata
        from sqlalchemy import select
        from app.database import get_session_factory

        # Используем кеш для страниц без cursor
        cache_page = 1 if before_cursor is None else 0
        if cache_page and not before_cursor:
            # Формируем ключ на основе candidate_id
            cached = await self._cache.get_chat_messages(str(candidate_id), cache_page)
            if cached:
                items = [ChatMessageResponse(**m) for m in cached]
                return ChatMessagesResponse(
                    items=items,
                    next_cursor=items[-1].created_at.isoformat() if items else None,
                    has_more=len(items) >= limit,
                )

        # Загружаем из репозитория — нужен chat_id
        meta = await self._repo.get_metadata_by_candidate(candidate_id)
        if meta is None:
            return ChatMessagesResponse(items=[], next_cursor=None, has_more=False)

        msgs, has_more = await self._repo.get_messages(
            chat_id=meta.chat_id,
            org_id=org_id,
            limit=limit,
            before_cursor=before_cursor,
        )

        items = [
            ChatMessageResponse(
                id=m.id,
                chat_id=m.chat_id,
                candidate_id=candidate_id,
                author_type=m.author_type,
                message_type=m.message_type,
                content=m.content,
                avito_message_id=m.avito_message_id,
                is_read=m.is_read,
                created_at=m.created_at,
            )
            for m in msgs
        ]

        next_cursor = None
        if has_more and items:
            next_cursor = items[0].created_at.isoformat()

        # Кешируем первую страницу
        if cache_page and not before_cursor:
            await self._cache.set_chat_messages(
                str(candidate_id),
                cache_page,
                [i.model_dump(mode="json") for i in items],
            )

        return ChatMessagesResponse(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def mark_read(
        self, request: Request, candidate_id: uuid.UUID
    ) -> None:
        """
        Отметить чат прочитанным.
        Используется write-behind: обновляем Redis, воркер смывает в БД.
        """
        org_id: uuid.UUID = request.state.org_id

        meta = await self._repo.get_metadata_by_candidate(candidate_id)
        if meta is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Чат не найден",
            )

        # Прямое обновление в БД: unread_count=0, has_new_message=false
        await self._repo.mark_read(meta.chat_id, org_id)
        await self._repo._session.commit()

        # Write-behind: синхронизируем Redis-буфер
        await self._cache.wb_update_chat_meta(
            meta.chat_id,
            {"unread_count": "0"},
        )

        # Инвалидируем кеш сообщений и кандидатов
        await self._cache.invalidate_chat(str(candidate_id))
        await self._cache.invalidate_candidates(org_id)
