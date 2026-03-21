"""
FastAPI приложение: фабрика, lifespan, middleware, роутеры.
"""

import logging
import traceback
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.middleware.org_access import OrgAccessMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.tenant import TenantMiddleware

logger = logging.getLogger(__name__)


def _configure_logging(settings: Settings) -> None:
    """Настроить логирование с JSON форматом в production."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    if settings.is_production:
        try:
            import structlog

            structlog.configure(
                processors=[
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.stdlib.add_log_level,
                    structlog.processors.JSONRenderer(),
                ],
                wrapper_class=structlog.BoundLogger,
                logger_factory=structlog.PrintLoggerFactory(),
            )
        except ImportError:
            logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    else:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


async def _ensure_db_partitions(settings: Settings) -> None:
    """
    Создать партиции для chat_messages, audit_log, error_log
    на текущий и следующий месяц если не существуют.
    """
    from datetime import date

    from sqlalchemy import text

    from app.database import get_engine

    engine = get_engine()

    today = date.today()
    months_to_create = []

    # Текущий месяц и следующий
    for month_offset in range(2):
        year = today.year
        month = today.month + month_offset
        if month > 12:
            month -= 12
            year += 1
        months_to_create.append((year, month))

    async with engine.begin() as conn:
        for year, month in months_to_create:
            # Определяем границы партиции
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, month + 1, 1)

            suffix = f"{year}_{month:02d}"

            for table in ("chat_messages", "audit_log", "error_log"):
                partition_name = f"{table}_{suffix}"
                sql = f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_class c
                            JOIN pg_namespace n ON n.oid = c.relnamespace
                            WHERE c.relname = '{partition_name}'
                        ) THEN
                            EXECUTE format(
                                'CREATE TABLE IF NOT EXISTS {partition_name}
                                 PARTITION OF {table}
                                 FOR VALUES FROM (%L) TO (%L)',
                                '{start}', '{end}'
                            );
                        END IF;
                    END;
                    $$;
                """
                try:
                    await conn.execute(text(sql))
                    logger.debug("Partition %s ensured", partition_name)
                except Exception:
                    logger.warning("Could not create partition %s (table may not exist yet)", partition_name)


