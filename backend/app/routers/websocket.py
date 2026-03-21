"""
WebSocket роутер — реал-тайм уведомления (упрощённый менеджер).

Аутентификация через query-параметр ?token=<jwt>.
Менеджер хранит: {org_id: set[WebSocket]}.

Экспортирует:
- manager: ConnectionManager
- broadcast_to_org(org_id, event_type, data) — вызывается из воркеров
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """
    Менеджер WebSocket подключений.

    Хранит: {org_id: set[WebSocket]}.
    Один пользователь может иметь несколько вкладок/подключений одновременно.
    """

    def __init__(self) -> None:
        # org_id (str) → множество активных WebSocket соединений
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, org_id: str) -> None:
        """Принять соединение и зарегистрировать в пуле организации."""
        await ws.accept()
        self._connections.setdefault(org_id, set()).add(ws)
        logger.debug("WS connected: org=%s total_conns=%d", org_id, len(self._connections[org_id]))

    def disconnect(self, ws: WebSocket, org_id: str) -> None:
        """Удалить соединение из пула организации."""
        if org_id in self._connections:
            self._connections[org_id].discard(ws)
            if not self._connections[org_id]:
                self._connections.pop(org_id, None)
        logger.debug("WS disconnected: org=%s", org_id)

    async def broadcast_to_org(self, org_id: str, message: dict) -> None:
        """
        Разослать сообщение всем подключённым пользователям организации.
        Мёртвые соединения удаляются автоматически.
        """
        conns = self._connections.get(org_id, set())
        if not conns:
            return

        dead: set[WebSocket] = set()
        for ws in list(conns):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)

        conns -= dead

        if dead and org_id in self._connections:
            self._connections[org_id] -= dead
            if not self._connections[org_id]:
                self._connections.pop(org_id, None)

    def connection_count(self, org_id: str) -> int:
        """Количество активных подключений для организации."""
        return len(self._connections.get(org_id, set()))


# Singleton — создаётся при импорте модуля
manager = ConnectionManager()


async def broadcast_to_org(org_id: str, event_type: str, data: dict) -> None:
    """
    Утилитарная функция для рассылки событий в организацию.
    Импортируется воркерами для отправки WS событий.

    Args:
        org_id: идентификатор организации (строка UUID)
        event_type: тип события ('new_message', 'mailing_progress', и т.д.)
        data: данные события

    Пример использования в воркере:
        from app.routers.websocket import broadcast_to_org
        await broadcast_to_org(str(org_id), "new_message", {"chat_id": "...", "message": {...}})
    """
    await manager.broadcast_to_org(
        org_id,
        {
            "type": event_type,
            "data": data,
            "ts": time.time(),
        },
    )


@router.websocket("/ws/v2")
async def websocket_endpoint(
    ws: WebSocket,
    token: Annotated[str, Query(description="JWT access токен")],
) -> None:
    """
    WebSocket эндпоинт (v2 — упрощённый менеджер).

    Аутентификация через ?token=<jwt>.
    Пинг каждые 30 секунд для поддержания соединения.

    Входящие сообщения:
    - {"type": "ping"} → {"type": "pong"}
    """
    org_id: str

    # Аутентификация
    try:
        from app.config import get_settings
        from app.security.jwt import JWTService

        settings = get_settings()
        jwt_service = JWTService(settings)
        payload = jwt_service.decode_access_token(token)

        if not payload.org_id:
            await ws.close(code=4001, reason="Unauthorized: missing org_id")
            return

        org_id = payload.org_id
    except Exception:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(ws, org_id)

    ping_task = asyncio.create_task(_ping_loop(ws))

    try:
        while True:
            try:
                data = await ws.receive_json()
            except Exception:
                # Клиент прислал не-JSON или соединение закрыто
                break

            if isinstance(data, dict) and data.get("type") == "ping":
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WS error org=%s", org_id)
    finally:
        ping_task.cancel()
        manager.disconnect(ws, org_id)


async def _ping_loop(ws: WebSocket) -> None:
    """Отправлять ping каждые 30 секунд для поддержания соединения."""
    try:
        while True:
            await asyncio.sleep(30)
            await ws.send_json({"type": "ping"})
    except Exception:
        pass
