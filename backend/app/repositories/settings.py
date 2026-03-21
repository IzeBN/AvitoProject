"""
Репозиторий настроек организации: этапы, теги, отделы.
"""

import uuid
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import PipelineStage, Tag
from app.models.rbac import Department
from app.repositories.base import BaseRepository


class StageRepository(BaseRepository[PipelineStage]):
    model = PipelineStage

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_org(self, org_id: uuid.UUID) -> list[PipelineStage]:
        result = await self._session.execute(
            select(PipelineStage)
            .where(PipelineStage.org_id == org_id)
            .order_by(PipelineStage.sort_order.asc(), PipelineStage.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_id_org(
        self, org_id: uuid.UUID, stage_id: uuid.UUID
    ) -> PipelineStage | None:
        result = await self._session.execute(
            select(PipelineStage).where(
                PipelineStage.id == stage_id,
                PipelineStage.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def reorder(self, org_id: uuid.UUID, items: list[dict]) -> None:
        """Обновить sort_order для списка этапов одним батчем."""
        for item in items:
            stmt = (
                update(PipelineStage)
                .where(
                    PipelineStage.id == item["id"],
                    PipelineStage.org_id == org_id,
                )
                .values(sort_order=item["sort_order"])
            )
            await self._session.execute(stmt)

    async def name_exists(
        self, org_id: uuid.UUID, name: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        conditions = [
            PipelineStage.org_id == org_id,
            PipelineStage.name == name,
        ]
        if exclude_id:
            conditions.append(PipelineStage.id != exclude_id)
        result = await self._session.execute(
            select(PipelineStage.id).where(and_(*conditions))
        )
        return result.scalar_one_or_none() is not None


class TagRepository(BaseRepository[Tag]):
    model = Tag

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_org(self, org_id: uuid.UUID) -> list[Tag]:
        result = await self._session.execute(
            select(Tag)
            .where(Tag.org_id == org_id)
            .order_by(Tag.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_id_org(self, org_id: uuid.UUID, tag_id: uuid.UUID) -> Tag | None:
        result = await self._session.execute(
            select(Tag).where(Tag.id == tag_id, Tag.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def name_exists(
        self, org_id: uuid.UUID, name: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        conditions = [Tag.org_id == org_id, Tag.name == name]
        if exclude_id:
            conditions.append(Tag.id != exclude_id)
        result = await self._session.execute(
            select(Tag.id).where(and_(*conditions))
        )
        return result.scalar_one_or_none() is not None


class DepartmentRepository(BaseRepository[Department]):
    model = Department

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_org(self, org_id: uuid.UUID) -> list[Department]:
        result = await self._session.execute(
            select(Department)
            .where(Department.org_id == org_id)
            .order_by(Department.name.asc())
        )
        return list(result.scalars().all())

    async def get_by_id_org(
        self, org_id: uuid.UUID, dept_id: uuid.UUID
    ) -> Department | None:
        result = await self._session.execute(
            select(Department).where(
                Department.id == dept_id,
                Department.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def name_exists(
        self, org_id: uuid.UUID, name: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        conditions = [Department.org_id == org_id, Department.name == name]
        if exclude_id:
            conditions.append(Department.id != exclude_id)
        result = await self._session.execute(
            select(Department.id).where(and_(*conditions))
        )
        return result.scalar_one_or_none() is not None
