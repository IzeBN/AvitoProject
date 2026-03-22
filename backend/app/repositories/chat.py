"""
Репозиторий чата — сообщения и метаданные.
"""

import uuid
from datetime import datetime

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatMetadata
from app.models.crm import Candidate
from app.repositories.base import BaseRepository


class ChatRepository(BaseRepository[ChatMessage]):
    model = ChatMessage

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_messages(
        self,
        chat_id: str,
        org_id: uuid.UUID,
        limit: int = 50,
        before_cursor: str | None = None,  # ISO datetime строка
    ) -> tuple[list[ChatMessage], bool]:
        """
        Получить историю сообщений с cursor-пагинацией.

        Возвращает (messages, has_more).
        """
        conditions = [
            ChatMessage.chat_id == chat_id,
            ChatMessage.org_id == org_id,
        ]

        if before_cursor:
            try:
                cursor_dt = datetime.fromisoformat(before_cursor)
                conditions.append(ChatMessage.created_at < cursor_dt)
            except ValueError:
                pass

        stmt = (
            select(ChatMessage)
            .where(and_(*conditions))
            .order_by(ChatMessage.created_at.desc())
            .limit(limit + 1)
        )
        result = await self._session.execute(stmt)
        msgs = list(result.scalars().all())

        has_more = len(msgs) > limit
        if has_more:
            msgs = msgs[:limit]

        # Возвращаем в хронологическом порядке
        msgs.reverse()
        return msgs, has_more

    async def get_chat_list(
        self,
        org_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """
        Список чатов с агрегированными данными.
        Возвращает (items, total).
        """
        from sqlalchemy import func

        # COUNT
        count_stmt = select(func.count(ChatMetadata.id)).where(
            ChatMetadata.org_id == org_id
        )
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size

        stmt = (
            select(
                ChatMetadata,
                Candidate.name.label("candidate_name"),
            )
            .join(Candidate, Candidate.id == ChatMetadata.candidate_id)
            .where(
                ChatMetadata.org_id == org_id,
                Candidate.deleted_at.is_(None),
            )
            .order_by(func.coalesce(ChatMetadata.last_message_at, ChatMetadata.updated_at).desc())
            .offset(offset)
            .limit(page_size)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        items = []
        for row in rows:
            meta = row[0]
            candidate_name = row[1]
            items.append(
                {
                    "candidate_id": meta.candidate_id,
                    "chat_id": meta.chat_id,
                    "candidate_name": candidate_name,
                    "last_message": meta.last_message,
                    "last_message_at": meta.last_message_at,
                    "unread_count": meta.unread_count,
                    "is_blocked": meta.is_blocked,
                }
            )

        return items, total

    async def get_metadata_by_candidate(
        self, candidate_id: uuid.UUID
    ) -> ChatMetadata | None:
        result = await self._session.execute(
            select(ChatMetadata).where(ChatMetadata.candidate_id == candidate_id)
        )
        return result.scalar_one_or_none()

    async def mark_read(self, chat_id: str, org_id: uuid.UUID) -> None:
        """Сбросить счётчик непрочитанных сообщений (запись в БД)."""
        stmt = (
            update(ChatMetadata)
            .where(
                ChatMetadata.chat_id == chat_id,
                ChatMetadata.org_id == org_id,
            )
            .values(unread_count=0)
        )
        await self._session.execute(stmt)

        # Помечаем все сообщения как прочитанные
        stmt2 = (
            update(ChatMessage)
            .where(
                ChatMessage.chat_id == chat_id,
                ChatMessage.org_id == org_id,
                ChatMessage.is_read == False,  # noqa: E712
                ChatMessage.author_type == "candidate",
            )
            .values(is_read=True)
        )
        await self._session.execute(stmt2)
