"""
Роутер кандидатов CRM.

GET    /api/v1/candidates/stages               — этапы воронки организации
GET    /api/v1/candidates/tags                 — теги организации
GET    /api/v1/candidates                      — список с фильтрами и пагинацией
POST   /api/v1/candidates                      — создать кандидата
DELETE /api/v1/candidates/{id}                 — удалить (soft delete)
GET    /api/v1/candidates/{id}                 — один кандидат
PATCH  /api/v1/candidates/{id}                 — обновить
POST   /api/v1/candidates/bulk-edit            — массовое обновление по IDs
POST   /api/v1/candidates/bulk-edit-by-filters — массовое по фильтрам
POST   /api/v1/candidates/{id}/tags/{tag_id}   — добавить тег
DELETE /api/v1/candidates/{id}/tags/{tag_id}   — удалить тег
GET    /api/v1/candidates/{id}/history         — audit log кандидата
"""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.auth import User
from app.redis import get_redis
from app.repositories.audit import AuditRepository
from app.repositories.candidate import CandidateRepository
from app.schemas.candidate import (
    BulkEditByFiltersRequest,
    BulkEditRequest,
    BulkEditResponse,
    CandidateCreate,
    CandidateEdit,
    CandidateFilters,
    CandidateListResponse,
    CandidateResponse,
)
from app.services.audit import AuditService
from app.services.cache import CacheService
from app.services.candidate import CandidateService

router = APIRouter(prefix="/candidates", tags=["candidates"])


def _get_candidate_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
) -> CandidateService:
    return CandidateService(
        repo=CandidateRepository(db),
        cache=CacheService(redis),
        audit=AuditService(db, request),
        encryption_key=settings.encryption_key_bytes,
        search_hash_key=settings.search_hash_key_bytes,
        db=db,
    )


@router.get(
    "/stages",
    summary="Этапы воронки организации",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def list_stages(
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    org_id: uuid.UUID = request.state.org_id
    stages = await service._repo.get_stages(org_id)
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "color": s.color,
            "sort_order": s.sort_order,
            "is_default": s.is_default,
        }
        for s in stages
    ]


