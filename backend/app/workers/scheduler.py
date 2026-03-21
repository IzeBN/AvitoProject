"""
ARQ periodic задачи планировщика:
- check_subscription_expiry   — каждые 10 минут
- create_monthly_partitions   — ежедневно
- flush_webhook_last_received — каждые 60 секунд
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def check_subscription_expiry(ctx: dict) -> None:
    """
    Проверить истечение подписок организаций.
    Запускается каждые 10 минут.
    """
    session_factory = ctx.get("session_factory")
    if not session_factory:
        logger.error("check_subscription_expiry: no session_factory in ctx")
        return

    try:
        async with session_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

            # Деактивировать организации с истекшей подпиской
            result = await session.execute(
                text("""
                    UPDATE organizations
                    SET access_status = 'expired'
                    WHERE access_status = 'active'
                      AND subscription_until IS NOT NULL
                      AND subscription_until < now()
                    RETURNING id, name
                """)
            )
            expired = result.fetchall()

            if expired:
                logger.info(
                    "check_subscription_expiry: expired %d orgs: %s",
                    len(expired),
                    [str(r[0]) for r in expired],
                )

            await session.commit()

    except Exception:
        logger.exception("check_subscription_expiry: error")


async def create_monthly_partitions(ctx: dict) -> None:
    """
    Создать партиции chat_messages, audit_log, error_log на следующий месяц.
    Запускается ежедневно — создаёт только если не существует.
    """
    session_factory = ctx.get("session_factory")
    if not session_factory:
        return

    try:
        from datetime import date

        today = date.today()

        # Текущий + следующий месяц
        months = []
        for offset in range(2):
            year = today.year
            month = today.month + offset
            if month > 12:
                month -= 12
                year += 1
            months.append((year, month))

        async with session_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

            for year, month in months:
                start = date(year, month, 1)
                if month == 12:
                    end = date(year + 1, 1, 1)
                else:
                    end = date(year, month + 1, 1)

                suffix = f"{year}_{month:02d}"

                for table in ("chat_messages", "audit_log", "error_log"):
                    partition_name = f"{table}_{suffix}"
                    sql = f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_class c
                                JOIN pg_namespace n ON n.oid = c.relnamespace
                                WHERE c.relname = '{partition_name}'
                            ) THEN
                                EXECUTE format(
                                    'CREATE TABLE IF NOT EXISTS {partition_name}
                                     PARTITION OF {table}
                                     FOR VALUES FROM (%L) TO (%L)',
                                    '{start}', '{end}'
                                );
                            END IF;
                        END;
                        $$;
                    """
                    try:
                        await session.execute(text(sql))
                        logger.debug("Partition %s ensured", partition_name)
                    except Exception:
                        logger.warning(
                            "Could not create partition %s", partition_name, exc_info=True
                        )

            await session.commit()

    except Exception:
        logger.exception("create_monthly_partitions: error")


async def flush_webhook_last_received(ctx: dict) -> None:
    """
    Прочитать wb:webhook_last:* ключи и batch UPDATE last_received_at в DB.
    Запускается каждые 60 секунд.
    """
    redis = ctx.get("redis")
    session_factory = ctx.get("session_factory")

    if redis is None or session_factory is None:
        return

    try:
        # Читаем все dirty токены
        dirty_tokens = await redis.smembers("wb:webhook_tokens:dirty")
        if not dirty_tokens:
            return

        updates = []
        for token_bytes in dirty_tokens:
            token = token_bytes.decode() if isinstance(token_bytes, bytes) else token_bytes
            updates.append(token)

        if updates:
            async with session_factory() as session:
                from sqlalchemy import text

                await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

                for token in updates:
                    await session.execute(
                        text("""
                            UPDATE avito_webhook_endpoints
                            SET last_received_at = now()
                            WHERE account_token = :token
                        """),
                        {"token": token},
                    )
                    await redis.delete(f"wb:webhook_last:{token}")

                await session.commit()

            logger.debug(
                "flush_webhook_last_received: updated %d endpoints", len(updates)
            )

        # Очистить dirty set
        await redis.delete("wb:webhook_tokens:dirty")

    except Exception:
        logger.exception("flush_webhook_last_received: error")
