"""
Роутер проверки самозанятых.

POST /api/v1/self-employed/check
GET  /api/v1/self-employed/history
POST /api/v1/self-employed/check-bulk
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_permission
from app.models.auth import User
from app.redis import get_redis
from app.schemas.self_employed import (
    SelfEmployedBulkRequest,
    SelfEmployedBulkResponse,
    SelfEmployedCheckRequest,
    SelfEmployedCheckResponse,
    SelfEmployedHistoryResponse,
)
from app.services.self_employed import SelfEmployedService

router = APIRouter(prefix="/self-employed", tags=["self-employed"])


def _get_service(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SelfEmployedService:
    avito_client = getattr(request.app.state, "avito_client", None)
    return SelfEmployedService(
        session=db,
        avito_client=avito_client,
        request=request,
    )


@router.post(
    "/check",
    response_model=SelfEmployedCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Проверить статус самозанятого",
    description="Проверяет ИНН через API налоговой службы. Результат сохраняется в БД.",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def check_self_employed(
    data: SelfEmployedCheckRequest,
    service: Annotated[SelfEmployedService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SelfEmployedCheckResponse:
    """Проверить статус самозанятого по ИНН."""
    return await service.check_inn(
        org_id=current_user.org_id,
        inn=data.inn,
        checked_by=current_user.id,
    )


@router.get(
    "/history",
    response_model=SelfEmployedHistoryResponse,
    summary="История проверок самозанятых",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_history(
    service: Annotated[SelfEmployedService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> SelfEmployedHistoryResponse:
    """Список всех проверок ИНН организации с пагинацией."""
    return await service.get_history(
        org_id=current_user.org_id,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/check-bulk",
    response_model=SelfEmployedBulkResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Массовая проверка ИНН",
    description=(
        "Ставит задачи в очередь ARQ (до 100 ИНН). "
        "Не блокирует запрос — результаты появятся в /history."
    ),
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def check_bulk(
    data: SelfEmployedBulkRequest,
    service: Annotated[SelfEmployedService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SelfEmployedBulkResponse:
    """Поставить массовую проверку ИНН в очередь."""
    return await service.check_bulk(
        org_id=current_user.org_id,
        inns=data.inns,
        checked_by=current_user.id,
    )
