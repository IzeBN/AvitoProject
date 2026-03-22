"""
Роутер управления рассылками.

GET  /api/v1/mailings                    — список рассылок с прогрессом
POST /api/v1/mailings                    — создать рассылку (по candidate_filters)
GET  /api/v1/mailings/{id}               — детали рассылки + прогресс
POST /api/v1/mailings/{id}/pause         — поставить на паузу
POST /api/v1/mailings/{id}/resume        — возобновить
POST /api/v1/mailings/{id}/stop          — остановить (отмена)
GET  /api/v1/mailings/{id}/recipients    — список получателей (пагинация)

Дополнительные (legacy):
POST /api/v1/mailings/by-ids             — создать по списку IDs
POST /api/v1/mailings/by-filters         — создать по фильтрам
POST /api/v1/mailings/{id}/cancel        — алиас для stop
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.auth import User
from app.redis import get_redis
from app.repositories.mailing import MailingRepository
from app.schemas.mailing import (
    MailingByFiltersRequest,
    MailingByIdsRequest,
    MailingByPhonesRequest,
    MailingCreateRequest,
    MailingJobResponse,
    MailingProgressResponse,
    MailingRecipientsPage,
    MailingRecipientResponse,
)
from app.services.mailing import MailingService

router = APIRouter(prefix="/mailings", tags=["mailings"])


def _get_service(db: AsyncSession, redis: Redis) -> MailingService:
    return MailingService(repo=MailingRepository(db), redis=redis)


# ===========================================================================
# List
# ===========================================================================


@router.get(
    "",
    response_model=list[MailingJobResponse],
    summary="Список рассылок",
    description="Возвращает рассылки организации с прогрессом из Redis. TTL кеша ~10 сек.",
)
async def list_mailings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Фильтр по статусу: pending, running, paused, done, failed, cancelled",
    ),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> list[MailingJobResponse]:
    """Список рассылок с прогрессом."""
    svc = _get_service(db, redis)
    repo = MailingRepository(db)
    offset = (page - 1) * per_page
    jobs = await repo.get_all(
        current_user.org_id,
        status_filter=status_filter,
        offset=offset,
        limit=per_page,
    )

    # Загрузить full_name создателей одним запросом
    from sqlalchemy import select as sa_select
    from app.models.auth import User as UserModel
    creator_ids = {job.created_by for job in jobs if job.created_by}
    creators: dict = {}
    if creator_ids:
        rows = await db.execute(
            sa_select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(creator_ids))
        )
        creators = {str(r.id): r.full_name for r in rows}

    result = []
    for job in jobs:
        progress_data = await svc.get_progress_from_redis(job.id)
        resp = MailingJobResponse.model_validate(job)
        if progress_data:
            resp.progress = MailingProgressResponse(**progress_data)
        creator_full_name = creators.get(str(job.created_by))
        if creator_full_name:
            from app.schemas.mailing import CreatedByResponse
            resp.created_by = CreatedByResponse(id=job.created_by, full_name=creator_full_name)
        result.append(resp)
    return result


# ===========================================================================
# Create (unified endpoint по candidate_filters)
# ===========================================================================


@router.post(
    "",
    response_model=MailingJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать рассылку",
    description=(
        "Разрезолвирует candidate_filters → список получателей, "
        "создаёт MailingJob + MailingRecipient строки. "
        "Если scheduled_at не задан — сразу ставит в очередь ARQ."
    ),
    dependencies=[Depends(require_permission("mailing.send"))],
)
async def create_mailing(
    body: MailingCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    request: Request,
) -> MailingJobResponse:
    """Создать рассылку по критериям фильтрации кандидатов."""
    # Разрезолвим кандидатов
    candidate_ids = await _resolve_candidates_by_filters(
        db, current_user.org_id, body.candidate_filters or {}
    )

    svc = _get_service(db, redis)
    job = await svc.create_by_filters(
        org_id=current_user.org_id,
        user_id=current_user.id,
        filters=body.candidate_filters or {},
        candidate_ids=candidate_ids,
        message=body.message_text,
        file_url=None,
        scheduled_at=body.scheduled_at,
        rate_limit_ms=body.rate_limit_ms,
    )

    if body.scheduled_at is None:
        await _enqueue_mailing(request, str(job.id))

    await db.commit()
    return MailingJobResponse.model_validate(job)


# ===========================================================================
# Detail
# ===========================================================================


@router.get(
    "/{job_id}",
    response_model=MailingJobResponse,
    summary="Детали рассылки + прогресс",
)
async def get_mailing(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> MailingJobResponse:
    svc = _get_service(db, redis)
    job = await svc.get_with_progress(current_user.org_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рассылка не найдена")

    progress_data = await svc.get_progress_from_redis(job.id)
    resp = MailingJobResponse.model_validate(job)
    if progress_data:
        resp.progress = MailingProgressResponse(**progress_data)
    return resp


# ===========================================================================
# Control endpoints
# ===========================================================================


@router.post(
    "/{job_id}/pause",
    status_code=status.HTTP_200_OK,
    summary="Поставить рассылку на паузу",
    dependencies=[Depends(require_permission("mailing.send"))],
)
async def pause_mailing(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict:
    """Устанавливает Redis-флаг mailing:{id}:pause, меняет статус на 'paused'."""
    svc = _get_service(db, redis)
    await svc.pause(current_user.org_id, job_id)
    await db.commit()
    return {"ok": True}


@router.post(
    "/{job_id}/resume",
    status_code=status.HTTP_200_OK,
    summary="Возобновить рассылку",
    dependencies=[Depends(require_permission("mailing.send"))],
)
async def resume_mailing(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    request: Request,
) -> dict:
    """Снимает pause-флаг, ставит статус 'running', re-enqueue ARQ воркера."""
    svc = _get_service(db, redis)
    job = await svc.resume(current_user.org_id, job_id)
    await db.commit()
    await _enqueue_mailing(request, str(job.id))
    return {"ok": True}


@router.post(
    "/{job_id}/stop",
    status_code=status.HTTP_200_OK,
    summary="Остановить рассылку",
    description="Устанавливает Redis-флаг mailing:{id}:stop, статус → 'cancelled'.",
    dependencies=[Depends(require_permission("mailing.send"))],
)
async def stop_mailing(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict:
    svc = _get_service(db, redis)
    await svc.cancel(current_user.org_id, job_id)
    await db.commit()
    return {"ok": True}


# ===========================================================================
# Recipients
# ===========================================================================


@router.get(
    "/{job_id}/recipients",
    response_model=MailingRecipientsPage,
    summary="Получатели рассылки",
)
async def get_mailing_recipients(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> MailingRecipientsPage:
    repo = MailingRepository(db)
    job = await repo.get_by_id(current_user.org_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рассылка не найдена")

    offset = (page - 1) * page_size
    recipients, total = await repo.get_recipients_page(job_id, offset, page_size)

    return MailingRecipientsPage(
        items=[MailingRecipientResponse.model_validate(r) for r in recipients],
        total=total,
        page=page,
        page_size=page_size,
    )


# ===========================================================================
# Legacy endpoints (backward compatibility)
# ===========================================================================


@router.post(
    "/by-ids",
    response_model=MailingJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать рассылку по IDs (legacy)",
    include_in_schema=False,
    dependencies=[Depends(require_permission("mailing.send"))],
)
async def create_mailing_by_ids(
    body: MailingByIdsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    request: Request,
) -> MailingJobResponse:
    svc = _get_service(db, redis)
    job = await svc.create_by_ids(
        org_id=current_user.org_id,
        user_id=current_user.id,
        candidate_ids=body.candidate_ids,
        message=body.message,
        file_url=body.file_url,
        scheduled_at=body.scheduled_at,
        rate_limit_ms=body.rate_limit_ms,
    )
    if body.scheduled_at is None:
        await _enqueue_mailing(request, str(job.id))
    await db.commit()
    return MailingJobResponse.model_validate(job)


@router.post(
    "/by-phones",
    response_model=MailingJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать рассылку по списку телефонов",
    description=(
        "Принимает список телефонных номеров. "
        "Ищет существующих кандидатов в организации по phone_search_hash. "
        "Для не найденных — создаёт минимальные записи кандидатов. "
        "Затем создаёт рассылку как обычно."
    ),
    dependencies=[Depends(require_permission("mailing.send"))],
)
async def create_mailing_by_phones(
    body: MailingByPhonesRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    request: Request,
) -> MailingJobResponse:
    from app.config import get_settings
    settings = get_settings()

    svc = _get_service(db, redis)
    job = await svc.create_by_phones(
        db=db,
        org_id=current_user.org_id,
        user_id=current_user.id,
        phones=body.phones,
        message=body.message_text,
        scheduled_at=body.scheduled_at,
        rate_limit_ms=body.rate_limit_ms,
        search_hash_key=settings.search_hash_key_bytes,
    )

    if body.scheduled_at is None:
        await _enqueue_mailing(request, str(job.id))

    await db.commit()
    return MailingJobResponse.model_validate(job)


@router.post(
    "/by-filters",
    response_model=MailingJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать рассылку по фильтрам (legacy)",
    include_in_schema=False,
    dependencies=[Depends(require_permission("mailing.send"))],
)
async def create_mailing_by_filters(
    body: MailingByFiltersRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    request: Request,
) -> MailingJobResponse:
    candidate_ids = await _resolve_candidates_by_filters(
        db, current_user.org_id, body.filters
    )
    svc = _get_service(db, redis)
    job = await svc.create_by_filters(
        org_id=current_user.org_id,
        user_id=current_user.id,
        filters=body.filters,
        candidate_ids=candidate_ids,
        message=body.message,
        file_url=body.file_url,
        scheduled_at=body.scheduled_at,
        rate_limit_ms=body.rate_limit_ms,
    )
    if body.scheduled_at is None:
        await _enqueue_mailing(request, str(job.id))
    await db.commit()
    return MailingJobResponse.model_validate(job)


@router.post(
    "/{job_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Отменить рассылку (legacy alias /stop)",
    include_in_schema=False,
    dependencies=[Depends(require_permission("mailing.send"))],
)
async def cancel_mailing(
    job_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict:
    svc = _get_service(db, redis)
    await svc.cancel(current_user.org_id, job_id)
    await db.commit()
    return {"ok": True}


# ===========================================================================
# Helpers
# ===========================================================================


async def _enqueue_mailing(request: Request, job_id: str) -> None:
    """Поставить run_mailing в очередь ARQ."""
    try:
        from arq.connections import ArqRedis

        from app.redis import get_arq_pool

        arq_pool = get_arq_pool()
        arq_redis = ArqRedis(pool_or_conn=arq_pool)
        await arq_redis.enqueue_job("run_mailing", job_id)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Failed to enqueue run_mailing job_id=%s", job_id
        )


async def _resolve_candidates_by_filters(
    db: AsyncSession,
    org_id: uuid.UUID,
    filters: dict,
) -> list[uuid.UUID]:
    """
    Загрузить IDs кандидатов по фильтрам.
    Поддерживает: stage_id, responsible_id, has_new_message, avito_account_id.
    """
    from sqlalchemy import select

    from app.models.crm import Candidate

    q = select(Candidate.id).where(
        Candidate.org_id == org_id,
        Candidate.deleted_at.is_(None),
    )

    if stage_id := filters.get("stage_id"):
        q = q.where(Candidate.stage_id == uuid.UUID(str(stage_id)))

    if responsible_id := filters.get("responsible_id"):
        q = q.where(Candidate.responsible_id == uuid.UUID(str(responsible_id)))

    if filters.get("has_new_message"):
        q = q.where(Candidate.has_new_message.is_(True))

    if avito_account_id := filters.get("avito_account_id"):
        q = q.where(Candidate.avito_account_id == uuid.UUID(str(avito_account_id)))

    result = await db.execute(q)
    return list(result.scalars().all())
