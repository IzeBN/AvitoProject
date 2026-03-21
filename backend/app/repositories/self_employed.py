"""
Репозиторий проверок самозанятых.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.self_employed import SelfEmployedCheck
from app.repositories.base import BaseRepository


class SelfEmployedRepository(BaseRepository[SelfEmployedCheck]):
    """Репозиторий для работы с проверками самозанятых."""

    model = SelfEmployedCheck

    async def create_check(
        self,
        org_id: uuid.UUID,
        inn: str,
        status: str,
        checked_by: uuid.UUID | None,
        raw_response: dict | None = None,
    ) -> SelfEmployedCheck:
        """Создать запись проверки."""
        check = SelfEmployedCheck(
            org_id=org_id,
            inn=inn,
            status=status,
            checked_by=checked_by,
            checked_at=datetime.now(timezone.utc),
            raw_response=raw_response or {},
        )
        self._session.add(check)
        await self._session.flush()
        await self._session.refresh(check)
        return check

    async def list_by_org(
        self,
        org_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[SelfEmployedCheck], int]:
        """Список проверок организации с пагинацией."""
        count_result = await self._session.execute(
            select(func.count(SelfEmployedCheck.id)).where(
                SelfEmployedCheck.org_id == org_id
            )
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        items_result = await self._session.execute(
            select(SelfEmployedCheck)
            .where(SelfEmployedCheck.org_id == org_id)
            .order_by(SelfEmployedCheck.checked_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(items_result.scalars().all())

        return items, total
