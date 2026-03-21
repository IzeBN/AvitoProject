"""
AnalyticsService — агрегация статистики с кешированием в Redis 15 мин.
"""

import logging
import uuid
from datetime import date, timedelta

import orjson

from app.repositories.analytics import AnalyticsRepository
from app.services.cache import CacheService

logger = logging.getLogger(__name__)

ANALYTICS_TTL = 900  # 15 минут


class AnalyticsService:
    """
    Сервис аналитики.

    Все методы кешируют результат в Redis на 15 минут.
    Ключ включает org_id, период и опциональный department_id.
    """

    def __init__(self, repo: AnalyticsRepository, cache: CacheService) -> None:
        self._repo = repo
        self._cache = cache

    def _cache_key(self, org_id: uuid.UUID, name: str, **kwargs) -> str:
        parts = [f"analytics:{org_id}:{name}"]
        for k, v in sorted(kwargs.items()):
            parts.append(f"{k}={v}")
        return ":".join(parts)

    async def get_overview(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
        department_id: uuid.UUID | None = None,
    ) -> dict:
        """Общая статистика за период. Кешируется 15 мин."""
        key = self._cache_key(
            org_id,
            "overview",
            date_from=str(date_from),
            date_to=str(date_to),
            dept=str(department_id) if department_id else "none",
        )
        cached = await self._cache._get(key)
        if cached is not None:
            return cached

        result = await self._repo.get_overview(org_id, date_from, date_to, department_id)
        await self._cache._set(key, result, ttl=ANALYTICS_TTL)
        return result

    async def get_funnel(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
        department_id: uuid.UUID | None = None,
    ) -> dict:
        """Конверсионная воронка по этапам."""
        key = self._cache_key(
            org_id,
            "funnel",
            date_from=str(date_from),
            date_to=str(date_to),
            dept=str(department_id) if department_id else "none",
        )
        cached = await self._cache._get(key)
        if cached is not None:
            return cached

        overview = await self._repo.get_overview(org_id, date_from, date_to, department_id)
        by_stage = overview.get("by_stage", [])
        total = sum(s["count"] for s in by_stage)

        stages = []
        prev_count = None
        for stage in by_stage:
            count = stage["count"]
            if prev_count is not None and prev_count > 0:
                conversion = round(count / prev_count * 100, 1)
            else:
                conversion = None
            stages.append({
                "name": stage["stage"],
                "count": count,
                "conversion_from_prev": conversion,
                "avg_days": None,
            })
            prev_count = count

        result = {"stages": stages}
        await self._cache._set(key, result, ttl=ANALYTICS_TTL)
        return result

    async def get_by_vacancy(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> dict:
        """Статистика по вакансиям."""
        key = self._cache_key(
            org_id, "by_vacancy",
            date_from=str(date_from),
            date_to=str(date_to),
        )
        cached = await self._cache._get(key)
        if cached is not None:
            return cached

        items = await self._repo.get_by_vacancy(org_id, date_from, date_to)
        result = {"items": items, "total_vacancies": len(items)}
        await self._cache._set(key, result, ttl=ANALYTICS_TTL)
        return result

    async def get_by_responsible(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> dict:
        """Статистика по ответственным."""
        key = self._cache_key(
            org_id, "by_responsible",
            date_from=str(date_from),
            date_to=str(date_to),
        )
        cached = await self._cache._get(key)
        if cached is not None:
            return cached

        items = await self._repo.get_by_responsible(org_id, date_from, date_to)
        result = {"items": items}
        await self._cache._set(key, result, ttl=ANALYTICS_TTL)
        return result

    async def get_by_department(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> dict:
        """Статистика по отделам."""
        key = self._cache_key(
            org_id, "by_department",
            date_from=str(date_from),
            date_to=str(date_to),
        )
        cached = await self._cache._get(key)
        if cached is not None:
            return cached

        items = await self._repo.get_department_stats(org_id, date_from, date_to)
        result = {"items": items}
        await self._cache._set(key, result, ttl=ANALYTICS_TTL)
        return result

    async def get_activity(
        self,
        org_id: uuid.UUID,
        date_from: date,
        date_to: date,
    ) -> dict:
        """Активность команды по дням."""
        key = self._cache_key(
            org_id, "activity",
            date_from=str(date_from),
            date_to=str(date_to),
        )
        cached = await self._cache._get(key)
        if cached is not None:
            return cached

        items = await self._repo.get_activity(org_id, date_from, date_to)
        result = {
            "items": items,
            "date_from": str(date_from),
            "date_to": str(date_to),
        }
        await self._cache._set(key, result, ttl=ANALYTICS_TTL)
        return result
