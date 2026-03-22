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

# Системные сообщения с этими flow_id считаются откликами
_RESPONSE_FLOWS = {"job", "job_apply_enrichment"}

# Фразы в системном сообщении, подтверждающие отклик
_RESPONSE_TRIGGERS = ["кандидат откликнулся", "кандидат посмотрел ваш телефон"]


def _extract_message_content(value: dict) -> tuple[str, str]:
    """
    Вернуть (content_text, message_type) по payload value.
    Обрабатывает все типы: text, image, location, video, voice, call, link, system.
    """
    raw_type: str = value.get("type", "text") or "text"
    content: dict = value.get("content") or {}

    if raw_type == "text":
        text = content.get("text") or value.get("text") or ""
        return text, "text"

    if raw_type == "image":
        sizes = content.get("image", {}).get("sizes", {})
        url = sizes.get("1280x960") or sizes.get("640x480") or ""
        return url, "image"

    if raw_type == "location":
        text = content.get("location", {}).get("text") or "Геолокация"
        return text, "text"

    if raw_type == "video":
        return "Видео", "text"

    if raw_type == "voice":
        return "Голосовое сообщение", "text"

    if raw_type == "call":
        return "Вызов", "text"

    if raw_type == "link":
        link = content.get("link", {})
        url = link.get("url") or link.get("text") or "Ссылка"
        return url, "link"

    # file и прочие неизвестные типы
    text = content.get("text") or ""
    return text, "file"


def _last_message_preview(text: str, msg_type: str) -> str:
    """Возвращает человекочитаемый превью для last_message в чат-листе."""
    if msg_type == "image":
        return "📷 Фото"
    if msg_type == "voice":
        return "🎙 Голосовое"
    if msg_type == "file":
        return "📎 Файл"
    if msg_type == "link":
        return text[:200] if text else "🔗 Ссылка"
    return text[:200] if text else ""


async def handle_new_response(
    ctx: dict,
    org_id: str,
    avito_account_id: str,
    payload: dict,
) -> None:
    """
    Новый отклик от Avito (через /responses webhook).
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

        # Avito присылает вложенную структуру: {payload: {type: "...", value: {...}}}
        value = payload.get("payload", {}).get("value", payload)

        chat_id: str = value.get("chat_id", "") or payload.get("chat_id", "")
        avito_user_id: int = value.get("user_id", 0) or payload.get("user_id", 0)
        avito_item_id: int = value.get("item_id", 0) or payload.get("item_id", 0)
        candidate_name: str = value.get("name", "") or payload.get("name", "") or ""
        phone_raw: str | None = value.get("phone") or payload.get("phone")

        # --- Обогащение через Avito API по applyId ---
        apply_id: str | None = str(payload.get("applyId") or payload.get("apply_id") or "").strip() or None
        vacancy_title: str | None = None
        vacancy_location: str | None = None

        avito_client = ctx.get("avito_client")
        if apply_id and avito_client:
            try:
                async with session_factory() as _sess:
                    from sqlalchemy import text as _text
                    _acc_row = (await _sess.execute(
                        _text("SELECT client_id_enc, client_secret_enc, avito_user_id FROM avito_accounts WHERE id = CAST(:id AS UUID)"),
                        {"id": str(_account_id)},
                    )).fetchone()

                if _acc_row:
                    from app.models.avito import AvitoAccount as _AvitoAccount
                    _fake_account = _AvitoAccount.__new__(_AvitoAccount)
                    _fake_account.id = _account_id
                    _fake_account.org_id = _org_id
                    _fake_account.client_id_enc = _acc_row[0]
                    _fake_account.client_secret_enc = _acc_row[1]
                    _fake_account.avito_user_id = _acc_row[2]

                    app_data = await avito_client.get_application(_fake_account, apply_id)

                    applicant = app_data.get("applicant") or {}
                    contacts = app_data.get("contacts") or {}
                    vacancy_data = app_data.get("vacancy") or {}

                    # Имя кандидата (API надёжнее payload)
                    api_name = (applicant.get("data") or {}).get("name") or ""
                    if api_name:
                        candidate_name = api_name

                    # Телефон (берём из API, если не пришёл в payload)
                    phones = contacts.get("phones") or []
                    if phones and not phone_raw:
                        phone_raw = (phones[0] or {}).get("value")

                    # chat_id из contacts если не пришёл в payload
                    api_chat_id = (contacts.get("chat") or {}).get("value") or ""
                    if api_chat_id and not chat_id:
                        chat_id = api_chat_id

                    # Вакансия
                    vacancy_title = vacancy_data.get("title") or None
                    vacancy_location = (vacancy_data.get("addressDetails") or {}).get("city") or None
                    api_item_id = vacancy_data.get("id")
                    if api_item_id and not avito_item_id:
                        avito_item_id = int(api_item_id)
            except Exception:
                logger.warning("handle_new_response: failed to enrich via Avito API apply_id=%s", apply_id)

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

            # Получаем default stage
            stage_result = await session.execute(
                text("SELECT id FROM pipeline_stages WHERE org_id = CAST(:org_id AS UUID) AND is_default = true LIMIT 1"),
                {"org_id": str(_org_id)},
            )
            stage_row = stage_result.fetchone()
            default_stage_id = str(stage_row[0]) if stage_row and stage_row[0] else None

            # Upsert candidate
            candidate_result = await session.execute(
                text("""
                    INSERT INTO candidates (
                        org_id, avito_account_id, chat_id, avito_user_id, avito_item_id,
                        name, phone_enc, phone_search_hash, source, has_new_message,
                        department_id, stage_id, vacancy, location
                    ) VALUES (
                        CAST(:org_id AS UUID), CAST(:account_id AS UUID), :chat_id, :avito_user_id,
                        :avito_item_id, :name, :phone_enc, :phone_search_hash,
                        'avito', true,
                        CAST(NULLIF(:department_id, '') AS UUID),
                        CAST(NULLIF(:stage_id, '') AS UUID),
                        :vacancy, :location
                    )
                    ON CONFLICT (org_id, chat_id) WHERE deleted_at IS NULL AND chat_id IS NOT NULL
                    DO UPDATE SET
                        avito_user_id     = EXCLUDED.avito_user_id,
                        avito_item_id     = EXCLUDED.avito_item_id,
                        name              = COALESCE(EXCLUDED.name, candidates.name),
                        phone_enc         = COALESCE(EXCLUDED.phone_enc, candidates.phone_enc),
                        phone_search_hash = COALESCE(EXCLUDED.phone_search_hash, candidates.phone_search_hash),
                        vacancy           = COALESCE(EXCLUDED.vacancy, candidates.vacancy),
                        location          = COALESCE(EXCLUDED.location, candidates.location),
                        has_new_message   = true,
                        updated_at        = now()
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
                    "stage_id": default_stage_id,
                    "vacancy": vacancy_title,
                    "location": vacancy_location,
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

        # Upsert вакансии в таблицу vacancies
        if avito_item_id and vacancy_title:
            try:
                async with session_factory() as v_session:
                    await v_session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
                    await v_session.execute(
                        text("""
                            INSERT INTO vacancies (org_id, avito_account_id, avito_item_id, title, location, status, synced_at)
                            VALUES (
                                CAST(:org_id AS UUID),
                                CAST(:account_id AS UUID),
                                :avito_item_id,
                                :title,
                                :location,
                                'active',
                                now()
                            )
                            ON CONFLICT (org_id, avito_item_id) DO UPDATE SET
                                title      = EXCLUDED.title,
                                location   = COALESCE(EXCLUDED.location, vacancies.location),
                                synced_at  = now()
                        """),
                        {
                            "org_id": str(_org_id),
                            "account_id": str(_account_id),
                            "avito_item_id": avito_item_id,
                            "title": vacancy_title,
                            "location": vacancy_location,
                        },
                    )
                    await v_session.commit()
            except Exception:
                logger.warning("handle_new_response: failed to upsert vacancy item_id=%s", avito_item_id)

        # Применить авто-тег к новому кандидату
        if candidate_id:
            auto_tag_id_bytes = await redis.get(f"org:{org_id}:auto_tag_id")
            if auto_tag_id_bytes:
                auto_tag_id_str = auto_tag_id_bytes.decode()
                try:
                    async with session_factory() as session:
                        from sqlalchemy import text
                        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
                        await session.execute(
                            text("""
                                INSERT INTO candidate_tags (candidate_id, tag_id, org_id)
                                VALUES (CAST(:cid AS UUID), CAST(:tid AS UUID), CAST(:oid AS UUID))
                                ON CONFLICT DO NOTHING
                            """),
                            {"cid": str(candidate_id), "tid": auto_tag_id_str, "oid": org_id},
                        )
                        await session.commit()
                except Exception:
                    logger.warning("handle_new_response: failed to apply auto-tag candidate=%s", candidate_id)

        # Проверяем auto_response_rules
        if avito_item_id and avito_account_id:
            try:
                await _check_and_send_auto_response(
                    ctx, _org_id, _account_id, chat_id, avito_item_id,
                    auto_type="on_response",
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

    Логика:
    - Пропустить собственные сообщения аккаунта (author_id == account.avito_user_id)
    - System-сообщения с flow_id 'job'/'job_apply_enrichment' и триггер-текстом
      обрабатываются как отклик (upsert кандидата + авто-ответ)
    - Прочие системные сообщения игнорируются
    - Обычные сообщения: INSERT chat_messages, write-behind chat_metadata, WS broadcast
    - Контент извлекается по типу: text, image (URL), location, video, voice, call, link
    """
    import uuid

    redis = ctx["redis"]
    session_factory = ctx["session_factory"]

    try:
        _org_id = uuid.UUID(org_id)
        _account_id = uuid.UUID(avito_account_id)

        # Avito присылает вложенную структуру: {payload: {type: "message", value: {...}}}
        value = payload.get("payload", {}).get("value", payload)

        chat_id: str = value.get("chat_id", "") or payload.get("chat_id", "")
        message_type_raw: str = value.get("type", "text") or "text"
        avito_message_id: str = str(value.get("id", "") or payload.get("id", ""))
        author_id = value.get("author_id")

        # created — Unix timestamp (int) или ISO строка
        from datetime import datetime, timezone
        _created_raw = value.get("created") or value.get("published_at")
        if isinstance(_created_raw, int):
            created_at_ts = datetime.fromtimestamp(_created_raw, tz=timezone.utc)
        elif isinstance(_created_raw, str) and _created_raw:
            try:
                created_at_ts = datetime.fromisoformat(_created_raw.replace("Z", "+00:00"))
            except ValueError:
                created_at_ts = None
        else:
            created_at_ts = None

        async with session_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

            # Загрузить данные аккаунта: avito_user_id + department_id
            acc_result = await session.execute(
                text("SELECT avito_user_id, department_id FROM avito_accounts WHERE id = CAST(:account_id AS UUID)"),
                {"account_id": str(_account_id)},
            )
            acc_row = acc_result.fetchone()
            account_avito_user_id: int | None = acc_row[0] if acc_row else None
            account_department_id: str | None = str(acc_row[1]) if acc_row and acc_row[1] else None

        # Пропустить собственные сообщения аккаунта
        if account_avito_user_id and author_id and int(author_id) == account_avito_user_id:
            logger.debug(
                "handle_new_message: skip own message chat_id=%s author_id=%s",
                chat_id, author_id,
            )
            return

        # ------------------------------------------------------------------
        # System-сообщение — возможный отклик через messages webhook
        # ------------------------------------------------------------------
        if message_type_raw == "system":
            await _handle_system_message(
                ctx, _org_id, _account_id, account_department_id,
                chat_id, value, account_avito_user_id,
            )
            return

        # ------------------------------------------------------------------
        # Обычное сообщение от кандидата
        # ------------------------------------------------------------------
        message_text, message_type = _extract_message_content(value)

        async with session_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

            # Найти candidate — если нет, создать
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
            is_new_candidate = candidate_id is None

            if candidate_id is None and chat_id:
                # Получаем default stage для нового кандидата
                stage_result = await session.execute(
                    text("SELECT id FROM pipeline_stages WHERE org_id = CAST(:org_id AS UUID) AND is_default = true LIMIT 1"),
                    {"org_id": str(_org_id)},
                )
                stage_row = stage_result.fetchone()
                default_stage_id = str(stage_row[0]) if stage_row and stage_row[0] else None

                new_cand = await session.execute(
                    text("""
                        INSERT INTO candidates (
                            org_id, avito_account_id, chat_id, source,
                            has_new_message, department_id, stage_id
                        ) VALUES (
                            CAST(:org_id AS UUID), CAST(:account_id AS UUID), :chat_id, 'avito',
                            true, CAST(NULLIF(:department_id, '') AS UUID),
                            CAST(NULLIF(:stage_id, '') AS UUID)
                        )
                        ON CONFLICT (org_id, chat_id) WHERE deleted_at IS NULL AND chat_id IS NOT NULL DO UPDATE SET
                            has_new_message = true,
                            updated_at = now()
                        RETURNING id
                    """),
                    {
                        "org_id": str(_org_id),
                        "account_id": str(_account_id),
                        "chat_id": chat_id,
                        "department_id": account_department_id,
                        "stage_id": default_stage_id,
                    },
                )
                new_row = new_cand.fetchone()
                candidate_id = new_row[0] if new_row else None

                # Upsert chat_metadata для нового кандидата
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

            # INSERT chat_messages (дедуп через WHERE NOT EXISTS)
            if candidate_id and chat_id:
                await session.execute(
                    text("""
                        INSERT INTO chat_messages (
                            org_id, candidate_id, chat_id, avito_message_id,
                            content, message_type, author_type, created_at
                        )
                        SELECT
                            CAST(:org_id AS UUID), CAST(:candidate_id AS UUID), :chat_id,
                            :avito_message_id, :content, :message_type, 'candidate',
                            COALESCE(CAST(:created_at AS TIMESTAMPTZ), now())
                        WHERE NOT EXISTS (
                            SELECT 1 FROM chat_messages
                            WHERE avito_message_id = CAST(:avito_message_id AS VARCHAR)
                              AND avito_message_id IS NOT NULL
                        )
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

        if not candidate_id:
            logger.warning("handle_new_message: no candidate_id, chat_id=%s", chat_id)
            return

        # Применить авто-тег к новому кандидату
        if is_new_candidate and candidate_id:
            auto_tag_id_bytes = await redis.get(f"org:{org_id}:auto_tag_id")
            if auto_tag_id_bytes:
                auto_tag_id_str = auto_tag_id_bytes.decode()
                try:
                    async with session_factory() as session:
                        from sqlalchemy import text
                        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
                        await session.execute(
                            text("""
                                INSERT INTO candidate_tags (candidate_id, tag_id, org_id)
                                VALUES (CAST(:cid AS UUID), CAST(:tid AS UUID), CAST(:oid AS UUID))
                                ON CONFLICT DO NOTHING
                            """),
                            {"cid": str(candidate_id), "tid": auto_tag_id_str, "oid": org_id},
                        )
                        await session.commit()
                except Exception:
                    logger.warning("handle_new_message: failed to apply auto-tag candidate=%s", candidate_id)

        # Попытаться обогатить нового кандидата данными из Avito API
        if is_new_candidate:
            try:
                await _enrich_candidate_from_api(
                    ctx, session_factory, _org_id, _account_id,
                    candidate_id, chat_id, account_avito_user_id,
                )
            except Exception:
                logger.warning(
                    "handle_new_message: enrich failed chat_id=%s", chat_id,
                    exc_info=True,
                )

            # Авто-ответ на первое сообщение — item_id может стать известен после обогащения
            try:
                # Получаем актуальный avito_item_id кандидата после обогащения
                async with session_factory() as _s:
                    from sqlalchemy import text as _text
                    await _s.execute(_text("SET LOCAL app.is_superadmin = 'true'"))
                    _item_result = await _s.execute(
                        _text("SELECT avito_item_id FROM candidates WHERE id = CAST(:cid AS UUID)"),
                        {"cid": str(candidate_id)},
                    )
                    _item_row = _item_result.fetchone()
                    _item_id = _item_row[0] if _item_row and _item_row[0] else None

                if _item_id:
                    await _check_and_send_auto_response(
                        ctx, _org_id, _account_id, chat_id, _item_id,
                        auto_type="on_first_message",
                    )
            except Exception:
                logger.warning(
                    "handle_new_message: auto_response failed chat_id=%s", chat_id,
                    exc_info=True,
                )

        # Write-behind: chat_metadata
        from app.services.cache import CacheService

        cache = CacheService(redis)
        await cache.wb_update_chat_meta(
            chat_id,
            {
                "last_message": _last_message_preview(message_text, message_type),
                "unread_count": "increment",
                "last_message_at": created_at_ts,
            },
        )
        await cache.wb_update_candidate_flags(
            candidate_id,
            {"has_new_message": "true"},
        )

        # Инвалидация кеша сообщений
        await cache.invalidate_chat(chat_id)

        # WebSocket broadcast
        from app.routers.ws import ws_manager

        if is_new_candidate:
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
# Internal helpers
# ------------------------------------------------------------------

async def _handle_system_message(
    ctx: dict,
    org_id,
    account_id,
    account_department_id: str | None,
    chat_id: str,
    value: dict,
    account_avito_user_id: int | None,
) -> None:
    """
    Обработка системного сообщения.
    Если flow_id == 'job'/'job_apply_enrichment' и текст содержит триггер —
    это отклик: upsert кандидата, отправить авто-ответ (если настроен).
    """
    content: dict = value.get("content") or {}
    flow_id: str = content.get("flow_id") or ""
    text_body: str = (content.get("text") or "").lower()

    if flow_id not in _RESPONSE_FLOWS:
        logger.debug(
            "_handle_system_message: skip flow_id=%s chat_id=%s", flow_id, chat_id
        )
        return

    is_trigger = any(t in text_body for t in _RESPONSE_TRIGGERS)
    if not is_trigger:
        logger.debug(
            "_handle_system_message: no trigger chat_id=%s text=%s", chat_id, text_body[:80]
        )
        return

    session_factory = ctx["session_factory"]
    redis = ctx["redis"]

    # Попробовать получить данные кандидата через Avito API
    candidate_avito_user_id: int = value.get("user_id") or 0
    candidate_name: str | None = None
    avito_item_id: int = 0

    if account_avito_user_id and chat_id:
        try:
            chat_data = await _fetch_chat_info(ctx, account_id, account_avito_user_id, chat_id)
            if chat_data:
                candidate_name = chat_data.get("users", [{}])[0].get("name") if chat_data.get("users") else None
                # item_id из context
                context = chat_data.get("context", {})
                avito_item_id = context.get("value", {}).get("id") or 0
                if not candidate_avito_user_id:
                    users = chat_data.get("users", [])
                    for u in users:
                        uid = u.get("id")
                        if uid and uid != account_avito_user_id:
                            candidate_avito_user_id = uid
                            break
        except Exception:
            logger.warning(
                "_handle_system_message: api fetch failed chat_id=%s", chat_id,
                exc_info=True,
            )

    async with session_factory() as session:
        from sqlalchemy import text

        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

        cand_result = await session.execute(
            text("""
                INSERT INTO candidates (
                    org_id, avito_account_id, chat_id, avito_user_id, avito_item_id,
                    name, source, has_new_message, department_id
                ) VALUES (
                    CAST(:org_id AS UUID), CAST(:account_id AS UUID), :chat_id,
                    :avito_user_id, :avito_item_id, :name,
                    'avito', true, CAST(NULLIF(:department_id, '') AS UUID)
                )
                ON CONFLICT (org_id, chat_id) WHERE deleted_at IS NULL AND chat_id IS NOT NULL
                DO UPDATE SET
                    avito_user_id = COALESCE(EXCLUDED.avito_user_id, candidates.avito_user_id),
                    avito_item_id = COALESCE(EXCLUDED.avito_item_id, candidates.avito_item_id),
                    name          = COALESCE(EXCLUDED.name, candidates.name),
                    has_new_message = true,
                    updated_at    = now()
                RETURNING id
            """),
            {
                "org_id": str(org_id),
                "account_id": str(account_id),
                "chat_id": chat_id,
                "avito_user_id": candidate_avito_user_id or None,
                "avito_item_id": avito_item_id or None,
                "name": candidate_name,
                "department_id": account_department_id,
            },
        )
        row = cand_result.fetchone()
        candidate_id = row[0] if row else None

        if candidate_id:
            await session.execute(
                text("""
                    INSERT INTO chat_metadata (org_id, candidate_id, chat_id, unread_count)
                    VALUES (CAST(:org_id AS UUID), CAST(:candidate_id AS UUID), :chat_id, 1)
                    ON CONFLICT (chat_id) DO UPDATE SET
                        unread_count = chat_metadata.unread_count + 1,
                        updated_at = now()
                """),
                {"org_id": str(org_id), "candidate_id": str(candidate_id), "chat_id": chat_id},
            )

        await session.commit()

    if candidate_id:
        # Инвалидация кеша кандидатов
        async for key in redis.scan_iter(match=f"candidates:{org_id}:*", count=100):
            await redis.delete(key)
        await redis.delete(f"org:{org_id}:filters")

        # WebSocket broadcast
        from app.routers.ws import ws_manager

        await ws_manager.broadcast_org(
            org_id,
            {"type": "new_candidate", "candidate_id": str(candidate_id)},
        )

        # Авто-ответ
        if avito_item_id:
            try:
                await _check_and_send_auto_response(
                    ctx, org_id, account_id, chat_id, avito_item_id,
                    auto_type="on_response",
                )
            except Exception:
                logger.warning(
                    "_handle_system_message: auto_response failed chat_id=%s", chat_id,
                    exc_info=True,
                )

        logger.info(
            "_handle_system_message: response created candidate_id=%s chat_id=%s",
            candidate_id, chat_id,
        )


async def _fetch_chat_info(ctx: dict, account_id, account_avito_user_id: int, chat_id: str) -> dict | None:
    """Получить данные чата через Avito API (кешируется в Redis)."""
    redis = ctx["redis"]
    import orjson

    cache_key = f"chat_info:{chat_id}"
    cached = await redis.get(cache_key)
    if cached:
        return orjson.loads(cached)

    session_factory = ctx["session_factory"]
    avito_client = _get_avito_client(ctx)

    async with session_factory() as session:
        from sqlalchemy import text, select
        from app.models.avito import AvitoAccount

        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
        result = await session.execute(
            select(AvitoAccount).where(AvitoAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

    if account is None:
        return None

    data = await avito_client.get_user_info(account, account_avito_user_id, chat_id)
    if data:
        await redis.setex(cache_key, 300, orjson.dumps(data))
    return data


async def _enrich_candidate_from_api(
    ctx: dict,
    session_factory,
    org_id,
    account_id,
    candidate_id,
    chat_id: str,
    account_avito_user_id: int | None,
) -> None:
    """
    Обогатить нового кандидата данными из Avito API.
    Вызывается один раз при создании кандидата через messages webhook.
    """
    if not account_avito_user_id:
        return

    chat_data = await _fetch_chat_info(ctx, account_id, account_avito_user_id, chat_id)
    if not chat_data:
        return

    # Извлечь имя кандидата (не наш аккаунт)
    candidate_name: str | None = None
    candidate_avito_user_id: int | None = None
    for u in chat_data.get("users", []):
        uid = u.get("id")
        if uid and uid != account_avito_user_id:
            candidate_name = u.get("name")
            candidate_avito_user_id = uid
            break

    # item_id из context
    context = chat_data.get("context", {})
    avito_item_id: int | None = context.get("value", {}).get("id") or None

    if not candidate_name and not candidate_avito_user_id and not avito_item_id:
        return

    async with session_factory() as session:
        from sqlalchemy import text

        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
        await session.execute(
            text("""
                UPDATE candidates
                SET name           = COALESCE(:name, name),
                    avito_user_id  = COALESCE(:avito_user_id, avito_user_id),
                    avito_item_id  = COALESCE(:avito_item_id, avito_item_id),
                    updated_at     = now()
                WHERE id = CAST(:candidate_id AS UUID)
            """),
            {
                "name": candidate_name,
                "avito_user_id": candidate_avito_user_id,
                "avito_item_id": avito_item_id,
                "candidate_id": str(candidate_id),
            },
        )
        await session.commit()

    logger.info(
        "_enrich_candidate: candidate_id=%s name=%s item_id=%s",
        candidate_id, candidate_name, avito_item_id,
    )


def _get_avito_client(ctx: dict):
    """Получить или создать AvitoAPIClient."""
    avito_client = ctx.get("avito_client")
    if avito_client is None:
        from app.config import get_settings
        from app.services.avito_client import AvitoAPIClient

        settings = get_settings()
        redis = ctx["redis"]
        avito_client = AvitoAPIClient(
            redis=redis,
            encryption_key=settings.encryption_key_bytes,
        )
        if avito_client.session is None:
            import aiohttp
            avito_client.session = aiohttp.ClientSession()
        ctx["avito_client"] = avito_client

    return avito_client


async def _check_and_send_auto_response(
    ctx: dict,
    org_id,
    account_id,
    chat_id: str,
    item_id: int,
    auto_type: str | None = None,
) -> None:
    """Проверить авто-ответ и отправить напрямую через AutoResponseService если нужно."""
    session_factory = ctx["session_factory"]
    avito_client = _get_avito_client(ctx)

    async with session_factory() as session:
        from sqlalchemy import text, select as sa_select
        from app.models.avito import AvitoAccount
        from app.repositories.messaging import MessagingRepository
        from app.services.auto_response import AutoResponseService

        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

        acc_result = await session.execute(
            sa_select(AvitoAccount).where(AvitoAccount.id == account_id)
        )
        account = acc_result.scalar_one_or_none()
        if account is None:
            logger.warning(
                "_check_and_send_auto_response: account not found account_id=%s", account_id
            )
            return

        repo = MessagingRepository(session)
        service = AutoResponseService(repo=repo, avito_client=avito_client)

        try:
            await service.send_auto_response(
                account=account,
                chat_id=chat_id,
                item_id=item_id,
                auto_type=auto_type,
            )
        except Exception:
            logger.exception(
                "_check_and_send_auto_response: send failed account=%s chat=%s",
                account_id,
                chat_id,
            )


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
