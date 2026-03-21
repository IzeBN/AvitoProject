"""
OrgAccess middleware: проверяет статус организации.

Алгоритм:
1. Если нет org_id в state (не аутентифицирован) — пропускаем
2. Суперадмины (role='superadmin') — пропускаем всегда
3. Читаем org_status:{org_id} из Redis (TTL 60s)
4. Если нет в кеше — читаем из БД и кешируем
5. suspended/expired → 403 с причиной
6. inactive → 403
"""

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

ORG_STATUS_CACHE_TTL = 60  # секунд
CACHE_KEY_PREFIX = "org_status:"

BLOCKED_STATUSES = {"suspended", "expired", "inactive"}

STATUS_MESSAGES = {
    "suspended": "Организация временно заблокирована. Обратитесь в поддержку.",
    "expired": "Подписка организации истекла. Обновите тарифный план.",
    "inactive": "Организация неактивна.",
}


class OrgAccessMiddleware(BaseHTTPMiddleware):
    """
    Проверяет доступность организации перед обработкой запроса.
    Статус кешируется в Redis на 60 секунд для снижения нагрузки на БД.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # WebSocket connections — BaseHTTPMiddleware не совместим с WS, пропускаем
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        org_id: str | None = getattr(request.state, "org_id", None)
        role: str | None = getattr(request.state, "role", None)

        # Не аутентифицирован или суперадмин — пропускаем
        if not org_id or role == "superadmin":
            return await call_next(request)

        try:
            status = await self._get_org_status(org_id, request)
        except Exception:
            logger.exception("Failed to check org status for org_id=%s", org_id)
            # При ошибке проверки — не блокируем, пропускаем
            return await call_next(request)

        if status in BLOCKED_STATUSES:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": STATUS_MESSAGES.get(status, "Доступ запрещён."),
                    "org_status": status,
                },
            )

        return await call_next(request)

    async def _get_org_status(self, org_id: str, request: Request) -> str:
        """
        Получить статус организации из кеша или БД.
        """
        from app.redis import get_pool
        from redis.asyncio import Redis

        cache_key = f"{CACHE_KEY_PREFIX}{org_id}"

        # Пробуем кеш
        pool = get_pool()
        redis: Redis = Redis(connection_pool=pool)
        try:
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return data["status"]

            # Кеш промах — читаем из БД
            status = await self._load_status_from_db(org_id)

            # Кешируем результат
            await redis.setex(
                cache_key,
                ORG_STATUS_CACHE_TTL,
                json.dumps({"status": status}),
            )
            return status
        finally:
            await redis.aclose()

    async def _load_status_from_db(self, org_id: str) -> str:
        """Загрузить статус организации из БД."""
        from sqlalchemy import select, text

        from app.database import get_session_factory
        from app.models.auth import Organization

        factory = get_session_factory()
        async with factory() as session:
            # Используем суперадмин режим для обхода RLS
            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
            result = await session.execute(
                select(Organization.access_status).where(
                    Organization.id == org_id
                )
            )
            row = result.scalar_one_or_none()
            # Если организация не найдена — считаем inactive
            return row if row is not None else "inactive"
