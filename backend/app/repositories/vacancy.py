"""
Репозиторий вакансий.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vacancy import Vacancy
from app.repositories.base import BaseRepository


class VacancyRepository(BaseRepository[Vacancy]):
    """Репозиторий для работы с вакансиями."""

    model = Vacancy

    async def list_by_org(
        self,
        org_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
    ) -> tuple[list[Vacancy], int]:
        """Получить вакансии организации с пагинацией."""
        base_q = select(Vacancy).where(Vacancy.org_id == org_id)
        count_q = select(func.count(Vacancy.id)).where(Vacancy.org_id == org_id)

        if status:
            base_q = base_q.where(Vacancy.status == status)
            count_q = count_q.where(Vacancy.status == status)

        total_result = await self._session.execute(count_q)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        items_result = await self._session.execute(
            base_q.order_by(Vacancy.created_at.desc()).offset(offset).limit(page_size)
        )
        items = list(items_result.scalars().all())

        return items, total

    async def upsert_from_avito(
        self,
        org_id: uuid.UUID,
        avito_account_id: uuid.UUID,
        items: list[dict],
    ) -> tuple[int, int]:
        """
        UPSERT вакансий из Avito API.
        Возвращает (created_count, updated_count).
        """
        if not items:
            return 0, 0

        now = datetime.now(timezone.utc)
        created = 0
        updated = 0

        for item in items:
            avito_item_id = item.get("id")
            if not avito_item_id:
                continue

            # Проверяем существование
            existing_result = await self._session.execute(
                select(Vacancy).where(
                    Vacancy.org_id == org_id,
                    Vacancy.avito_item_id == avito_item_id,
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing:
                existing.title = item.get("title") or existing.title
                existing.location = item.get("address") or existing.location
                existing.status = item.get("status", "active")
                existing.raw_data = item
                existing.synced_at = now
                self._session.add(existing)
                updated += 1
            else:
                vacancy = Vacancy(
                    org_id=org_id,
                    avito_account_id=avito_account_id,
                    avito_item_id=avito_item_id,
                    title=item.get("title"),
                    location=item.get("address"),
                    status=item.get("status", "active"),
                    raw_data=item,
                    synced_at=now,
                )
                self._session.add(vacancy)
                created += 1

        await self._session.flush()
        return created, updated

    async def get_by_org_and_id(
        self, org_id: uuid.UUID, vacancy_id: uuid.UUID
    ) -> Vacancy | None:
        """Получить вакансию организации по ID."""
        result = await self._session.execute(
            select(Vacancy).where(
                Vacancy.id == vacancy_id,
                Vacancy.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def iter_all_by_org(self, org_id: uuid.UUID):
        """
        Итератор по всем вакансиям организации для CSV экспорта.
        Использует yield для потоковой отдачи без загрузки всего в память.
        """
        result = await self._session.execute(
            select(Vacancy)
            .where(Vacancy.org_id == org_id)
            .order_by(Vacancy.created_at.desc())
        )
        for vacancy in result.scalars():
            yield vacancy
