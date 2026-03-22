"""
AvitoAPIClient — HTTP клиент к Avito API.
Кеширует OAuth2 токены в Redis (TTL 23ч).
При 401 инвалидирует кеш и делает один повтор.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from app.models.avito import AvitoAccount
    from app.security.encryption import decrypt as _decrypt_fn

logger = logging.getLogger(__name__)


class AvitoAPIClient:
    """
    Клиент к Avito REST API.

    Создаётся один раз в lifespan приложения и хранится в app.state.
    Токены OAuth2 кешируются в Redis с TTL 23 часа.
    """

    BASE_URL = "https://api.avito.ru"

    def __init__(self, redis: "Redis", encryption_key: bytes) -> None:
        self._redis = redis
        self._enc_key = encryption_key
        self.session: aiohttp.ClientSession | None = None

    def _decrypt(self, value: str) -> str:
        from app.security.encryption import decrypt
        return decrypt(value, self._enc_key)

    async def _get_token(self, account: "AvitoAccount") -> str:
        """
        Получить OAuth2 токен для аккаунта.
        Кеш-ключ: avito_token:{org_id}:{account_id} TTL 23ч.
        """
        cache_key = f"avito_token:{account.org_id}:{account.id}"
        cached = await self._redis.get(cache_key)
        if cached:
            return cached if isinstance(cached, str) else cached.decode()

        return await self._fetch_token(account, cache_key)

    async def _fetch_token(self, account: "AvitoAccount", cache_key: str) -> str:
        """Запросить новый токен у Avito и сохранить в кеш."""
        client_id = self._decrypt(account.client_id_enc)
        client_secret = self._decrypt(account.client_secret_enc)

        assert self.session is not None, "aiohttp session not initialized"

        async with self.session.post(
            f"{self.BASE_URL}/token/",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        token: str = data["access_token"]
        await self._redis.setex(cache_key, 23 * 3600, token)
        return token

    async def _invalidate_token(self, account: "AvitoAccount") -> None:
        cache_key = f"avito_token:{account.org_id}:{account.id}"
        await self._redis.delete(cache_key)

    async def _request(
        self,
        method: str,
        path: str,
        account: "AvitoAccount",
        *,
        _retry: bool = True,
        **kwargs,
    ) -> dict:
        """
        Выполнить запрос к Avito API.
        При 401 инвалидирует токен и делает один повтор.
        """
        assert self.session is not None, "aiohttp session not initialized"

        token = await self._get_token(account)
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        async with self.session.request(
            method,
            f"{self.BASE_URL}{path}",
            headers=headers,
            **kwargs,
        ) as resp:
            if resp.status in (401, 403) and _retry:
                await self._invalidate_token(account)
                return await self._request(
                    method, path, account, _retry=False, **kwargs
                )

            if resp.status == 429:
                raise AvitoRateLimitError("Avito API rate limit exceeded")

            resp.raise_for_status()

            if resp.content_type == "application/json":
                return await resp.json()
            return {}

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def send_message(
        self,
        account: "AvitoAccount",
        chat_id: str,
        user_id: int,
        text: str,
    ) -> dict:
        """Отправить текстовое сообщение в чат."""
        return await self._request(
            "POST",
            f"/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages",
            account,
            json={"message": {"text": text}, "type": "text"},
        )

    async def send_file(
        self,
        account: "AvitoAccount",
        chat_id: str,
        user_id: int,
        file_data: bytes,
        content_type: str,
        filename: str,
    ) -> dict:
        """Отправить файл/изображение в чат."""
        form = aiohttp.FormData()
        form.add_field(
            "file",
            file_data,
            content_type=content_type,
            filename=filename,
        )
        return await self._request(
            "POST",
            f"/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages",
            account,
            data=form,
        )

    async def get_messages(
        self,
        account: "AvitoAccount",
        chat_id: str,
        user_id: int,
    ) -> list[dict]:
        """Получить историю сообщений чата."""
        data = await self._request(
            "GET",
            f"/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages/",
            account,
        )
        return data.get("messages", [])

    async def mark_chat_read(
        self,
        account: "AvitoAccount",
        chat_id: str,
        user_id: int,
    ) -> None:
        """Отметить чат как прочитанный."""
        await self._request(
            "POST",
            f"/messenger/v1/accounts/{user_id}/chats/{chat_id}/read",
            account,
        )

    async def block_user(
        self,
        account: "AvitoAccount",
        user_id: int,
        avito_user_id: int,
        item_id: int,
    ) -> None:
        """Заблокировать пользователя."""
        await self._request(
            "POST",
            f"/messenger/v1/accounts/{user_id}/blacklist",
            account,
            json={"user_id": avito_user_id, "item_id": item_id},
        )

    async def get_voice_url(
        self,
        account: "AvitoAccount",
        user_id: int,
        voice_id: str,
    ) -> str:
        """Получить URL голосового сообщения."""
        data = await self._request(
            "GET",
            f"/messenger/v1/accounts/{user_id}/voices/{voice_id}",
            account,
        )
        return data.get("url", "")

    async def get_user_info(
        self,
        account: "AvitoAccount",
        user_id: int,
        chat_id: str,
    ) -> dict:
        """Получить информацию о пользователе из чата."""
        data = await self._request(
            "GET",
            f"/messenger/v1/accounts/{user_id}/chats/{chat_id}",
            account,
        )
        return data

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    async def register_message_webhook(
        self,
        account: "AvitoAccount",
        url: str,
    ) -> None:
        """Зарегистрировать вебхук сообщений мессенджера Avito."""
        await self._request(
            "POST",
            "/messenger/v3/webhook",
            account,
            json={"url": url},
        )

    async def register_response_webhook(
        self,
        account: "AvitoAccount",
        url: str,
        secret: str,
    ) -> None:
        """Зарегистрировать вебхук откликов на вакансии Avito."""
        await self._request(
            "PUT",
            "/job/v1/applications/webhook",
            account,
            json={"url": url, "secret": secret},
        )

    # ------------------------------------------------------------------
    # Billing
    # ------------------------------------------------------------------

    async def get_balance(self, account: "AvitoAccount") -> dict:
        """Получить баланс аккаунта."""
        return await self._request(
            "GET",
            f"/core/v1/accounts/{account.avito_user_id}/balance/",
            account,
        )

    # ------------------------------------------------------------------
    # Items (объявления)
    # ------------------------------------------------------------------

    async def get_items(self, account: "AvitoAccount") -> list[dict]:
        """Выгрузить все объявления аккаунта (все статусы, с пагинацией)."""
        all_items: list[dict] = []
        per_page = 100
        page = 1

        while True:
            data = await self._request(
                "GET",
                f"/core/v1/accounts/{account.avito_user_id}/items",
                account,
                params={"per_page": per_page, "page": page},
            )
            resources = data.get("resources", [])
            all_items.extend(resources)

            meta = data.get("meta", {})
            total = meta.get("total", len(all_items))
            if len(all_items) >= total or len(resources) < per_page:
                break
            page += 1

        return all_items

    async def activate_item(self, account: "AvitoAccount", item_id: int) -> None:
        """Активировать объявление."""
        await self._request(
            "POST",
            f"/core/v1/accounts/{account.avito_user_id}/items/{item_id}/activate",
            account,
        )

    async def deactivate_item(self, account: "AvitoAccount", item_id: int) -> None:
        """Деактивировать объявление."""
        await self._request(
            "POST",
            f"/core/v1/accounts/{account.avito_user_id}/items/{item_id}/close",
            account,
        )

    async def verify_credentials_and_get_info(
        self,
        client_id: str,
        client_secret: str,
    ) -> dict:
        """
        Проверить учётные данные и получить информацию о пользователе Avito.
        Возвращает dict с полями id (avito_user_id) и name.
        Поднимает ValueError если credentials неверны.
        """
        assert self.session is not None, "aiohttp session not initialized"

        async with self.session.post(
            f"{self.BASE_URL}/token/",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        ) as resp:
            if not resp.ok:
                raise ValueError("Неверные client_id или client_secret")
            token_data = await resp.json()

        token = token_data["access_token"]

        async with self.session.get(
            f"{self.BASE_URL}/core/v1/accounts/self",
            headers={"Authorization": f"Bearer {token}"},
        ) as resp:
            if not resp.ok:
                raise ValueError("Не удалось получить информацию об аккаунте Avito")
            return await resp.json()

    # ------------------------------------------------------------------
    # Self-employed (самозанятые)
    # ------------------------------------------------------------------

    async def get_self_employed_status(self, inn: str) -> dict:
        """
        Проверить статус самозанятого по ИНН через API налоговой.
        Внешний API, не требует авторизации Avito.
        """
        assert self.session is not None, "aiohttp session not initialized"

        url = "https://statusnpd.nalog.ru/api/v1/tracker/taxpayer_status"
        async with self.session.post(
            url,
            json={"inn": inn, "requestDate": ""},
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return {"status": "unknown", "inn": inn}


class AvitoRateLimitError(Exception):
    """Avito API вернул 429 Too Many Requests."""
