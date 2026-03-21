"""
ARQ воркер: flush write-behind буферов chat_metadata и candidate flags.
Подключается к WorkerSettings в app/workers/settings.py.
"""

import logging

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    """Инициализация контекста воркера при старте."""
    import urllib.parse

    from redis.asyncio import Redis, ConnectionPool

    from app.config import get_settings
    from app.database import init_db, get_session_factory

    settings = get_settings()

    # Инициализируем БД если ещё не инициализирована
    try:
        get_session_factory()
    except RuntimeError:
        init_db(settings)

    ctx["session_factory"] = get_session_factory()

    # Отдельный Redis клиент для воркера
    pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=5,
        decode_responses=False,
    )
    ctx["redis"] = Redis(connection_pool=pool)

    logger.info("WriteBehind worker started")


async def shutdown(ctx: dict) -> None:
    """Закрытие ресурсов воркера."""
    redis = ctx.get("redis")
    if redis:
        await redis.aclose()
    logger.info("WriteBehind worker stopped")


async def flush_write_behind_task(ctx: dict) -> None:
    """
    ARQ periodic task — сброс write-behind буферов каждые 5 секунд.
    """
    from app.services.write_behind import flush_write_behind

    await flush_write_behind(ctx)