@router.get(
    "/tags",
    summary="Теги организации",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def list_tags(
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    org_id: uuid.UUID = request.state.org_id
    tags = await service._repo.get_tags(org_id)
    return [
        {"id": str(t.id), "name": t.name, "color": t.color}
        for t in tags
    ]


@router.get(
    "",
    response_model=CandidateListResponse,
    summary="Список кандидатов",
    description="Возвращает страницу кандидатов с применёнными фильтрами.",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def list_candidates(
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
    # Пагинация
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    page_size: int = Query(default=50, ge=1, le=200, description="Размер страницы"),
    # Фильтры (query params)
    stage_id: uuid.UUID | None = Query(default=None),
    responsible_id: uuid.UUID | None = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
    avito_account_id: uuid.UUID | None = Query(default=None),
    has_new_message: bool | None = Query(default=None),
    only_unread: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=255),
    location: str | None = Query(default=None, max_length=255),
    vacancy: str | None = Query(default=None, max_length=500),
    tag_ids: list[uuid.UUID] | None = Query(default=None),
    created_at_from: date | None = Query(default=None),
    created_at_to: date | None = Query(default=None),
    due_date_from: date | None = Query(default=None),
    due_date_to: date | None = Query(default=None),
) -> CandidateListResponse:
    filters = CandidateFilters(
        stage_id=stage_id,
        responsible_id=responsible_id,
        department_id=department_id,
        avito_account_id=avito_account_id,
        has_new_message=has_new_message,
        only_unread=only_unread,
        search=search,
        location=location,
        vacancy=vacancy,
        tag_ids=tag_ids,
        created_at_from=datetime(created_at_from.year, created_at_from.month, created_at_from.day) if created_at_from else None,
        created_at_to=datetime(created_at_to.year, created_at_to.month, created_at_to.day, 23, 59, 59) if created_at_to else None,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
    )
    return await service.get_list(request, filters, page, page_size)


@router.post(
    "",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать кандидата",
    dependencies=[Depends(require_permission("crm.candidates.create"))],
)
async def create_candidate(
    data: CandidateCreate,
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> CandidateResponse:
    return await service.create(request, data)


@router.get(
    "/export",
    summary="Экспорт кандидатов в CSV",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def export_candidates(
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
    stage_id: uuid.UUID | None = Query(default=None),
    responsible_id: uuid.UUID | None = Query(default=None),
    department_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=255),
) -> StreamingResponse:
    import csv
    import io

    org_id: uuid.UUID = request.state.org_id
    filters = CandidateFilters(
        stage_id=stage_id,
        responsible_id=responsible_id,
        department_id=department_id,
        search=search,
    )
    # Загружаем до 10000 записей для экспорта
    candidates, _ = await service._repo.get_list(
        org_id=org_id,
        filters=filters,
        page=1,
        page_size=10000,
        user_departments=None,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "ФИО", "Телефон", "Этап", "Ответственный", "Дата создания"])
    for c in candidates:
        writer.writerow([
            str(c.id),
            c.name or "",
            "",  # телефон зашифрован, не экспортируем без отдельного права
            str(c.stage_id) if c.stage_id else "",
            str(c.responsible_id) if c.responsible_id else "",
            c.created_at.strftime("%Y-%m-%d") if c.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=candidates.csv"},
    )


@router.delete(
    "/{candidate_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить кандидата (soft delete)",
    dependencies=[Depends(require_permission("crm.candidates.delete"))],
)
async def delete_candidate(
    candidate_id: uuid.UUID,
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.soft_delete(request, candidate_id)


@router.get(
    "/{candidate_id}",
    response_model=CandidateResponse,
    summary="Кандидат по ID",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_candidate(
    candidate_id: uuid.UUID,
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> CandidateResponse:
    return await service.get_one(request, candidate_id)


@router.patch(
    "/{candidate_id}",
    response_model=CandidateResponse,
    summary="Обновить кандидата",
    dependencies=[Depends(require_permission("crm.candidates.edit"))],
)
async def update_candidate(
    candidate_id: uuid.UUID,
    data: CandidateEdit,
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> CandidateResponse:
    return await service.update(request, candidate_id, data)


@router.post(
    "/bulk-edit",
    response_model=BulkEditResponse,
    summary="Массовое обновление по IDs",
    dependencies=[Depends(require_permission("crm.candidates.edit"))],
)
async def bulk_edit(
    data: BulkEditRequest,
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> BulkEditResponse:
    return await service.bulk_update(request, data)


@router.post(
    "/bulk-edit-by-filters",
    response_model=BulkEditResponse,
    summary="Массовое обновление по фильтрам",
    dependencies=[Depends(require_permission("crm.candidates.edit"))],
)
async def bulk_edit_by_filters(
    data: BulkEditByFiltersRequest,
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> BulkEditResponse:
    return await service.bulk_update_by_filters(request, data)


@router.post(
    "/{candidate_id}/tags/{tag_id}",
    status_code=status.HTTP_200_OK,
    summary="Добавить тег кандидату",
    dependencies=[Depends(require_permission("crm.candidates.edit"))],
)
async def add_tag(
    candidate_id: uuid.UUID,
    tag_id: uuid.UUID,
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.add_tag(request, candidate_id, tag_id)


@router.delete(
    "/{candidate_id}/tags/{tag_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить тег с кандидата",
    dependencies=[Depends(require_permission("crm.candidates.edit"))],
)
async def remove_tag(
    candidate_id: uuid.UUID,
    tag_id: uuid.UUID,
    request: Request,
    service: Annotated[CandidateService, Depends(_get_candidate_service)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.remove_tag(request, candidate_id, tag_id)


@router.get(
    "/{candidate_id}/history",
    summary="История действий по кандидату",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_history(
    candidate_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict:
    org_id = request.state.org_id
    audit_repo = AuditRepository(db)
    items, total = await audit_repo.get_for_entity(
        org_id=org_id,
        entity_type="candidate",
        entity_id=candidate_id,
        page=page,
        page_size=page_size,
    )
    import math
    pages = max(1, math.ceil(total / page_size))
    return {
        "items": [
            {
                "id": str(item.id),
                "action": item.action,
                "user_full_name": item.user_full_name,
                "user_role": item.user_role,
                "human_readable": item.human_readable,
                "details": item.details,
                "ip_address": str(item.ip_address) if item.ip_address else None,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }
