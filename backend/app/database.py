"""
Асинхронный движок SQLAlchemy с asyncpg.
Предоставляет session factory и утилиты для управления RLS.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings

# Движок и фабрика сессий инициализируются в lifespan
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine(settings: Settings) -> AsyncEngine:
    """Создать async SQLAlchemy engine с настройками пула."""
    return create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.DEBUG,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Создать фабрику сессий."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


def init_db(settings: Settings) -> None:
    """Инициализировать движок и фабрику сессий (вызывается в lifespan)."""
    global _engine, _session_factory
    _engine = create_engine(settings)
    _session_factory = create_session_factory(_engine)


async def close_db() -> None:
    """Закрыть пул соединений (вызывается при shutdown)."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def get_engine() -> AsyncEngine:
    """Получить текущий движок (для использования вне DI)."""
    if _engine is None:
        raise RuntimeError("Database engine is not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Получить фабрику сессий."""
    if _session_factory is None:
        raise RuntimeError("Session factory is not initialized. Call init_db() first.")
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — предоставляет сессию БД.
    Сессия автоматически закрывается после запроса.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def set_rls_org(session: AsyncSession, org_id: Any) -> None:
    """
    Установить org_id для RLS политик в рамках текущей транзакции.
    Вызывается для каждого запроса аутентифицированного пользователя.
    """
    # SET не принимает bound-параметры в PostgreSQL — подставляем UUID напрямую
    safe_org_id = str(org_id).replace("'", "")  # UUID contains only hex + dashes, safe
    await session.execute(text(f"SET LOCAL app.current_org_id = '{safe_org_id}'"))


async def set_rls_superadmin(session: AsyncSession) -> None:
    """
    Установить флаг суперадмина — обходит все RLS политики.
    Используется только для суперадмин операций.
    """
    await session.execute(
        text("SET LOCAL app.is_superadmin = 'true'"),
    )
