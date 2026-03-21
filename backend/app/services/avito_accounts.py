"""
AvitoAccountService — бизнес-логика управления Avito аккаунтами.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from typing import TYPE_CHECKING

from app.models.avito import AvitoAccount, AvitoWebhookEndpoint
from app.repositories.avito_account import AvitoAccountRepository

if TYPE_CHECKING:
    from app.services.avito_client import AvitoAPIClient

logger = logging.getLogger(__name__)

WEBHOOK_EVENT_TYPES = [
    "messages",
    "responses",
]


class AvitoAccountService:
    def __init__(
        self,
        repo: AvitoAccountRepository,
        avito_client: "AvitoAPIClient",
        encryption_key: bytes,
        base_url: str = "",  # не используется, оставлен для совместимости
    ) -> None:
        from app.config import get_settings
        self._repo = repo
        self._client = avito_client
        self._enc_key = encryption_key
        self._base_url = get_settings().WEBHOOK_BASE_URL.rstrip("/")

    def _encrypt(self, value: str) -> str:
        from app.security.encryption import encrypt
        return encrypt(value, self._enc_key)

    async def list_accounts(self, org_id: uuid.UUID) -> list[AvitoAccount]:
        return await self._repo.get_all(org_id)

    async def create_account(
        self,
        org_id: uuid.UUID,
        client_id: str,
        client_secret: str,
    ) -> AvitoAccount:
        from fastapi import HTTPException, status

        # 1. Проверяем credentials и получаем данные аккаунта из Avito API
        try:
            user_info = await self._client.verify_credentials_and_get_info(
                client_id, client_secret
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Не удалось подключить аккаунт Avito: {exc}",
            ) from exc

        avito_user_id: int = user_info["id"]
        account_name: str = user_info.get("name") or f"Avito {avito_user_id}"

        # 2. Сохраняем аккаунт (flush, без commit)
        account = AvitoAccount(
            org_id=org_id,
            account_name=account_name,
            avito_user_id=avito_user_id,
            client_id_enc=self._encrypt(client_id),
            client_secret_enc=self._encrypt(client_secret),
        )
        account = await self._repo.create(account)

        # 3. Настраиваем вебхуки — если ошибка, откат (commit не был сделан)
        try:
            await self._register_webhooks_for_account(account, org_id)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Не удалось настроить вебхуки Avito: {exc}",
            ) from exc

        return account

    async def delete_account(
        self, org_id: uuid.UUID, account_id: uuid.UUID
    ) -> None:
        account = await self._repo.get_by_id(org_id, account_id)
        if account is None:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аккаунт не найден")
        await self._repo.delete(account)

    async def get_balance(
        self, org_id: uuid.UUID, account_id: uuid.UUID
    ) -> dict:
        account = await self._repo.get_by_id(org_id, account_id)
        if account is None:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аккаунт не найден")
        return await self._client.get_balance(account)

    async def setup_webhooks(
        self, org_id: uuid.UUID, account_id: uuid.UUID
    ) -> list[AvitoWebhookEndpoint]:
        """
        Регистрирует 2 вебхука: messages и responses.
        URL содержит avito_user_id для мгновенной идентификации аккаунта.
        """
        account = await self._repo.get_by_id_with_webhooks(org_id, account_id)
        if account is None:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Аккаунт не найден")

        return await self._register_webhooks_for_account(account, org_id)

    async def _register_webhooks_for_account(
        self,
        account: AvitoAccount,
        org_id: uuid.UUID,
    ) -> list[AvitoWebhookEndpoint]:
        """Регистрирует вебхуки messages+responses в Avito и сохраняет эндпоинты в БД."""
        existing_endpoints = await self._repo.get_endpoints_for_account(account.id)
        existing = {ep.event_type: ep for ep in existing_endpoints}

        result_endpoints: list[AvitoWebhookEndpoint] = []

        for event_type in WEBHOOK_EVENT_TYPES:
            # URL содержит avito_user_id — идентификация аккаунта без доп. вычислений
            webhook_url = (
                f"{self._base_url}/api/v1/webhooks/avito"
                f"/{event_type}/{account.avito_user_id}"
            )
            # secret — для подписи откликов
            token = secrets.token_urlsafe(48)

            if event_type in existing:
                endpoint = existing[event_type]
                endpoint.account_token = token
                endpoint.is_active = True
            else:
                endpoint = AvitoWebhookEndpoint(
                    org_id=org_id,
                    avito_account_id=account.id,
                    event_type=event_type,
                    account_token=token,
                    is_active=True,
                )

            await self._repo.upsert_webhook_endpoint(endpoint)

            try:
                if event_type == "messages":
                    await self._client.register_message_webhook(account, webhook_url)
                elif event_type == "responses":
                    await self._client.register_response_webhook(account, webhook_url, token)
            except Exception:
                logger.exception(
                    "Failed to register webhook event_type=%s account=%s",
                    event_type,
                    account.id,
                )

            result_endpoints.append(endpoint)

        return result_endpoints
