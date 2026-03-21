"""
CacheService — read-through кеш через Redis с orjson сериализацией.
Поддерживает write-behind буферизацию для chat_metadata и candidate flags.
"""

import logging
import uuid
from typing import Any

import orjson
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class CacheService:
    """
    Сервис кеширования на базе Redis.

    Использует orjson для быстрой (де)сериализации.
    Паттерн scan_iter вместо KEYS — не блокирует Redis.
    """

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    # -----------------------------------------------------------------------
    # Кандидаты
    # -----------------------------------------------------------------------

    async def get_candidates_list(
        self, org_id: uuid.UUID, filters_hash: str, page: int
    ) -> list | None:
        return await self._get(f"candidates:{org_id}:{filters_hash}:{page}")

    async def set_candidates_list(
        self, org_id: uuid.UUID, filters_hash: str, page: int, data: list
    ) -> None:
        await self._set(f"candidates:{org_id}:{filters_hash}:{page}", data, ttl=30)

    async def invalidate_candidates(self, org_id: uuid.UUID) -> None:
        """Удалить все кешированные страницы кандидатов организации."""
        pattern = f"candidates:{org_id}:*"
        async for key in self.redis.scan_iter(match=pattern, count=100):
            await self.redis.delete(key)

    # -----------------------------------------------------------------------
    # Настройки организации
    # -----------------------------------------------------------------------

    async def get_org_settings(self, org_id: uuid.UUID) -> dict | None:
        return await self._get(f"org:{org_id}:settings")

    async def set_org_settings(self, org_id: uuid.UUID, data: dict) -> None:
        await self._set(f"org:{org_id}:settings", data, ttl=600)

    async def invalidate_org_settings(self, org_id: uuid.UUID) -> None:
        await self.redis.delete(f"org:{org_id}:settings")

    async def get_org_filters(self, org_id: uuid.UUID) -> dict | None:
        return await self._get(f"org:{org_id}:filters")

    async def set_org_filters(self, org_id: uuid.UUID, data: dict) -> None:
        await self._set(f"org:{org_id}:filters", data, ttl=300)

    async def invalidate_org_filters(self, org_id: uuid.UUID) -> None:
        await self.redis.delete(f"org:{org_id}:filters")

    async def invalidate_org_all(self, org_id: uuid.UUID) -> None:
        """Инвалидировать все кеши настроек и фильтров организации."""
        await self.invalidate_org_settings(org_id)
        await self.invalidate_org_filters(org_id)

    # -----------------------------------------------------------------------
    # Сообщения чата
    # -----------------------------------------------------------------------

    async def get_chat_messages(self, chat_id: str, page: int) -> list | None:
        return await self._get(f"chat_msgs:{chat_id}:{page}")

    async def set_chat_messages(self, chat_id: str, page: int, data: list) -> None:
        await self._set(f"chat_msgs:{chat_id}:{page}", data, ttl=180)

    async def invalidate_chat(self, chat_id: str) -> None:
        """Удалить все кешированные страницы истории чата."""
        pattern = f"chat_msgs:{chat_id}:*"
        async for key in self.redis.scan_iter(match=pattern, count=100):
            await self.redis.delete(key)

    # -----------------------------------------------------------------------
    # Write-behind буфер
    # -----------------------------------------------------------------------

    async def wb_update_chat_meta(self, chat_id: str, data: dict) -> None:
        """
        Обновить метаданные чата в Redis write-behind буфере.
        Воркер flush_write_behind смывает данные в PostgreSQL каждые 5 секунд.
        """
        str_data = {k: str(v) if v is not None else "" for k, v in data.items()}
        await self.redis.hset(f"wb:chat_meta:{chat_id}", mapping=str_data)
        await self.redis.sadd("wb:chat_meta:dirty", chat_id)

    async def wb_update_candidate_flags(
        self, candidate_id: uuid.UUID, data: dict
    ) -> None:
        """
        Обновить флаги кандидата в Redis write-behind буфере.
        """
        str_data = {k: str(v) if v is not None else "" for k, v in data.items()}
        await self.redis.hset(
            f"wb:candidate:{candidate_id}:flags", mapping=str_data
        )
        await self.redis.sadd("wb:candidate:dirty", str(candidate_id))

    # -----------------------------------------------------------------------
    # Внутренние методы
    # -----------------------------------------------------------------------

    async def _get(self, key: str) -> Any | None:
        try:
            raw = await self.redis.get(key)
            if raw is None:
                return None
            return orjson.loads(raw)
        except Exception:
            logger.warning("Cache GET error for key=%s", key, exc_info=True)
            return None

    async def _set(self, key: str, data: Any, ttl: int) -> None:
        try:
            await self.redis.setex(
                key, ttl, orjson.dumps(data, default=str)
            )
        except Exception:
            logger.warning("Cache SET error for key=%s", key, exc_info=True)
