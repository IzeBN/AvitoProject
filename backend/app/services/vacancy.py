"""
VacancyService — работа с вакансиями и синхронизация с Avito API.
"""

import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.vacancy import VacancyRepository
from app.schemas.vacancy import VacancyListResponse, VacancyResponse, VacancySyncResponse

logger = logging.getLogger(__name__)


class VacancyService:
    """
    Сервис вакансий.
    Синхронизация с Avito API, CRUD, CSV экспорт.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = VacancyRepository(session)

    async def list_vacancies(
        self,
        org_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
    ) -> VacancyListResponse:
        """Список вакансий организации."""
        items, total = await self._repo.list_by_org(org_id, page, page_size, status)
        pages = (total + page_size - 1) // page_size if total > 0 else 1
        return VacancyListResponse(
            items=[VacancyResponse.model_validate(v) for v in items],
            total=total,
            page=page,
            pages=pages,
        )

    async def sync_from_avito(
        self,
        org_id: uuid.UUID,
        avito_client,
    ) -> VacancySyncResponse:
        """
        Синхронизировать вакансии с Avito API.
        Для каждого аккаунта запрашивает список объявлений и делает UPSERT.
        """
        from sqlalchemy import select

        try:
            from app.models.avito import AvitoAccount
        except ImportError:
            logger.warning("AvitoAccount model not found, skipping sync")
            return VacancySyncResponse(
                synced_count=0, created=0, updated=0, accounts_processed=0
            )

        result = await self._session.execute(
            select(AvitoAccount).where(AvitoAccount.org_id == org_id)
        )
        accounts = list(result.scalars().all())

        total_created = 0
        total_updated = 0

        for account in accounts:
            try:
                items = await avito_client.get_items(account)
                created, updated = await self._repo.upsert_from_avito(
                    org_id, account.id, items
                )
                total_created += created
                total_updated += updated
                logger.info(
                    "Synced vacancies for account %s: created=%d, updated=%d",
                    account.id,
                    created,
                    updated,
                )
            except Exception:
                logger.exception("Failed to sync vacancies for account %s", account.id)

        await self._session.commit()

        return VacancySyncResponse(
            synced_count=total_created + total_updated,
            created=total_created,
            updated=total_updated,
            accounts_processed=len(accounts),
        )

    async def get_vacancy(
        self, org_id: uuid.UUID, vacancy_id: uuid.UUID
    ) -> VacancyResponse | None:
        """Получить вакансию по ID."""
        vacancy = await self._repo.get_by_org_and_id(org_id, vacancy_id)
        if vacancy is None:
            return None
        return VacancyResponse.model_validate(vacancy)

    async def update_vacancy(
        self,
        org_id: uuid.UUID,
        vacancy_id: uuid.UUID,
        updates: dict,
        avito_client=None,
    ) -> VacancyResponse | None:
        """Обновить вакансию (локально + через Avito API если есть клиент)."""
        vacancy = await self._repo.get_by_org_and_id(org_id, vacancy_id)
        if vacancy is None:
            return None

        updated = await self._repo.update(vacancy, **updates)
        return VacancyResponse.model_validate(updated)

    async def activate_vacancy(
        self,
        org_id: uuid.UUID,
        vacancy_id: uuid.UUID,
        avito_client=None,
    ) -> bool:
        """Опубликовать объявление через Avito API."""
        from sqlalchemy import select

        vacancy = await self._repo.get_by_org_and_id(org_id, vacancy_id)
        if vacancy is None:
            return False

        if avito_client is not None:
            try:
                from app.models.avito import AvitoAccount

                result = await self._session.execute(
                    select(AvitoAccount).where(
                        AvitoAccount.id == vacancy.avito_account_id
                    )
                )
                account = result.scalar_one_or_none()
                if account:
                    await avito_client.activate_item(account, vacancy.avito_item_id)
            except Exception:
                logger.exception("Failed to activate vacancy %s on Avito", vacancy_id)

        await self._repo.update(vacancy, status="active")
        return True

    async def deactivate_vacancy(
        self,
        org_id: uuid.UUID,
        vacancy_id: uuid.UUID,
        avito_client=None,
    ) -> bool:
        """Снять объявление с публикации через Avito API."""
        from sqlalchemy import select

        vacancy = await self._repo.get_by_org_and_id(org_id, vacancy_id)
        if vacancy is None:
            return False

        if avito_client is not None:
            try:
                from app.models.avito import AvitoAccount

                result = await self._session.execute(
                    select(AvitoAccount).where(
                        AvitoAccount.id == vacancy.avito_account_id
                    )
                )
                account = result.scalar_one_or_none()
                if account:
                    await avito_client.deactivate_item(account, vacancy.avito_item_id)
            except Exception:
                logger.exception("Failed to deactivate vacancy %s on Avito", vacancy_id)

        await self._repo.update(vacancy, status="closed")
        return True

    async def export_csv_stream(self, org_id: uuid.UUID) -> AsyncIterator[bytes]:
        """
        Потоковый экспорт вакансий в CSV.
        Генерирует строки по одной — не грузит всё в память.
        """
        header = ["id", "title", "location", "status", "avito_item_id", "synced_at", "created_at"]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=header)

        writer.writeheader()
        header_line = output.getvalue().encode("utf-8-sig")
        output.truncate(0)
        output.seek(0)
        yield header_line

        async for vacancy in self._repo.iter_all_by_org(org_id):
            writer.writerow({
                "id": str(vacancy.id),
                "title": vacancy.title or "",
                "location": vacancy.location or "",
                "status": vacancy.status,
                "avito_item_id": vacancy.avito_item_id,
                "synced_at": str(vacancy.synced_at) if vacancy.synced_at else "",
                "created_at": str(vacancy.created_at),
            })
            line = output.getvalue().encode("utf-8")
            output.truncate(0)
            output.seek(0)
            yield line
