"""
Репозиторий кандидатов — все запросы к БД.
"""

import uuid
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.crm import Candidate, CandidateTag, Tag
from app.models.chat import ChatMetadata
from app.repositories.base import BaseRepository
from app.schemas.candidate import CandidateFilters


class CandidateRepository(BaseRepository[Candidate]):
    model = Candidate

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    def _build_conditions(
        self,
        org_id: uuid.UUID,
        filters: CandidateFilters,
        user_departments: list[uuid.UUID] | None,
    ) -> list:
        """Построить список условий WHERE для фильтрации кандидатов."""
        conditions = [
            Candidate.org_id == org_id,
            Candidate.deleted_at.is_(None),
        ]

        if filters.stage_id is not None:
            conditions.append(Candidate.stage_id == filters.stage_id)

        if filters.responsible_id is not None:
            conditions.append(Candidate.responsible_id == filters.responsible_id)

        if filters.department_id is not None:
            conditions.append(Candidate.department_id == filters.department_id)

        if filters.avito_account_id is not None:
            conditions.append(Candidate.avito_account_id == filters.avito_account_id)

        if filters.has_new_message is not None:
            conditions.append(Candidate.has_new_message == filters.has_new_message)

        if filters.location is not None:
            conditions.append(Candidate.location.ilike(f"%{filters.location}%"))

        if filters.vacancy is not None:
            conditions.append(Candidate.vacancy.ilike(f"%{filters.vacancy}%"))

        if filters.due_date_from is not None:
            conditions.append(Candidate.due_date >= filters.due_date_from)

        if filters.due_date_to is not None:
            conditions.append(Candidate.due_date <= filters.due_date_to)

        if filters.created_at_from is not None:
            conditions.append(Candidate.created_at >= filters.created_at_from)

        if filters.created_at_to is not None:
            conditions.append(Candidate.created_at <= filters.created_at_to)

        # Контроль доступа по отделу
        if user_departments is not None:
            conditions.append(
                or_(
                    Candidate.department_id.in_(user_departments),
                    Candidate.department_id.is_(None),
                )
            )

        return conditions

    async def get_list(
        self,
        org_id: uuid.UUID,
        filters: CandidateFilters,
        page: int,
        page_size: int,
        user_departments: list[uuid.UUID] | None,
        search_hash_fn: Any | None = None,  # callable(str) -> str
    ) -> tuple[list[Candidate], int]:
        """
        Получить список кандидатов с фильтрами и пагинацией.

        Возвращает (items, total_count).
        """
        conditions = self._build_conditions(org_id, filters, user_departments)

        # Поиск
        if filters.search:
            search_val = filters.search.strip()
            if search_val and search_val[0].isdigit() and search_hash_fn is not None:
                # Поиск по телефону через HMAC хеш
                phone_hash = search_hash_fn(search_val)
                conditions.append(Candidate.phone_search_hash == phone_hash)
            elif search_val:
                # Поиск по имени через pg_trgm similarity
                conditions.append(
                    text("candidates.name % :search").bindparams(search=search_val)
                )

        offset = (page - 1) * page_size

        # Базовый запрос
        base_stmt = (
            select(Candidate)
            .options(
                selectinload(Candidate.tags),
                selectinload(Candidate.stage),
                selectinload(Candidate.department),
                selectinload(Candidate.responsible),
            )
            .where(and_(*conditions))
        )

        # Фильтрация по тегам
        if filters.tag_ids:
            tag_subq = (
                select(CandidateTag.candidate_id)
                .where(CandidateTag.tag_id.in_(filters.tag_ids))
                .distinct()
                .scalar_subquery()
            )
            base_stmt = base_stmt.where(Candidate.id.in_(tag_subq))

        # Фильтр only_unread — через JOIN с chat_metadata
        if filters.only_unread:
            unread_subq = (
                select(ChatMetadata.candidate_id)
                .where(ChatMetadata.unread_count > 0)
                .scalar_subquery()
            )
            base_stmt = base_stmt.where(Candidate.id.in_(unread_subq))

        # Фильтр last_message_from — через JOIN с chat_metadata
        if filters.last_message_from is not None:
            lm_subq = (
                select(ChatMetadata.candidate_id)
                .where(ChatMetadata.last_message_at >= filters.last_message_from)
                .scalar_subquery()
            )
            base_stmt = base_stmt.where(Candidate.id.in_(lm_subq))

        # COUNT
        count_stmt = select(func.count()).select_from(
            base_stmt.with_only_columns(Candidate.id).subquery()
        )
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        # Данные с пагинацией
        data_stmt = (
            base_stmt
            .order_by(Candidate.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self._session.execute(data_stmt)
        items = list(result.scalars().unique().all())

        return items, total

    async def get_by_id_with_relations(
        self, org_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> Candidate | None:
        """Загрузить кандидата со всеми связями."""
        result = await self._session.execute(
            select(Candidate)
            .options(
                selectinload(Candidate.tags),
                selectinload(Candidate.stage),
                selectinload(Candidate.department),
                selectinload(Candidate.responsible),
            )
            .where(
                Candidate.id == candidate_id,
                Candidate.org_id == org_id,
                Candidate.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_chat_id(self, org_id: uuid.UUID, chat_id: str) -> Candidate | None:
        result = await self._session.execute(
            select(Candidate).where(
                Candidate.org_id == org_id,
                Candidate.chat_id == chat_id,
                Candidate.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def bulk_update(
        self,
        org_id: uuid.UUID,
        candidate_ids: list[uuid.UUID],
        data: dict,
    ) -> int:
        """
        Массовое обновление кандидатов по списку ID.
        Возвращает количество обновлённых.
        """
        if not data:
            return 0

        stmt = (
            update(Candidate)
            .where(
                Candidate.id.in_(candidate_ids),
                Candidate.org_id == org_id,
                Candidate.deleted_at.is_(None),
            )
            .values(**data)
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def bulk_update_by_filters(
        self,
        org_id: uuid.UUID,
        filters: CandidateFilters,
        data: dict,
        user_departments: list[uuid.UUID] | None = None,
    ) -> int:
        """
        Массовое обновление кандидатов по фильтрам.
        Возвращает количество обновлённых.
        """
        if not data:
            return 0

        conditions = self._build_conditions(org_id, filters, user_departments)

        # Формируем подзапрос ID для тегов если нужно
        if filters.tag_ids:
            tag_subq = (
                select(CandidateTag.candidate_id)
                .where(CandidateTag.tag_id.in_(filters.tag_ids))
                .distinct()
                .scalar_subquery()
            )
            conditions.append(Candidate.id.in_(tag_subq))

        stmt = (
            update(Candidate)
            .where(and_(*conditions))
            .values(**data)
            .execution_options(synchronize_session="fetch")
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def add_tag(
        self, org_id: uuid.UUID, candidate_id: uuid.UUID, tag_id: uuid.UUID
    ) -> None:
        """Привязать тег к кандидату (игнорирует дубликаты)."""
        # Проверяем что кандидат принадлежит организации
        stmt = select(Candidate.id).where(
            Candidate.id == candidate_id,
            Candidate.org_id == org_id,
            Candidate.deleted_at.is_(None),
        )
        result = await self._session.execute(stmt)
        if result.scalar_one_or_none() is None:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кандидат не найден")

        # Проверяем что тег принадлежит организации
        tag_stmt = select(Tag.id).where(Tag.id == tag_id, Tag.org_id == org_id)
        tag_result = await self._session.execute(tag_stmt)
        if tag_result.scalar_one_or_none() is None:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тег не найден")

        # Upsert через INSERT ... ON CONFLICT DO NOTHING
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(CandidateTag).values(
            candidate_id=candidate_id,
            tag_id=tag_id,
            org_id=org_id,
        ).on_conflict_do_nothing()
        await self._session.execute(stmt)

    async def remove_tag(
        self, org_id: uuid.UUID, candidate_id: uuid.UUID, tag_id: uuid.UUID
    ) -> None:
        """Удалить тег с кандидата."""
        stmt = delete(CandidateTag).where(
            CandidateTag.candidate_id == candidate_id,
            CandidateTag.tag_id == tag_id,
            CandidateTag.org_id == org_id,
        )
        await self._session.execute(stmt)

    async def get_chat_metadata(self, candidate_id: uuid.UUID) -> ChatMetadata | None:
        result = await self._session.execute(
            select(ChatMetadata).where(ChatMetadata.candidate_id == candidate_id)
        )
        return result.scalar_one_or_none()

    async def create_candidate(
        self,
        org_id: uuid.UUID,
        **kwargs: Any,
    ) -> Candidate:
        """Создать нового кандидата."""
        candidate = Candidate(org_id=org_id, **kwargs)
        self._session.add(candidate)
        await self._session.flush()
        await self._session.refresh(candidate)
        return candidate

    async def soft_delete(
        self, org_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> Candidate | None:
        """
        Мягко удалить кандидата (установить deleted_at).
        Возвращает кандидата или None если не найден.
        """
        from datetime import timezone

        result = await self._session.execute(
            select(Candidate).where(
                Candidate.id == candidate_id,
                Candidate.org_id == org_id,
                Candidate.deleted_at.is_(None),
            )
        )
        candidate = result.scalar_one_or_none()
        if candidate is None:
            return None

        from datetime import datetime
        candidate.deleted_at = datetime.now(timezone.utc)
        self._session.add(candidate)
        await self._session.flush()
        return candidate

    async def get_stages(self, org_id: uuid.UUID) -> list:
        """Получить все этапы воронки организации."""
        from app.models.crm import PipelineStage

        result = await self._session.execute(
            select(PipelineStage)
            .where(PipelineStage.org_id == org_id)
            .order_by(PipelineStage.sort_order)
        )
        return list(result.scalars().all())

    async def get_tags(self, org_id: uuid.UUID) -> list:
        """Получить все теги организации."""
        result = await self._session.execute(
            select(Tag)
            .where(Tag.org_id == org_id)
            .order_by(Tag.name)
        )
        return list(result.scalars().all())