async def _ensure_superadmin(settings: Settings) -> None:
    """
    Создать суперадмина если не существует.
    Вызывается при каждом старте — идемпотентно.
    """
    from sqlalchemy import select, text

    from app.database import get_session_factory
    from app.models.auth import Organization, User, UserCredentials
    from app.security.passwords import hash_password

    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
            # Advisory lock — только один воркер выполняет инициализацию
            await session.execute(text("SELECT pg_advisory_xact_lock(123456789)"))

            result = await session.execute(
                select(User).where(User.email == settings.SUPERADMIN_EMAIL.lower())
            )
            existing = result.scalar_one_or_none()

            if existing is not None:
                logger.debug("Superadmin already exists: %s", settings.SUPERADMIN_EMAIL)
                return

            # Создаём системную организацию для суперадмина
            result = await session.execute(
                select(Organization).where(Organization.slug == "system")
            )
            sys_org = result.scalar_one_or_none()

            if sys_org is None:
                sys_org = Organization(
                    name="System",
                    slug="system",
                    access_status="active",
                )
                session.add(sys_org)
                await session.flush()

            # Создаём пользователя
            superadmin = User(
                org_id=sys_org.id,
                email=settings.SUPERADMIN_EMAIL.lower(),
                username="superadmin",
                full_name="Super Admin",
                role="superadmin",
                is_active=True,
            )
            session.add(superadmin)
            await session.flush()

            credentials = UserCredentials(
                user_id=superadmin.id,
                password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
            )
            session.add(credentials)

    logger.info("Superadmin created: %s", settings.SUPERADMIN_EMAIL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Управление жизненным циклом приложения.

    Startup:
    1. Инициализация DB пула
    2. Инициализация Redis пула
    3. Проверка подключений
    4. Создание партиций таблиц
    5. Создание суперадмина
    6. Проверка SMTP (если настроен)

    Shutdown:
    - Закрытие всех пулов
    """
    settings = get_settings()
    _configure_logging(settings)

    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.ENVIRONMENT)

    # 1. Инициализируем БД
    from app.database import init_db

    init_db(settings)
    logger.info("Database pool initialized")

    # 1b. aiohttp ClientSession для AvitoAPIClient (создаётся один раз)
    import aiohttp

    aiohttp_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
    )
    logger.info("aiohttp ClientSession created")

    # 2. Инициализируем Redis
    from app.redis import init_redis

    init_redis(settings)
    logger.info("Redis pool initialized")

    # 3. Проверяем подключения
    from app.database import get_engine
    from app.redis import check_redis_connection

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection OK")
    except Exception:
        logger.critical("Database connection FAILED", exc_info=True)
        raise

    redis_ok = await check_redis_connection(settings)
    if redis_ok:
        logger.info("Redis connection OK")
    else:
        logger.warning("Redis connection FAILED — cache and sessions will not work")

    # 4. Создаём партиции
    try:
        await _ensure_db_partitions(settings)
        logger.info("Database partitions ensured")
    except Exception:
        logger.warning("Failed to ensure partitions", exc_info=True)

    # 5. Создаём суперадмина
    try:
        await _ensure_superadmin(settings)
    except Exception:
        logger.warning("Failed to ensure superadmin", exc_info=True)

    # 6. Проверяем SMTP
    if settings.SMTP_HOST:
        from app.services.email.smtp import SMTPService

        smtp = SMTPService(settings)
        smtp_ok = await smtp.test_connection()
        if smtp_ok:
            logger.info("SMTP connection OK")
        else:
            logger.warning("SMTP connection FAILED — email notifications will be disabled")

    # Инициализируем AvitoAPIClient и сохраняем в app.state
    from app.redis import get_pool
    from redis.asyncio import Redis
    from app.services.avito_client import AvitoAPIClient

    redis_for_avito = Redis(connection_pool=get_pool())
    avito_client = AvitoAPIClient(
        redis=redis_for_avito,
        encryption_key=settings.encryption_key_bytes,
    )
    avito_client.session = aiohttp_session
    app.state.avito_client = avito_client
    logger.info("AvitoAPIClient initialized")

    logger.info("%s started successfully", settings.APP_NAME)

    yield

    # Shutdown
    logger.info("Shutting down %s...", settings.APP_NAME)

    await aiohttp_session.close()
    logger.info("aiohttp ClientSession closed")

    from app.database import close_db
    from app.redis import close_redis

    await close_db()
    await close_redis()

    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Фабрика FastAPI приложения."""
    settings = get_settings()

    app = FastAPI(
        title="AvitoСRM API",
        version="1.0.0",
        description=(
            "REST API для мультитенантной CRM платформы на базе Avito. "
            "Управление кандидатами, рассылки, интеграция с Avito Messenger."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ---------------------------------------------------------------
    # Middleware (порядок важен — выполняется в обратном порядке добавления)
    # ---------------------------------------------------------------

    # CORS — должен быть первым (снаружи)
    cors_origins = (
        ["http://localhost", "http://localhost:1420", "tauri://localhost"]
        if settings.is_development
        else ["https://app.responscrm.ru"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=r"https?://localhost(:\d+)?$" if settings.is_development else None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Проверка доступности организации
    app.add_middleware(OrgAccessMiddleware)

    # Tenant context из JWT
    app.add_middleware(TenantMiddleware)

    # Request ID на каждый запрос
    app.add_middleware(RequestIDMiddleware)

    # ---------------------------------------------------------------
    # Роутеры
    # ---------------------------------------------------------------
    from app.routers.auth import router as auth_router
    from app.routers.candidates import router as candidates_router
    from app.routers.chat import router as chat_router
    from app.routers.tasks import router as tasks_router
    from app.routers.settings import router as settings_router

    # Phase 3
    from app.routers.avito_accounts import router as avito_accounts_router
    from app.routers.mailings import router as mailings_router
    from app.routers.webhooks import router as webhooks_router
    from app.routers.messaging import router as messaging_router
    from app.routers.ws import router as ws_router
    from app.routers.websocket import router as websocket_router

    # Phase 4
    from app.routers.analytics import router as analytics_router
    from app.routers.vacancies import router as vacancies_router
    from app.routers.self_employed import router as self_employed_router
    from app.routers.users import router as users_router
    from app.routers.superadmin import router as superadmin_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(candidates_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")

    # Phase 3 роутеры
    app.include_router(avito_accounts_router, prefix="/api/v1")
    app.include_router(mailings_router, prefix="/api/v1")
    app.include_router(webhooks_router, prefix="/api/v1")
    app.include_router(messaging_router, prefix="/api/v1")
    app.include_router(ws_router, prefix="/api/v1")
    app.include_router(websocket_router, prefix="/api/v1")

    # Phase 4 роутеры
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(vacancies_router, prefix="/api/v1")
    app.include_router(self_employed_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(superadmin_router, prefix="/api/v1")

    # ---------------------------------------------------------------
    # Health check
    # ---------------------------------------------------------------
    @app.get(
        "/health",
        tags=["system"],
        summary="Health check",
        include_in_schema=False,
    )
    async def health() -> dict:
        return {"status": "ok", "service": settings.APP_NAME}

    # ---------------------------------------------------------------
    # Глобальный обработчик ошибок
    # ---------------------------------------------------------------
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        org_id = getattr(request.state, "org_id", None)
        user_id = getattr(request.state, "user_id", None)

        logger.exception(
            "Unhandled exception (request_id=%s, path=%s)",
            request_id,
            request.url.path,
        )

        # Асинхронно пишем в error_log (не ждём — fire and forget)
        _write_error_log_async(
            request=request,
            exc=exc,
            org_id=org_id,
            user_id=user_id,
            request_id=request_id,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Внутренняя ошибка сервера",
                "request_id": request_id,
            },
        )

    return app


def _write_error_log_async(
    request: Request,
    exc: Exception,
    org_id: str | None,
    user_id: str | None,
    request_id: str | None,
) -> None:
    """
    Записать ошибку в error_log без блокировки ответа.
    Запускает задачу в фоне через asyncio.
    """
    import asyncio
    import uuid

    async def _write() -> None:
        try:
            from app.database import get_session_factory
            from app.models.error_log import ErrorLog

            factory = get_session_factory()
            async with factory() as session:
                from sqlalchemy import text

                await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

                error = ErrorLog(
                    org_id=uuid.UUID(org_id) if org_id else None,
                    user_id=uuid.UUID(user_id) if user_id else None,
                    source="api",
                    layer=type(exc).__module__,
                    handler=request.url.path,
                    request_method=request.method,
                    request_path=str(request.url.path),
                    request_id=request_id,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    stack_trace=traceback.format_exc(),
                    status_code=500,
                )
                session.add(error)
                await session.commit()
        except Exception:
            logger.exception("Failed to write error_log")

    asyncio.create_task(_write())


# Создаём экземпляр приложения
app = create_app()
