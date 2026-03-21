"""
SelfEmployedService — проверка самозанятых через API налоговой.
"""

import logging
import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.self_employed import SelfEmployedRepository
from app.schemas.self_employed import (
    SelfEmployedBulkResponse,
    SelfEmployedCheckResponse,
    SelfEmployedHistoryResponse,
    SelfEmployedHistoryItem,
)
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


def _map_nalog_status(raw: dict) -> str:
    """
    Перевести ответ налоговой в статус: 'active' | 'inactive' | 'not_found' | 'unknown'.
    """
    status = raw.get("status", "").lower()
    if status in ("taxpayer", "active", "registered"):
        return "active"
    if status in ("not_registered", "inactive", "closed"):
        return "inactive"
    if status == "not_found" or raw.get("code") == 404:
        return "not_found"
    return "unknown"


class SelfEmployedService:
    """
    Сервис проверки самозанятых.
    Одиночные проверки выполняются синхронно.
    Массовые — через ARQ очередь (fire-and-forget).
    """

    def __init__(
        self,
        session: AsyncSession,
        avito_client,
        request: Request,
    ) -> None:
        self._session = session
        self._avito_client = avito_client
        self._repo = SelfEmployedRepository(session)
        self._audit = AuditService(db=session, request=request)

    async def check_inn(
        self,
        org_id: uuid.UUID,
        inn: str,
        checked_by: uuid.UUID,
    ) -> SelfEmployedCheckResponse:
        """
        Проверить ИНН через API налоговой.
        Сохраняет результат в БД и записывает в audit_log.
        """
        try:
            raw_response = await self._avito_client.get_self_employed_status(inn)
            status = _map_nalog_status(raw_response)
        except Exception:
            logger.exception("Failed to check self-employed status for INN %s", inn)
            raw_response = {}
            status = "unknown"

        check = await self._repo.create_check(
            org_id=org_id,
            inn=inn,
            status=status,
            checked_by=checked_by,
            raw_response=raw_response,
        )
        await self._session.commit()

        await self._audit.log(
            action="self_employed.checked",
            entity_type="self_employed_check",
            entity_id=check.id,
            entity_display=inn,
            human_readable=f"Проверен статус самозанятого ИНН {inn}: {status}",
            details={"inn": inn, "status": status},
        )

        return SelfEmployedCheckResponse(
            inn=inn,
            status=status,
            checked_at=check.checked_at,
        )

    async def get_history(
        self,
        org_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> SelfEmployedHistoryResponse:
        """Получить историю проверок организации."""
        items, total = await self._repo.list_by_org(org_id, page, page_size)
        pages = (total + page_size - 1) // page_size if total > 0 else 1
        return SelfEmployedHistoryResponse(
            items=[SelfEmployedHistoryItem.model_validate(i) for i in items],
            total=total,
            page=page,
            pages=pages,
        )

    async def check_bulk(
        self,
        org_id: uuid.UUID,
        inns: list[str],
        checked_by: uuid.UUID,
    ) -> SelfEmployedBulkResponse:
        """
        Поставить в очередь ARQ массовую проверку ИНН.
        Не блокирует запрос — возвращает job_id сразу.
        """
        from app.redis import get_arq_pool
        from arq.connections import ArqRedis

        arq_pool_conn = get_arq_pool()
        arq_client = ArqRedis(pool_or_conn=arq_pool_conn)

        job_ids = []
        for inn in inns:
            job = await arq_client.enqueue_job(
                "check_self_employed_inn",
                org_id=str(org_id),
                inn=inn,
                checked_by=str(checked_by),
            )
            if job:
                job_ids.append(job.job_id)

        # Используем первый job_id как идентификатор группы
        group_job_id = job_ids[0] if job_ids else "unknown"

        return SelfEmployedBulkResponse(
            job_id=group_job_id,
            total=len(inns),
        )
