"""
Webhook роутер — приём событий от Avito API.
Не требует JWT авторизации.
Всегда возвращает 200 (даже при ошибках — иначе Avito перестанет слать).

Эндпоинты содержат avito_user_id для мгновенной идентификации аккаунта:
  POST /webhooks/avito/messages/{avito_user_id}   — новые сообщения мессенджера
  POST /webhooks/avito/responses/{avito_user_id}  — отклики на вакансии
"""

from __future__ import annotations

import hashlib
import logging

import orjson
from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


def _body_hash(body: bytes) -> str:
    """Стабильный MD5-хеш тела запроса (не зависит от PYTHONHASHSEED)."""
    return hashlib.md5(body, usedforsecurity=False).hexdigest()[:24]


def _extract_message_uid(payload: dict, body: bytes) -> str:
    """
    Извлечь стабильный уникальный ключ события из message-хука.
    Avito кладёт ID сообщения в payload.payload.value.id.
    Fallback: MD5 тела запроса.
    """
    value = (payload.get("payload") or {}).get("value") or {}
    msg_id = (
        value.get("id")
        or payload.get("id")
        or payload.get("event_id")
    )
    if msg_id:
        return str(msg_id)
    # Для системных сообщений без id используем chat_id + тип + хеш
    chat_id = value.get("chat_id") or payload.get("chat_id") or ""
    msg_type = value.get("type") or ""
    if chat_id:
        return f"{chat_id}:{msg_type}:{_body_hash(body)}"
    return _body_hash(body)


async def _get_account_cached(
    avito_user_id: int,
    db: AsyncSession,
    redis: Redis,
) -> dict | None:
    """
    Получить данные аккаунта по avito_user_id.
    Кеш в Redis TTL 5 мин. Возвращает dict {org_id, avito_account_id}.
    """
    cache_key = f"webhook_account:{avito_user_id}"
    cached = await redis.get(cache_key)
    if cached:
        return orjson.loads(cached)

    from app.repositories.avito_account import AvitoAccountRepository
    repo = AvitoAccountRepository(db)
    account = await repo.get_by_avito_user_id(avito_user_id)
    if account is None:
        return None

    data = {
        "org_id": str(account.org_id),
        "avito_account_id": str(account.id),
    }
    await redis.setex(cache_key, 300, orjson.dumps(data))
    return data


async def _dedup(redis: Redis, key: str) -> bool:
    """Вернуть True если событие новое (SET NX EX 300)."""
    return bool(await redis.set(key, "1", nx=True, ex=300))


@router.post("/webhooks/avito/messages/{avito_user_id}", status_code=200)
async def avito_messages_webhook(
    avito_user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    """Принять вебхук новых сообщений мессенджера Avito."""
    try:
        body = await request.body()
        payload = orjson.loads(body) if body else {}
    except Exception:
        logger.warning("messages webhook: failed to parse body user_id=%s", avito_user_id)
        return {"ok": True}

    try:
        account_data = await _get_account_cached(avito_user_id, db, redis)
        if not account_data:
            logger.warning("messages webhook: unknown avito_user_id=%s", avito_user_id)
            return {"ok": True}

        event_uid = _extract_message_uid(payload, body)
        if not await _dedup(redis, f"webhook:dedup:msg:{avito_user_id}:{event_uid}"):
            logger.debug("messages webhook: duplicate event_uid=%s skipped", event_uid)
            return {"ok": True}

        arq_redis = request.app.state.arq_redis
        await arq_redis.enqueue_job(
            "handle_new_message",
            account_data["org_id"],
            account_data["avito_account_id"],
            payload,
        )

    except Exception:
        logger.exception("messages webhook: unhandled error user_id=%s", avito_user_id)

    return {"ok": True}


@router.post("/webhooks/avito/responses/{avito_user_id}", status_code=200)
async def avito_responses_webhook(
    avito_user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> dict:
    """Принять вебхук откликов на вакансии Avito."""
    try:
        body = await request.body()
        payload = orjson.loads(body) if body else {}
    except Exception:
        logger.warning("responses webhook: failed to parse body user_id=%s", avito_user_id)
        return {"ok": True}

    try:
        account_data = await _get_account_cached(avito_user_id, db, redis)
        if not account_data:
            logger.warning("responses webhook: unknown avito_user_id=%s", avito_user_id)
            return {"ok": True}

        apply_id = payload.get("applyId") or payload.get("apply_id")
        event_uid = str(apply_id) if apply_id else _body_hash(body)
        if not await _dedup(redis, f"webhook:dedup:resp:{avito_user_id}:{event_uid}"):
            logger.debug("responses webhook: duplicate apply_id=%s skipped", apply_id)
            return {"ok": True}

        arq_redis = request.app.state.arq_redis
        await arq_redis.enqueue_job(
            "handle_new_response",
            account_data["org_id"],
            account_data["avito_account_id"],
            payload,
        )

    except Exception:
        logger.exception("responses webhook: unhandled error user_id=%s", avito_user_id)

    return {"ok": True}
