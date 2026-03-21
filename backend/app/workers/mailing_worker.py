"""
ARQ воркер рассылок.
run_mailing — основная задача отправки сообщений кандидатам.
check_scheduled_mailings — periodic: запуск запланированных рассылок.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Exponential backoff при 429: 5s, 15s, 60s
_RATE_LIMIT_DELAYS = [5, 15, 60]


async def run_mailing(ctx: dict, job_id: str) -> None:
    """
    Основной воркер рассылки.

    Cursor-style обход получателей позволяет возобновить после паузы
    без потери позиции.
    """
    redis = ctx["redis"]
    session_factory = ctx["session_factory"]

    _job_id = uuid.UUID(job_id)

    # 1. Загрузить job, обновить статус
    async with session_factory() as session:
        from sqlalchemy import text

        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

        result = await session.execute(
            text("SELECT id, org_id, message, file_url, rate_limit_ms FROM mailing_jobs WHERE id = :id::uuid"),
            {"id": job_id},
        )
        row = result.fetchone()
        if row is None:
            logger.error("run_mailing: job not found job_id=%s", job_id)
            return

        job_org_id = row[1]
        message_text: str = row[2]
        file_url: str | None = row[3]
        rate_limit_ms: int = row[4] or 1000

        await session.execute(
            text("""
                UPDATE mailing_jobs
                SET status = 'running', started_at = now(), updated_at = now()
                WHERE id = :id::uuid AND status IN ('pending', 'resuming')
            """),
            {"id": job_id},
        )
        await session.commit()

    # 2. Загрузить AvitoAPIClient из app state — недоступно в воркере,
    #    поэтому создаём напрямую
    avito_client = _get_avito_client(ctx)

    # 3. Cursor-based обход получателей
    last_id: uuid.UUID | None = None
    sent = 0
    failed = 0
    processed = 0
    batch_size = 20

    while True:
        # Проверить паузу/стоп
        if await redis.exists(f"mailing:{job_id}:pause"):
            logger.info("run_mailing: paused job_id=%s", job_id)
            async with session_factory() as session:
                from sqlalchemy import text
                await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
                await session.execute(
                    text("UPDATE mailing_jobs SET status = 'paused', updated_at = now() WHERE id = :id::uuid"),
                    {"id": job_id},
                )
                await session.commit()
            return

        if await redis.exists(f"mailing:{job_id}:stop"):
            logger.info("run_mailing: cancelled job_id=%s", job_id)
            async with session_factory() as session:
                from sqlalchemy import text
                await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
                await session.execute(
                    text("""
                        UPDATE mailing_recipients
                        SET status = 'skipped'
                        WHERE mailing_job_id = :id::uuid AND status = 'pending'
                    """),
                    {"id": job_id},
                )
                await session.execute(
                    text("UPDATE mailing_jobs SET status = 'cancelled', finished_at = now(), updated_at = now() WHERE id = :id::uuid"),
                    {"id": job_id},
                )
                await session.commit()
            await redis.delete(f"mailing:{job_id}:progress")
            return

        # Загрузить следующую порцию pending получателей
        async with session_factory() as session:
            from sqlalchemy import text
            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

            if last_id is None:
                result = await session.execute(
                    text("""
                        SELECT mr.id, mr.candidate_id, mr.attempt_count,
                               c.avito_account_id, c.chat_id, c.avito_user_id
                        FROM mailing_recipients mr
                        JOIN candidates c ON c.id = mr.candidate_id
                        WHERE mr.mailing_job_id = :job_id::uuid AND mr.status = 'pending'
                        ORDER BY mr.id
                        LIMIT :limit
                    """),
                    {"job_id": job_id, "limit": batch_size},
                )
            else:
                result = await session.execute(
                    text("""
                        SELECT mr.id, mr.candidate_id, mr.attempt_count,
                               c.avito_account_id, c.chat_id, c.avito_user_id
                        FROM mailing_recipients mr
                        JOIN candidates c ON c.id = mr.candidate_id
                        WHERE mr.mailing_job_id = :job_id::uuid
                          AND mr.status = 'pending'
                          AND mr.id > :last_id::uuid
                        ORDER BY mr.id
                        LIMIT :limit
                    """),
                    {"job_id": job_id, "last_id": str(last_id), "limit": batch_size},
                )

            rows = result.fetchall()

        if not rows:
            break  # Все отправлено

        for row in rows:
            recipient_id = row[0]
            candidate_id = row[1]
            attempt_count: int = row[2]
            account_id = row[3]
            chat_id: str = row[4] or ""
            avito_user_id: int = row[5] or 0

            last_id = recipient_id

            if not chat_id or not avito_user_id or not account_id:
                # Нет данных для отправки — пропустить
                await _update_recipient(
                    session_factory, recipient_id, "skipped", attempt_count
                )
                continue

            # Получить аккаунт
            account = await _load_account(session_factory, account_id)
            if account is None:
                await _update_recipient(
                    session_factory, recipient_id, "failed", attempt_count + 1,
                    error_message="Account not found"
                )
                failed += 1
                continue

            # Отправка с retry при 429
            success = False
            last_error = None

            for attempt_idx, delay in enumerate([0] + _RATE_LIMIT_DELAYS):
                if delay > 0:
                    await asyncio.sleep(delay)

                try:
                    from app.services.avito_client import AvitoRateLimitError

                    if file_url:
                        # Файл — скачать и отправить
                        await _send_with_file(avito_client, account, chat_id, avito_user_id, message_text, file_url)
                    else:
                        await avito_client.send_message(
                            account, chat_id, avito_user_id, message_text
                        )
                    success = True
                    break

                except Exception as exc:
                    from app.services.avito_client import AvitoRateLimitError

                    last_error = str(exc)
                    if isinstance(exc, AvitoRateLimitError) and attempt_idx < len(_RATE_LIMIT_DELAYS):
                        logger.warning(
                            "run_mailing: rate limit, retry %d job=%s", attempt_idx + 1, job_id
                        )
                        continue
                    break

            if success:
                await _update_recipient(
                    session_factory, recipient_id, "sent", attempt_count + 1,
                    sent_at=datetime.now(timezone.utc)
                )
                sent += 1
            else:
                await _update_recipient(
                    session_factory, recipient_id, "failed", attempt_count + 1,
                    error_message=last_error
                )
                failed += 1

            processed += 1

            # Каждые 10 отправок — обновить прогресс
            if processed % 10 == 0:
                total_result = await _count_total(session_factory, job_id)
                await redis.hset(
                    f"mailing:{job_id}:progress",
                    mapping={"sent": sent, "failed": failed, "total": total_result},
                )

                from app.routers.ws import ws_manager
                import uuid as _uuid
                await ws_manager.broadcast_org(
                    _uuid.UUID(str(job_org_id)),
                    {
                        "type": "mailing_progress",
                        "job_id": job_id,
                        "sent": sent,
                        "failed": failed,
                        "total": total_result,
                    },
                )

            # Rate limiting
            await asyncio.sleep(rate_limit_ms / 1000)

    # 4. Завершение
    async with session_factory() as session:
        from sqlalchemy import text
        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
        await session.execute(
            text("""
                UPDATE mailing_jobs
                SET status = 'done', finished_at = now(), sent = :sent, failed = :failed, updated_at = now()
                WHERE id = :id::uuid
            """),
            {"id": job_id, "sent": sent, "failed": failed},
        )
        await session.commit()

    await redis.delete(f"mailing:{job_id}:progress")

    from app.routers.ws import ws_manager
    import uuid as _uuid
    await ws_manager.broadcast_org(
        _uuid.UUID(str(job_org_id)),
        {"type": "mailing_done", "job_id": job_id, "sent": sent, "failed": failed},
    )

    logger.info(
        "run_mailing: done job_id=%s sent=%d failed=%d", job_id, sent, failed
    )


async def check_scheduled_mailings(ctx: dict) -> None:
    """
    ARQ periodic задача — каждые 30 секунд.
    Запускает рассылки у которых scheduled_at <= now() и status='pending'.
    """
    session_factory = ctx["session_factory"]

    try:
        async with session_factory() as session:
            from sqlalchemy import text
            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

            result = await session.execute(
                text("""
                    SELECT id FROM mailing_jobs
                    WHERE status = 'pending'
                      AND scheduled_at IS NOT NULL
                      AND scheduled_at <= now()
                """)
            )
            rows = result.fetchall()

        for row in rows:
            job_id = str(row[0])
            try:
                from arq.connections import ArqRedis
                from app.redis import get_arq_pool

                arq_pool = get_arq_pool()
                arq_redis = ArqRedis(pool_or_conn=arq_pool)
                await arq_redis.enqueue_job("run_mailing", job_id)
                logger.info("check_scheduled_mailings: enqueued job_id=%s", job_id)
            except Exception:
                logger.exception(
                    "check_scheduled_mailings: failed to enqueue job_id=%s", job_id
                )

    except Exception:
        logger.exception("check_scheduled_mailings: error")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_avito_client(ctx: dict):
    """Получить или создать AvitoAPIClient."""
    avito_client = ctx.get("avito_client")
    if avito_client is None:
        # В воркере нет доступа к app.state — создаём клиент
        from app.config import get_settings
        from app.services.avito_client import AvitoAPIClient

        settings = get_settings()
        redis = ctx["redis"]
        avito_client = AvitoAPIClient(
            redis=redis,
            encryption_key=settings.encryption_key_bytes,
        )
        # aiohttp session — используем существующую или создаём новую
        if avito_client.session is None:
            import aiohttp
            avito_client.session = aiohttp.ClientSession()
        ctx["avito_client"] = avito_client

    return avito_client


async def _load_account(session_factory, account_id):
    """Загрузить AvitoAccount из БД."""
    try:
        async with session_factory() as session:
            from sqlalchemy import text, select
            from app.models.avito import AvitoAccount

            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
            result = await session.execute(
                select(AvitoAccount).where(
                    AvitoAccount.id == account_id,
                    AvitoAccount.is_active.is_(True),
                )
            )
            return result.scalar_one_or_none()
    except Exception:
        logger.exception("_load_account failed: account_id=%s", account_id)
        return None


async def _update_recipient(
    session_factory,
    recipient_id,
    status: str,
    attempt_count: int,
    sent_at: datetime | None = None,
    error_message: str | None = None,
) -> None:
    try:
        async with session_factory() as session:
            from sqlalchemy import text
            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
            await session.execute(
                text("""
                    UPDATE mailing_recipients
                    SET status = :status,
                        attempt_count = :attempt_count,
                        last_attempt_at = now(),
                        sent_at = :sent_at,
                        error_message = :error_message
                    WHERE id = :id::uuid
                """),
                {
                    "id": str(recipient_id),
                    "status": status,
                    "attempt_count": attempt_count,
                    "sent_at": sent_at,
                    "error_message": error_message,
                },
            )
            await session.commit()
    except Exception:
        logger.exception("_update_recipient failed")


async def _count_total(session_factory, job_id: str) -> int:
    try:
        async with session_factory() as session:
            from sqlalchemy import text
            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
            result = await session.execute(
                text("SELECT total FROM mailing_jobs WHERE id = :id::uuid"),
                {"id": job_id},
            )
            row = result.fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


async def _send_with_file(avito_client, account, chat_id: str, user_id: int, text: str, file_url: str) -> None:
    """Скачать файл и отправить вместе с текстом."""
    import aiohttp

    assert avito_client.session is not None
    async with avito_client.session.get(file_url) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
        file_data = await resp.read()
        filename = file_url.split("/")[-1] or "file"

    await avito_client.send_file(account, chat_id, user_id, file_data, content_type, filename)
    if text:
        await avito_client.send_message(account, chat_id, user_id, text)
