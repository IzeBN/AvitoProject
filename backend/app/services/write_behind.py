"""
WriteBehindFlusher — периодический сброс write-behind буферов из Redis в PostgreSQL.
Запускается как arq periodic task каждые 5 секунд.
"""

import logging

logger = logging.getLogger(__name__)


async def flush_write_behind(ctx: dict) -> None:
    """
    ARQ periodic task: смывает write-behind буферы chat_metadata и candidate flags в БД.

    ctx должен содержать:
        - 'redis': redis.asyncio.Redis
        - 'session_factory': async_sessionmaker
    """
    redis = ctx.get("redis")
    session_factory = ctx.get("session_factory")

    if redis is None or session_factory is None:
        logger.error("flush_write_behind: missing redis or session_factory in ctx")
        return

    await _flush_chat_metadata(redis, session_factory)
    await _flush_candidate_flags(redis, session_factory)


async def _flush_chat_metadata(redis, session_factory) -> None:
    """Смыть обновления chat_metadata из write-behind буфера в PostgreSQL."""
    dirty_chats = await redis.smembers("wb:chat_meta:dirty")
    if not dirty_chats:
        return

    updates = []
    for chat_id_bytes in dirty_chats:
        chat_id = (
            chat_id_bytes.decode() if isinstance(chat_id_bytes, bytes) else chat_id_bytes
        )
        data = await redis.hgetall(f"wb:chat_meta:{chat_id}")
        if data:
            decoded = {
                (k.decode() if isinstance(k, bytes) else k): (
                    v.decode() if isinstance(v, bytes) else v
                )
                for k, v in data.items()
            }
            decoded["chat_id"] = chat_id
            updates.append(decoded)

    if updates:
        try:
            async with session_factory() as session:
                from sqlalchemy import text

                await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

                for u in updates:
                    chat_id = u["chat_id"]
                    unread_raw = u.get("unread_count", "0")
                    # Пустая строка — сброс в 0
                    try:
                        unread = int(unread_raw) if unread_raw else 0
                    except (ValueError, TypeError):
                        unread = 0

                    last_message = u.get("last_message") or None
                    last_message_at_raw = u.get("last_message_at") or None
                    if last_message_at_raw:
                        try:
                            from datetime import datetime as _dt
                            last_message_at_raw = _dt.fromisoformat(last_message_at_raw)
                        except (ValueError, TypeError):
                            last_message_at_raw = None

                    stmt = text("""
                        UPDATE chat_metadata
                        SET last_message      = :last_message,
                            unread_count      = :unread_count,
                            last_message_at   = CAST(:last_message_at AS TIMESTAMPTZ),
                            updated_at        = now()
                        WHERE chat_id = :chat_id
                    """)
                    await session.execute(
                        stmt,
                        {
                            "last_message": last_message,
                            "unread_count": unread,
                            "last_message_at": last_message_at_raw or None,
                            "chat_id": chat_id,
                        },
                    )

                await session.commit()

            logger.debug(
                "flush_write_behind: flushed %d chat_metadata records", len(updates)
            )
        except Exception:
            logger.exception("flush_write_behind: error flushing chat_metadata")
            return  # Не чистим dirty set — попробуем снова на следующем такте

    # Очищаем dirty set и ключи хешей
    pipe = redis.pipeline()
    for chat_id_bytes in dirty_chats:
        chat_id = (
            chat_id_bytes.decode() if isinstance(chat_id_bytes, bytes) else chat_id_bytes
        )
        pipe.delete(f"wb:chat_meta:{chat_id}")
    pipe.delete("wb:chat_meta:dirty")
    await pipe.execute()


async def _flush_candidate_flags(redis, session_factory) -> None:
    """Смыть обновления флагов кандидатов из write-behind буфера в PostgreSQL."""
    dirty_candidates = await redis.smembers("wb:candidate:dirty")
    if not dirty_candidates:
        return

    updates = []
    for cid_bytes in dirty_candidates:
        cid = cid_bytes.decode() if isinstance(cid_bytes, bytes) else cid_bytes
        data = await redis.hgetall(f"wb:candidate:{cid}:flags")
        if data:
            decoded = {
                (k.decode() if isinstance(k, bytes) else k): (
                    v.decode() if isinstance(v, bytes) else v
                )
                for k, v in data.items()
            }
            decoded["candidate_id"] = cid
            updates.append(decoded)

    if updates:
        try:
            async with session_factory() as session:
                from sqlalchemy import text

                await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

                for u in updates:
                    candidate_id = u["candidate_id"]
                    has_new_msg_raw = u.get("has_new_message", "")
                    has_new_message = has_new_msg_raw.lower() in ("true", "1", "yes")

                    await session.execute(
                        text("""
                            UPDATE candidates
                            SET has_new_message = :has_new_message,
                                updated_at      = now()
                            WHERE id = CAST(:candidate_id AS UUID)
                        """),
                        {
                            "has_new_message": has_new_message,
                            "candidate_id": candidate_id,
                        },
                    )

                await session.commit()

            logger.debug(
                "flush_write_behind: flushed %d candidate flags", len(updates)
            )
        except Exception:
            logger.exception("flush_write_behind: error flushing candidate flags")
            return

    # Очищаем dirty set и ключи
    pipe = redis.pipeline()
    for cid_bytes in dirty_candidates:
        cid = cid_bytes.decode() if isinstance(cid_bytes, bytes) else cid_bytes
        pipe.delete(f"wb:candidate:{cid}:flags")
    pipe.delete("wb:candidate:dirty")
    await pipe.execute()
