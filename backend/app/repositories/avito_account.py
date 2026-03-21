"""
AvitoAccountRepository — доступ к данным Avito аккаунтов и вебхук эндпоинтов.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.avito import AvitoAccount, AvitoWebhookEndpoint


class AvitoAccountRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_all(self, org_id: uuid.UUID) -> list[AvitoAccount]:
        result = await self._db.execute(
            select(AvitoAccount)
            .where(AvitoAccount.org_id == org_id)
            .order_by(AvitoAccount.created_at)
        )
        return list(result.scalars().all())

    async def get_all_with_webhooks(self, org_id: uuid.UUID) -> list[AvitoAccount]:
        result = await self._db.execute(
            select(AvitoAccount)
            .options(selectinload(AvitoAccount.webhook_endpoints))
            .where(AvitoAccount.org_id == org_id)
            .order_by(AvitoAccount.created_at)
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, org_id: uuid.UUID, account_id: uuid.UUID
    ) -> AvitoAccount | None:
        result = await self._db.execute(
            select(AvitoAccount)
            .where(
                AvitoAccount.org_id == org_id,
                AvitoAccount.id == account_id,
                AvitoAccount.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_org(
        self, org_id: uuid.UUID, account_id: uuid.UUID
    ) -> AvitoAccount | None:
        """Получить аккаунт по ID без фильтрации по is_active (для admin-операций)."""
        result = await self._db.execute(
            select(AvitoAccount).where(
                AvitoAccount.org_id == org_id,
                AvitoAccount.id == account_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_webhooks(
        self, org_id: uuid.UUID, account_id: uuid.UUID
    ) -> AvitoAccount | None:
        result = await self._db.execute(
            select(AvitoAccount)
            .options(selectinload(AvitoAccount.webhook_endpoints))
            .where(
                AvitoAccount.org_id == org_id,
                AvitoAccount.id == account_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, account: AvitoAccount) -> AvitoAccount:
        self._db.add(account)
        await self._db.flush()
        await self._db.refresh(account)
        return account

    async def delete(self, account: AvitoAccount) -> None:
        await self._db.delete(account)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Webhook endpoints
    # ------------------------------------------------------------------

    async def get_by_avito_user_id(
        self, avito_user_id: int
    ) -> AvitoAccount | None:
        """Найти активный аккаунт по avito_user_id (для webhook роутера)."""
        result = await self._db.execute(
            select(AvitoAccount).where(
                AvitoAccount.avito_user_id == avito_user_id,
                AvitoAccount.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_webhook_by_token(
        self, token: str
    ) -> AvitoWebhookEndpoint | None:
        result = await self._db.execute(
            select(AvitoWebhookEndpoint).where(
                AvitoWebhookEndpoint.account_token == token,
                AvitoWebhookEndpoint.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def upsert_webhook_endpoint(
        self,
        endpoint: AvitoWebhookEndpoint,
    ) -> AvitoWebhookEndpoint:
        self._db.add(endpoint)
        await self._db.flush()
        await self._db.refresh(endpoint)
        return endpoint

    async def get_endpoints_for_account(
        self, account_id: uuid.UUID
    ) -> list[AvitoWebhookEndpoint]:
        result = await self._db.execute(
            select(AvitoWebhookEndpoint).where(
                AvitoWebhookEndpoint.avito_account_id == account_id,
            )
        )
        return list(result.scalars().all())
