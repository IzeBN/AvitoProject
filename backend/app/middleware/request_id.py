"""
Middleware для добавления X-Request-ID к каждому запросу.
Если клиент прислал X-Request-ID — используется его значение,
иначе генерируется новый UUID.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Добавляет X-Request-ID к запросу и ответу.
    Сохраняет значение в request.state.request_id для логирования.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.scope.get("type") == "websocket":
            return await call_next(request)

        # Используем существующий ID или генерируем новый
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
