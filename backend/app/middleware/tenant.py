"""
Tenant middleware: декодирует JWT и устанавливает RLS контекст.

Для каждого аутентифицированного запроса:
1. Декодирует Bearer токен из Authorization заголовка
2. Сохраняет user_id, org_id, role в request.state
3. Не устанавливает RLS здесь — это делается в get_db() dependency
   через set_rls_org(), так как RLS нужен SET LOCAL внутри транзакции.

Пропускает без авторизации:
- /api/v1/auth/* — публичные auth endpoints
- /webhooks/* — вебхуки Avito (имеют свою авторизацию через токен)
- /health — healthcheck
- /api/docs, /api/redoc, /api/openapi.json — документация
"""

from app.config import get_settings
from app.security.jwt import JWTService

import logging

from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Пути, которые не требуют JWT авторизации
EXEMPT_PREFIXES = (
    "/api/v1/auth/",
    "/webhooks/",
    "/api/v1/webhooks/",  # Avito webhooks (Phase 3)
    "/health",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Извлекает JWT из Authorization заголовка и заполняет request.state.
    Не блокирует запрос — отсутствие токена обрабатывается в dependencies.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # WebSocket — пропускаем, WS роутер сам делает аутентификацию
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        # Инициализируем state дефолтными значениями
        request.state.user_id = None
        request.state.org_id = None
        request.state.role = None
        request.state.is_authenticated = False

        # Пропускаем exempt пути
        path = request.url.path
        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return await call_next(request)

        # Извлекаем Bearer токен
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return await call_next(request)

        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            return await call_next(request)

        # Декодируем токен
        try:

            settings = get_settings()
            jwt_service = JWTService(settings)
            payload = jwt_service.decode_access_token(token)

            request.state.user_id = payload.sub
            request.state.org_id = payload.org_id
            request.state.role = payload.role
            request.state.is_authenticated = True

        except JWTError:
            # Невалидный токен — просто не ставим is_authenticated
            # Эндпоинты сами решат, нужна ли авторизация
            pass
        except Exception:
            logger.exception("Unexpected error in TenantMiddleware")

        return await call_next(request)
