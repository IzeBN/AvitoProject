"""
Репозиторий журнала ошибок.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import Organization
from app.models.error_log import ErrorLog
from app.repositories.base import BaseRepository


class ErrorLogRepository(BaseRepository[ErrorLog]):
    """Репозиторий для работы с журналом ошибок."""

    model = ErrorLog

    async def list_errors(
        self,
        org_id: uuid.UUID | None = None,
        source: str | None = None,
        layer: str | None = None,
        resolved: bool | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ErrorLog], int, int]:
        """
        Список ошибок с фильтрацией.
        Возвращает (items, total, unresolved_count).
        """
        base_cond = []
        if org_id is not None:
            base_cond.append(ErrorLog.org_id == org_id)
        if source:
            base_cond.append(ErrorLog.source == source)
        if layer:
            base_cond.append(ErrorLog.layer == layer)
        if resolved is not None:
            base_cond.append(ErrorLog.resolved == resolved)
        if date_from:
            dt_from = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
            base_cond.append(ErrorLog.created_at >= dt_from)
        if date_to:
            dt_to = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)
            base_cond.append(ErrorLog.created_at <= dt_to)

        count_result = await self._session.execute(
            select(func.count(ErrorLog.id)).where(*base_cond)
        )
        total = count_result.scalar_one()

        # Количество неразрешённых (без фильтра resolved)
        unresolved_cond = [c for c in base_cond if not str(c).endswith("resolved")]
        unresolved_q = select(func.count(ErrorLog.id)).where(
            ErrorLog.resolved.is_(False)
        )
        if org_id is not None:
            unresolved_q = unresolved_q.where(ErrorLog.org_id == org_id)
        unresolved_result = await self._session.execute(unresolved_q)
        unresolved_count = unresolved_result.scalar_one()

        offset = (page - 1) * page_size
        items_result = await self._session.execute(
            select(ErrorLog)
            .where(*base_cond)
            .order_by(ErrorLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(items_result.scalars().all())

        return items, total, unresolved_count

    async def resolve(
        self,
        error_id: uuid.UUID,
        resolved_by: uuid.UUID,
        note: str | None = None,
    ) -> ErrorLog | None:
        """Отметить ошибку как решённую."""
        result = await self._session.execute(
            select(ErrorLog).where(ErrorLog.id == error_id)
        )
        error = result.scalar_one_or_none()
        if error is None:
            return None

        error.resolved = True
        error.resolved_by = resolved_by
        error.resolved_at = datetime.now(timezone.utc)
        if note:
            error.note = note
        self._session.add(error)
        await self._session.flush()
        return error

    async def resolve_bulk(
        self,
        ids: list[uuid.UUID],
        resolved_by: uuid.UUID,
    ) -> int:
        """Массовое решение ошибок. Возвращает количество обновлённых."""
        from sqlalchemy import update

        result = await self._session.execute(
            update(ErrorLog)
            .where(
                ErrorLog.id.in_(ids),
                ErrorLog.resolved.is_(False),
            )
            .values(
                resolved=True,
                resolved_by=resolved_by,
                resolved_at=datetime.now(timezone.utc),
            )
        )
        await self._session.flush()
        return result.rowcount

    async def count_today(self) -> int:
        """Количество ошибок за сегодня."""
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self._session.execute(
            select(func.count(ErrorLog.id)).where(ErrorLog.created_at >= today)
        )
        return result.scalar_one()

    async def count_unresolved(self) -> int:
        """Количество неразрешённых ошибок."""
        result = await self._session.execute(
            select(func.count(ErrorLog.id)).where(ErrorLog.resolved.is_(False))
        )
        return result.scalar_one()
