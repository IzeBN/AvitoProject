"""
AuditService — fire-and-forget запись в журнал аудита.
"""

import asyncio
import logging
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """
    Сервис записи действий пользователей в журнал аудита.

    Все записи выполняются асинхронно через create_task (fire-and-forget).
    Данные пользователя берутся из request.state, установленного TenantMiddleware.
    """

    def __init__(self, db: AsyncSession, request: Request) -> None:
        self._db = db
        self._request = request

    def _get_ip(self) -> str | None:
        """Определить IP с учётом proxy (X-Forwarded-For)."""
        forwarded_for = self._request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Берём первый IP из цепочки (оригинальный клиент)
            return forwarded_for.split(",")[0].strip()
        if self._request.client:
            return self._request.client.host
        return None

    async def log(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        entity_display: str = "",
        details: dict | None = None,
        human_readable: str,
        related_entity_type: str | None = None,
        related_entity_id: uuid.UUID | None = None,
        related_entity_display: str | None = None,
    ) -> None:
        """
        Записать событие в audit_log.

        Запускается через asyncio.create_task — не блокирует текущий запрос.
        """
        if details is None:
            details = {}

        # Снимаем данные из request.state прямо сейчас (до переключения контекста)
        state = self._request.state
        org_id: uuid.UUID | None = getattr(state, "org_id", None)
        user_id: uuid.UUID | None = getattr(state, "user_id", None)
        user_full_name: str | None = getattr(state, "user_full_name", None)
        user_role: str | None = getattr(state, "user_role", None)
        request_id: str | None = getattr(state, "request_id", None)

        ip_address = self._get_ip()
        user_agent = self._request.headers.get("User-Agent", "")[:500]

        if org_id is None:
            logger.warning("AuditService.log called without org_id in request.state")
            return

        asyncio.create_task(
            self._write(
                org_id=org_id,
                user_id=user_id,
                user_full_name=user_full_name,
                user_role=user_role,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_display=entity_display,
                details=details,
                human_readable=human_readable,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
                related_entity_display=related_entity_display,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
            )
        )

    async def _write(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID | None,
        user_full_name: str | None,
        user_role: str | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
        entity_display: str,
        details: dict,
        human_readable: str,
        related_entity_type: str | None,
        related_entity_id: uuid.UUID | None,
        related_entity_display: str | None,
        ip_address: str | None,
        user_agent: str | None,
        request_id: str | None,
    ) -> None:
        """Записать запись аудита в отдельной сессии БД."""
        try:
            from app.database import get_session_factory
            from sqlalchemy import text

            factory = get_session_factory()
            async with factory() as session:
                # Обходим RLS для записи в аудит
                await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

                entry = AuditLog(
                    org_id=org_id,
                    user_id=user_id,
                    user_full_name=user_full_name,
                    user_role=user_role,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_display=entity_display or "",
                    details=details,
                    human_readable=human_readable,
                    related_entity_type=related_entity_type,
                    related_entity_id=related_entity_id,
                    related_entity_display=related_entity_display,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id,
                )
                session.add(entry)
                await session.commit()

        except Exception:
            logger.exception(
                "Failed to write audit log: action=%s entity=%s/%s",
                action,
                entity_type,
                entity_id,
            )
