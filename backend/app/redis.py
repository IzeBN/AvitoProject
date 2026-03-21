"""
Пул соединений Redis через redis.asyncio.
Отдельный пул для основного приложения и для ARQ.
"""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from app.config import Settings

# Основной пул для приложения
_pool: ConnectionPool | None = None

# Пул для ARQ (может использовать другой URL/DB)
_arq_pool: ConnectionPool | None = None


def init_redis(settings: Settings) -> None:
    """Инициализировать пул соединений Redis (вызывается в lifespan)."""
    global _pool, _arq_pool

    _pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=settings.REDIS_POOL_SIZE,
        decode_responses=True,
    )

    _arq_pool = ConnectionPool.from_url(
        settings.arq_redis_url,
        max_connections=10,
        decode_responses=True,
    )


async def close_redis() -> None:
    """Закрыть пулы соединений Redis (вызывается при shutdown)."""
    global _pool, _arq_pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None


def get_pool() -> ConnectionPool:
    """Получить основной пул Redis."""
    if _pool is None:
        raise RuntimeError("Redis pool is not initialized. Call init_redis() first.")
    return _pool


def get_arq_pool() -> ConnectionPool:
    """Получить пул Redis для ARQ."""
    if _arq_pool is None:
        raise RuntimeError("ARQ Redis pool is not initialized. Call init_redis() first.")
    return _arq_pool


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    FastAPI dependency — предоставляет Redis клиент из пула.
    Соединение возвращается в пул после запроса.
    """
    pool = get_pool()
    client: Redis = Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.aclose()


async def check_redis_connection(settings: Settings) -> bool:
    """Проверить доступность Redis (используется при старте)."""
    try:
        client: Redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False
