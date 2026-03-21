"""
Роутер вакансий.

GET  /api/v1/vacancies
POST /api/v1/vacancies/sync
GET  /api/v1/vacancies/export
GET  /api/v1/vacancies/{id}
PATCH /api/v1/vacancies/{id}
POST /api/v1/vacancies/{id}/activate
POST /api/v1/vacancies/{id}/deactivate
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.auth import User
from app.schemas.vacancy import VacancyListResponse, VacancyResponse, VacancySyncResponse, VacancyUpdate
from app.services.vacancy import VacancyService

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


def _get_vacancy_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VacancyService:
    return VacancyService(session=db)


@router.get(
    "",
    response_model=VacancyListResponse,
    summary="Список вакансий",
    dependencies=[Depends(require_permission("vacancies.view"))],
)
async def list_vacancies(
    service: Annotated[VacancyService, Depends(_get_vacancy_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
) -> VacancyListResponse:
    """Список вакансий организации из локальной таблицы."""
    return await service.list_vacancies(
        org_id=current_user.org_id,
        page=page,
        page_size=page_size,
        status=status_filter,
    )


@router.post(
    "/sync",
    response_model=VacancySyncResponse,
    summary="Синхронизировать вакансии с Avito",
    description="Для каждого аккаунта запрашивает объявления из Avito API и делает UPSERT.",
    dependencies=[Depends(require_permission("vacancies.manage"))],
)
async def sync_vacancies(
    request: Request,
    service: Annotated[VacancyService, Depends(_get_vacancy_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VacancySyncResponse:
    """Синхронизировать вакансии с Avito API для всех аккаунтов организации."""
    avito_client = getattr(request.app.state, "avito_client", None)
    return await service.sync_from_avito(
        org_id=current_user.org_id,
        avito_client=avito_client,
    )


@router.get(
    "/export",
    summary="Экспорт вакансий в CSV",
    description="Потоковый экспорт — не загружает все данные в память.",
    dependencies=[Depends(require_permission("vacancies.view"))],
)
async def export_vacancies(
    service: Annotated[VacancyService, Depends(_get_vacancy_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """Экспорт всех вакансий организации в CSV файл."""
    filename = f"vacancies_{current_user.org_id}.csv"
    return StreamingResponse(
        service.export_csv_stream(org_id=current_user.org_id),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{vacancy_id}",
    response_model=VacancyResponse,
    summary="Детали вакансии",
    dependencies=[Depends(require_permission("vacancies.view"))],
)
async def get_vacancy(
    vacancy_id: uuid.UUID,
    service: Annotated[VacancyService, Depends(_get_vacancy_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VacancyResponse:
    """Получить вакансию по ID."""
    vacancy = await service.get_vacancy(org_id=current_user.org_id, vacancy_id=vacancy_id)
    if vacancy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")
    return vacancy


@router.patch(
    "/{vacancy_id}",
    response_model=VacancyResponse,
    summary="Обновить вакансию",
    dependencies=[Depends(require_permission("vacancies.manage"))],
)
async def update_vacancy(
    vacancy_id: uuid.UUID,
    data: VacancyUpdate,
    request: Request,
    service: Annotated[VacancyService, Depends(_get_vacancy_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VacancyResponse:
    """Обновить заголовок/локацию вакансии."""
    avito_client = getattr(request.app.state, "avito_client", None)
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет данных для обновления",
        )
    result = await service.update_vacancy(
        org_id=current_user.org_id,
        vacancy_id=vacancy_id,
        updates=updates,
        avito_client=avito_client,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")
    return result


@router.post(
    "/{vacancy_id}/activate",
    status_code=status.HTTP_200_OK,
    summary="Опубликовать вакансию",
    dependencies=[Depends(require_permission("vacancies.manage"))],
)
async def activate_vacancy(
    vacancy_id: uuid.UUID,
    request: Request,
    service: Annotated[VacancyService, Depends(_get_vacancy_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Опубликовать объявление через Avito API."""
    avito_client = getattr(request.app.state, "avito_client", None)
    ok = await service.activate_vacancy(
        org_id=current_user.org_id,
        vacancy_id=vacancy_id,
        avito_client=avito_client,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")


@router.post(
    "/{vacancy_id}/deactivate",
    status_code=status.HTTP_200_OK,
    summary="Снять вакансию с публикации",
    dependencies=[Depends(require_permission("vacancies.manage"))],
)
async def deactivate_vacancy(
    vacancy_id: uuid.UUID,
    request: Request,
    service: Annotated[VacancyService, Depends(_get_vacancy_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Снять объявление с публикации через Avito API."""
    avito_client = getattr(request.app.state, "avito_client", None)
    ok = await service.deactivate_vacancy(
        org_id=current_user.org_id,
        vacancy_id=vacancy_id,
        avito_client=avito_client,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вакансия не найдена")
