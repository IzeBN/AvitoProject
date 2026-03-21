"""
WebSocket роутер — реал-тайм уведомления.
Аутентификация через query-параметр ?token=...
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Annotated

import orjson
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class WebSocketManager:
    """
    Менеджер WebSocket подключений.
    Хранит: {org_id: {user_id: WebSocket}}
    """

    def __init__(self) -> None:
        # org_id -> user_id -> WebSocket
        self._connections: dict[uuid.UUID, dict[uuid.UUID, WebSocket]] = {}

    async def connect(
        self, ws: WebSocket, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        await ws.accept()
        if org_id not in self._connections:
            self._connections[org_id] = {}
        self._connections[org_id][user_id] = ws
        logger.debug("WS connected: org=%s user=%s", org_id, user_id)

    def disconnect(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        org_conns = self._connections.get(org_id)
        if org_conns:
            org_conns.pop(user_id, None)
            if not org_conns:
                self._connections.pop(org_id, None)
        logger.debug("WS disconnected: org=%s user=%s", org_id, user_id)

    async def broadcast_org(self, org_id: uuid.UUID, data: dict) -> None:
        """Разослать сообщение всем подключённым пользователям организации."""
        org_conns = self._connections.get(org_id)
        if not org_conns:
            return

        payload = orjson.dumps(data).decode()
        dead: list[uuid.UUID] = []

        for user_id, ws in list(org_conns.items()):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(user_id)

        for user_id in dead:
            self.disconnect(org_id, user_id)

    async def send_to_user(self, user_id: uuid.UUID, data: dict) -> None:
        """Отправить сообщение конкретному пользователю."""
        for org_conns in self._connections.values():
            ws = org_conns.get(user_id)
            if ws:
                try:
                    await ws.send_text(orjson.dumps(data).decode())
                except Exception:
                    pass
                return


# Singleton — создаётся при импорте модуля
ws_manager = WebSocketManager()


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: Annotated[str, Query(description="JWT access token")],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> None:
    """
    WebSocket эндпоинт.
    Аутентификация через ?token=<jwt>.
    Пинг каждые 30 секунд для поддержания соединения.
    """
    # Аутентификация
    org_id: uuid.UUID
    user_id: uuid.UUID

    try:
        from app.config import get_settings
        from app.security.jwt import JWTService

        settings = get_settings()
        jwt_service = JWTService(settings)
        payload = jwt_service.decode_access_token(token)
        user_id = uuid.UUID(payload.sub)
        org_id = uuid.UUID(payload.org_id) if payload.org_id else None

        if org_id is None:
            await ws.close(code=4001, reason="Invalid token: missing org_id")
            return
    except Exception:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws_manager.connect(ws, org_id, user_id)

    ping_task = asyncio.create_task(_ping_loop(ws))

    try:
        while True:
            # Читаем входящие (клиент может присылать ping)
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WS error org=%s user=%s", org_id, user_id)
    finally:
        ping_task.cancel()
        ws_manager.disconnect(org_id, user_id)


async def _ping_loop(ws: WebSocket) -> None:
    """Отправлять ping каждые 30 секунд."""
    try:
        while True:
            await asyncio.sleep(30)
            await ws.send_text('{"type":"ping"}')
    except Exception:
        pass
