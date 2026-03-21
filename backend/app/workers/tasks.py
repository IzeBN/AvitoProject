"""
ARQ задачи для фоновой обработки.
check_self_employed_inn — одиночная проверка ИНН (вызывается из bulk endpoint).
check_subscription_expiry — cron: обновление статусов истёкших подписок.
"""

import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def check_self_employed_inn(
    ctx: dict,
    org_id: str,
    inn: str,
    checked_by: str,
) -> dict:
    """
    ARQ задача: проверить один ИНН и сохранить результат.
    Вызывается из SelfEmployedService.check_bulk для каждого ИНН.
    """
    from app.database import get_session_factory
    from app.models.self_employed import SelfEmployedCheck
    from app.services.avito_client import AvitoAPIClient
    from sqlalchemy import text

    logger.info("Checking self-employed INN=%s org=%s", inn, org_id)

    factory = get_session_factory()
    async with factory() as session:
        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

        # Инициализируем клиент из Redis пула
        try:
            from app.redis import get_pool
            from redis.asyncio import Redis

            pool = get_pool()
            redis_client = Redis(connection_pool=pool)

            from app.config import get_settings
            settings = get_settings()
            enc_key = settings.encryption_key_bytes

            avito_client = AvitoAPIClient(redis=redis_client, encryption_key=enc_key)

            import aiohttp
            async with aiohttp.ClientSession() as http_session:
                avito_client.session = http_session
                raw_response = await avito_client.get_self_employed_status(inn)
        except Exception:
            logger.exception("Failed to call nalog API for INN=%s", inn)
            raw_response = {}

        # Определяем статус
        status_str = raw_response.get("status", "").lower()
        if status_str in ("taxpayer", "active", "registered"):
            mapped_status = "active"
        elif status_str in ("not_registered", "inactive", "closed"):
            mapped_status = "inactive"
        elif status_str == "not_found":
            mapped_status = "not_found"
        else:
            mapped_status = "unknown"

        check = SelfEmployedCheck(
            org_id=uuid.UUID(org_id),
            inn=inn,
            status=mapped_status,
            checked_by=uuid.UUID(checked_by) if checked_by else None,
            checked_at=datetime.now(timezone.utc),
            raw_response=raw_response,
        )
        session.add(check)
        await session.commit()

    logger.info("INN=%s checked: status=%s", inn, mapped_status)
    return {"inn": inn, "status": mapped_status}


async def check_subscription_expiry(ctx: dict) -> None:
    """
    Cron задача: обновить статус организаций с истёкшей подпиской.
    Запускается раз в час. Помечает access_status='expired'.
    """
    from app.database import get_session_factory
    from app.models.auth import Organization
    from sqlalchemy import select, text, update

    now = datetime.now(timezone.utc)

    factory = get_session_factory()
    async with factory() as session:
        await session.execute(text("SET LOCAL app.is_superadmin = 'true'"))

        result = await session.execute(
            update(Organization)
            .where(
                Organization.subscription_until < now,
                Organization.access_status == "active",
            )
            .values(access_status="expired")
            .returning(Organization.id, Organization.name)
        )
        expired_orgs = result.all()
        await session.commit()

    if expired_orgs:
        logger.info(
            "Marked %d organizations as expired: %s",
            len(expired_orgs),
            [str(r.id) for r in expired_orgs],
        )

        # Инвалидируем кеши и отправляем WebSocket
        for row in expired_orgs:
            try:
                from app.redis import get_pool
                from redis.asyncio import Redis

                pool = get_pool()
                redis_client = Redis(connection_pool=pool)
                await redis_client.delete(f"org_status:{row.id}")
                await redis_client.aclose()

                from app.routers.ws import ws_manager
                await ws_manager.broadcast_org(
                    row.id,
                    {"type": "org_access_changed", "status": "expired"},
                )
            except Exception:
                logger.warning("Failed to notify org %s about expiry", row.id)
