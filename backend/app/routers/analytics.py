"""
Роутер аналитики.

GET /api/v1/analytics/overview
GET /api/v1/analytics/funnel
GET /api/v1/analytics/by-vacancy
GET /api/v1/analytics/by-responsible
GET /api/v1/analytics/by-department
GET /api/v1/analytics/activity
"""

import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.auth import User
from app.redis import get_redis
from app.repositories.analytics import AnalyticsRepository
from app.services.analytics import AnalyticsService
from app.services.cache import CacheService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_analytics_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> AnalyticsService:
    return AnalyticsService(
        repo=AnalyticsRepository(db),
        cache=CacheService(redis),
    )


def _default_date_range() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=30), today


@router.get(
    "/overview",
    summary="Общая статистика за период",
    description="Кешируется 15 минут. Фильтрация по org_id применяется автоматически из токена.",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_overview(
    service: Annotated[AnalyticsService, Depends(_get_analytics_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
):
    """Общая статистика организации за период."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    return await service.get_overview(
        org_id=current_user.org_id,
        date_from=date_from,
        date_to=date_to,
        department_id=department_id,
    )


@router.get(
    "/funnel",
    summary="Конверсионная воронка",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_funnel(
    service: Annotated[AnalyticsService, Depends(_get_analytics_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
):
    """Конверсионная воронка по этапам отбора."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    return await service.get_funnel(
        org_id=current_user.org_id,
        date_from=date_from,
        date_to=date_to,
        department_id=department_id,
    )


@router.get(
    "/by-vacancy",
    summary="Статистика по вакансиям",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_by_vacancy(
    service: Annotated[AnalyticsService, Depends(_get_analytics_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
):
    """Статистика кандидатов по вакансиям."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    return await service.get_by_vacancy(
        org_id=current_user.org_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/by-responsible",
    summary="Статистика по ответственным",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_by_responsible(
    service: Annotated[AnalyticsService, Depends(_get_analytics_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
):
    """Статистика по ответственным менеджерам."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    return await service.get_by_responsible(
        org_id=current_user.org_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/by-department",
    summary="Статистика по отделам",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_by_department(
    service: Annotated[AnalyticsService, Depends(_get_analytics_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
):
    """Статистика по отделам организации."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    return await service.get_by_department(
        org_id=current_user.org_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/activity",
    summary="Активность команды по дням",
    description="Данные из audit_log: количество сообщений и изменений по дням.",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_activity(
    service: Annotated[AnalyticsService, Depends(_get_analytics_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
):
    """Активность команды: сообщения и изменения по дням."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    return await service.get_activity(
        org_id=current_user.org_id,
        date_from=date_from,
        date_to=date_to,
    )
