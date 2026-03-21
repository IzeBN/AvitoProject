"""
Репозиторий журнала аудита.
"""

import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_for_entity(
        self,
        org_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        """Получить записи аудита для конкретной сущности с пагинацией."""
        conditions = [
            AuditLog.org_id == org_id,
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
        ]
        where_clause = and_(*conditions)

        count_result = await self._session.execute(
            select(func.count(AuditLog.id)).where(where_clause)
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self._session.execute(
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())

        return items, total
