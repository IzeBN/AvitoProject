"""
ARQ обработчики вебхуков Avito.
4 строго изолированных хендлера:
  - handle_new_response
  - handle_new_message
  - handle_message_read
  - handle_chat_blocked
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def handle_new_response(
    ctx: dict,
    org_id: str,
    avito_account_id: str,
    payload: dict,
) -> None:
    """
    Новый отклик от Avito.
    1. Расшифровать phone из payload если есть
    2. Upsert candidate (ON CONFLICT org_id, chat_id)
    3. Создать chat_metadata запись
    4. Проверить auto_response_rules для item_id
    5. Если есть активное правило — enqueue send_auto_response
    6. WebSocket broadcast: {type: 'new_candidate', candidate_id}
    7. Инвалидировать кеш: candidates:{org_id}:*, org:{org_id}:filters
    8. audit_log: action='candidate.created', source='webhook'
    """
    import uuid

    redis = ctx["redis"]
    session_factory = ctx["session_factory"]

    try:
        _org_id = uuid.UUID(org_id)
        _account_id = uuid.UUID(avito_account_id)

        chat_id: str = payload.get("chat_id", "")
        avito_user_id: int = payload.get("user_id", 0)
        avito_item_id: int = payload.get("item_id", 0)
        candidate_name: str = payload.get("name", "") or ""
        phone_raw: str | None = payload.get("phone")

        async with session_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

            from app.config import get_settings
            from app.security.encryption import compute_search_hash, encrypt

            settings = get_settings()
            enc_key = settings.encryption_key_bytes
            hash_key = settings.search_hash_key_bytes

            phone_enc: str | None = None
            phone_search_hash: str | None = None
            if phone_raw:
                phone_enc = encrypt(phone_raw, enc_key)
                phone_search_hash = compute_search_hash(phone_raw, hash_key)

            # Получаем department_id аккаунта для автоназначения
            dept_result = await session.execute(
                text("SELECT department_id FROM avito_accounts WHERE id = CAST(:account_id AS UUID)"),
                {"account_id": str(_account_id)},
            )
            dept_row = dept_result.fetchone()
            account_department_id = str(dept_row[0]) if dept_row and dept_row[0] else None

            # Upsert candidate
            candidate_result = await session.execute(
                text("""
                    INSERT INTO candidates (
                        org_id, avito_account_id, chat_id, avito_user_id, avito_item_id,
                        name, phone_enc, phone_search_hash, source, has_new_message,
                        department_id
                    ) VALUES (
                        CAST(:org_id AS UUID), CAST(:account_id AS UUID), :chat_id, :avito_user_id,
                        :avito_item_id, :name, :phone_enc, :phone_search_hash,
                        'avito', true,
                        CAST(NULLIF(:department_id, '') AS UUID)
                    )
                    ON CONFLICT (org_id, chat_id)
                    DO UPDATE SET
                        avito_user_id    = EXCLUDED.avito_user_id,
                        avito_item_id    = EXCLUDED.avito_item_id,
                        name             = COALESCE(EXCLUDED.name, candidates.name),
                        phone_enc        = COALESCE(EXCLUDED.phone_enc, candidates.phone_enc),
                        phone_search_hash = COALESCE(EXCLUDED.phone_search_hash, candidates.phone_search_hash),
                        has_new_message  = true,
                        updated_at       = now()
                    RETURNING id
                """),
                {
                    "org_id": str(_org_id),
                    "account_id": str(_account_id),
                    "chat_id": chat_id,
                    "avito_user_id": avito_user_id,
                    "avito_item_id": avito_item_id,
                    "name": candidate_name or None,
                    "phone_enc": phone_enc,
                    "phone_search_hash": phone_search_hash,
                    "department_id": account_department_id,
                },
            )
            row = candidate_result.fetchone()
            candidate_id = row[0] if row else None

            # Upsert chat_metadata
            if chat_id and candidate_id:
                await session.execute(
                    text("""
                        INSERT INTO chat_metadata (
                            org_id, candidate_id, chat_id, unread_count
                        ) VALUES (
                            CAST(:org_id AS UUID), CAST(:candidate_id AS UUID), :chat_id, 1
                        )
                        ON CONFLICT (chat_id) DO UPDATE SET
                            unread_count = chat_metadata.unread_count + 1,
                            updated_at   = now()
                    """),
                    {
                        "org_id": str(_org_id),
                        "candidate_id": str(candidate_id),
                        "chat_id": chat_id,
                    },
                )

            await session.commit()

        # Проверяем auto_response_rules
        if avito_item_id and avito_account_id:
            try:
                await _check_and_send_auto_response(
                    ctx, _org_id, _account_id, chat_id, avito_user_id, avito_item_id
                )
            except Exception:
                logger.exception(
                    "handle_new_response: auto_response error org=%s", org_id
                )

        # Инвалидация кеша
        async for key in redis.scan_iter(match=f"candidates:{org_id}:*", count=100):
            await redis.delete(key)
        await redis.delete(f"org:{org_id}:filters")

        # WebSocket broadcast
        if candidate_id:
            from app.routers.ws import ws_manager

            await ws_manager.broadcast_org(
                _org_id,
                {"type": "new_candidate", "candidate_id": str(candidate_id)},
            )

        # Audit log
        await _write_audit_log(
            session_factory,
            org_id=_org_id,
            action="candidate.created",
            entity_type="candidate",
            entity_id=candidate_id,
            details={"source": "webhook", "chat_id": chat_id},
        )

    except Exception:
        logger.exception(
            "handle_new_response: unhandled error org=%s account=%s",
            org_id,
            avito_account_id,
        )
        await _write_error_log(
            ctx,
            org_id=org_id,
            handler="handle_new_response",
            error_type="UnhandledError",
            payload=payload,
        )


async def handle_new_message(
    ctx: dict,
    org_id: str,
    avito_account_id: str,
    payload: dict,
) -> None:
    """
    Новое сообщение в чате.
    1. Найти candidate по (org_id, chat_id)
    2. INSERT chat_messages
    3. Write-behind: update chat_metadata (last_message, unread_count+1, last_message_at)
    4. Write-behind: candidate.has_new_message = True
    5. WebSocket broadcast: {type: 'new_message', ...}
    6. Инвалидировать кеш: chat_msgs:{chat_id}:*
    """
    import uuid

    redis = ctx["redis"]
    session_factory = ctx["session_factory"]

    try:
        _org_id = uuid.UUID(org_id)

        chat_id: str = payload.get("chat_id", "")
        message_text: str = payload.get("text", "") or ""
        message_type: str = payload.get("type", "text")
        avito_message_id: str = str(payload.get("id", ""))
        created_at_ts = payload.get("created", "")

        async with session_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

            # Найти candidate — если нет, создать (первое сообщение без отклика)
            cand_result = await session.execute(
                text("""
                    SELECT id FROM candidates
                    WHERE org_id = CAST(:org_id AS UUID) AND chat_id = :chat_id
                    LIMIT 1
                """),
                {"org_id": str(_org_id), "chat_id": chat_id},
            )
            cand_row = cand_result.fetchone()
            candidate_id = cand_row[0] if cand_row else None

            _account_id = uuid.UUID(avito_account_id)

            if candidate_id is None and chat_id:
                # Получаем department_id аккаунта
                dept_result = await session.execute(
                    text("SELECT department_id FROM avito_accounts WHERE id = CAST(:account_id AS UUID)"),
                    {"account_id": str(_account_id)},
                )
                dept_row = dept_result.fetchone()
                account_department_id = str(dept_row[0]) if dept_row and dept_row[0] else None

                # Upsert кандидата
                new_cand = await session.execute(
                    text("""
                        INSERT INTO candidates (
                            org_id, avito_account_id, chat_id, source,
                            has_new_message, department_id
                        ) VALUES (
                            CAST(:org_id AS UUID), CAST(:account_id AS UUID), :chat_id, 'avito',
                            true, CAST(NULLIF(:department_id, '') AS UUID)
                        )
                        ON CONFLICT (org_id, chat_id) DO UPDATE SET
                            has_new_message = true,
                            updated_at = now()
                        RETURNING id
                    """),
                    {
                        "org_id": str(_org_id),
                        "account_id": str(_account_id),
                        "chat_id": chat_id,
                        "department_id": account_department_id,
                    },
                )
                new_row = new_cand.fetchone()
                candidate_id = new_row[0] if new_row else None

                # Upsert chat_metadata
                if candidate_id:
                    await session.execute(
                        text("""
                            INSERT INTO chat_metadata (org_id, candidate_id, chat_id, unread_count)
                            VALUES (CAST(:org_id AS UUID), CAST(:candidate_id AS UUID), :chat_id, 1)
                            ON CONFLICT (chat_id) DO UPDATE SET
                                unread_count = chat_metadata.unread_count + 1,
                                updated_at = now()
                        """),
                        {"org_id": str(_org_id), "candidate_id": str(candidate_id), "chat_id": chat_id},
                    )

            # INSERT chat_messages
            if candidate_id and chat_id:
                await session.execute(
                    text("""
                        INSERT INTO chat_messages (
                            org_id, candidate_id, chat_id, avito_message_id,
                            content, message_type, author_type, created_at
                        ) VALUES (
                            CAST(:org_id AS UUID), CAST(:candidate_id AS UUID), :chat_id,
                            :avito_message_id, :content, :message_type, 'candidate',
                            COALESCE(CAST(:created_at AS TIMESTAMPTZ), now())
                        )
                        ON CONFLICT (avito_message_id)
                        WHERE avito_message_id IS NOT NULL
                        DO NOTHING
                    """),
                    {
                        "org_id": str(_org_id),
                        "candidate_id": str(candidate_id),
                        "chat_id": chat_id,
                        "avito_message_id": avito_message_id or None,
                        "content": message_text,
                        "message_type": message_type,
                        "created_at": created_at_ts or None,
                    },
                )

            await session.commit()

        # Write-behind: chat_metadata
        from app.services.cache import CacheService

        cache = CacheService(redis)
        await cache.wb_update_chat_meta(
            chat_id,
            {
                "last_message": message_text[:200],
                "unread_count": "increment",  # flush_write_behind обработает
                "last_message_at": created_at_ts,
            },
        )

        if candidate_id:
            await cache.wb_update_candidate_flags(
                candidate_id,
                {"has_new_message": "true"},
            )

        # Инвалидация кеша сообщений
        await cache.invalidate_chat(chat_id)

        # WebSocket broadcast
        from app.routers.ws import ws_manager

        if candidate_id:
            await ws_manager.broadcast_org(
                _org_id,
                {"type": "new_candidate", "candidate_id": str(candidate_id)},
            )
            await ws_manager.broadcast_org(
                _org_id,
                {
                    "type": "new_message",
                    "candidate_id": str(candidate_id),
                    "chat_id": chat_id,
                    "message": {"text": message_text, "type": message_type},
                },
            )

    except Exception:
        logger.exception(
            "handle_new_message: unhandled error org=%s", org_id
        )
        await _write_error_log(
            ctx,
            org_id=org_id,
            handler="handle_new_message",
            error_type="UnhandledError",
            payload=payload,
        )


async def handle_message_read(
    ctx: dict,
    org_id: str,
    avito_account_id: str,
    payload: dict,
) -> None:
    """
    Чат прочитан (кандидатом).
    1. Write-behind: chat_metadata.unread_count = 0
    2. WebSocket broadcast: {type: 'chat_read', chat_id}
    """
    import uuid

    redis = ctx["redis"]

    try:
        _org_id = uuid.UUID(org_id)
        chat_id: str = payload.get("chat_id", "")

        from app.services.cache import CacheService

        cache = CacheService(redis)
        await cache.wb_update_chat_meta(chat_id, {"unread_count": "0"})

        from app.routers.ws import ws_manager

        await ws_manager.broadcast_org(
            _org_id,
            {"type": "chat_read", "chat_id": chat_id},
        )

    except Exception:
        logger.exception(
            "handle_message_read: unhandled error org=%s", org_id
        )
        await _write_error_log(
            ctx,
            org_id=org_id,
            handler="handle_message_read",
            error_type="UnhandledError",
            payload=payload,
        )


async def handle_chat_blocked(
    ctx: dict,
    org_id: str,
    avito_account_id: str,
    payload: dict,
) -> None:
    """
    Пользователь заблокирован.
    1. UPDATE chat_metadata: is_blocked = True
    2. WebSocket broadcast: {type: 'chat_blocked', chat_id}
    """
    import uuid

    session_factory = ctx["session_factory"]

    try:
        _org_id = uuid.UUID(org_id)
        chat_id: str = payload.get("chat_id", "")

        async with session_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

            await session.execute(
                text("""
                    UPDATE chat_metadata
                    SET is_blocked = true, updated_at = now()
                    WHERE org_id = CAST(:org_id AS UUID) AND chat_id = :chat_id
                """),
                {"org_id": str(_org_id), "chat_id": chat_id},
            )
            await session.commit()

        from app.routers.ws import ws_manager

        await ws_manager.broadcast_org(
            _org_id,
            {"type": "chat_blocked", "chat_id": chat_id},
        )

    except Exception:
        logger.exception(
            "handle_chat_blocked: unhandled error org=%s", org_id
        )
        await _write_error_log(
            ctx,
            org_id=org_id,
            handler="handle_chat_blocked",
            error_type="UnhandledError",
            payload=payload,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

async def _check_and_send_auto_response(
    ctx: dict,
    org_id,
    account_id,
    chat_id: str,
    avito_user_id: int,
    item_id: int,
) -> None:
    """Проверить авто-ответ и поставить задачу в очередь если нужно."""
    session_factory = ctx["session_factory"]

    async with session_factory() as session:
        from sqlalchemy import text

        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

        result = await session.execute(
            text("""
                SELECT id FROM auto_response_rules
                WHERE org_id = CAST(:org_id AS UUID)
                  AND avito_account_id = CAST(:account_id AS UUID)
                  AND is_active = true
                  AND (avito_item_id = :item_id OR avito_item_id IS NULL)
                ORDER BY avito_item_id NULLS LAST
                LIMIT 1
            """),
            {
                "org_id": str(org_id),
                "account_id": str(account_id),
                "item_id": item_id,
            },
        )
        row = result.fetchone()

    if row:
        # Enqueue авто-ответ
        try:
            from arq.connections import ArqRedis
            from app.redis import get_arq_pool

            arq_pool = get_arq_pool()
            arq_redis = ArqRedis(pool_or_conn=arq_pool)
            await arq_redis.enqueue_job(
                "send_auto_response",
                str(org_id),
                str(account_id),
                chat_id,
                avito_user_id,
                item_id,
            )
        except Exception:
            logger.exception("_check_and_send_auto_response: enqueue failed")


async def _write_audit_log(
    session_factory,
    org_id,
    action: str,
    entity_type: str,
    entity_id,
    details: dict,
) -> None:
    try:
        from app.models.audit import AuditLog
        from sqlalchemy import text

        async with session_factory() as session:
            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
            entry = AuditLog(
                org_id=org_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_display="",
                details=details,
                human_readable=f"{action} via webhook",
            )
            session.add(entry)
            await session.commit()
    except Exception:
        logger.exception("_write_audit_log failed: action=%s", action)


async def _write_error_log(
    ctx: dict,
    org_id: str,
    handler: str,
    error_type: str,
    payload: dict,
) -> None:
    session_factory = ctx.get("session_factory")
    if not session_factory:
        return
    try:
        import uuid
        from app.models.error_log import ErrorLog
        from sqlalchemy import text

        async with session_factory() as session:
            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
            error = ErrorLog(
                org_id=uuid.UUID(org_id) if org_id else None,
                source="worker",
                layer="webhook_worker",
                handler=handler,
                error_type=error_type,
                error_message=str(payload)[:1000],
                status_code=0,
            )
            session.add(error)
            await session.commit()
    except Exception:
        logger.exception("_write_error_log failed in handler=%s", handler)
