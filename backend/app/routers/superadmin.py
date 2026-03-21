"""
SuperAdmin роутер — управление всей платформой.

Все роуты защищены require_role('superadmin').
Все операции используют set_rls_superadmin (без RLS).

Prefix: /api/v1/superadmin
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, set_rls_superadmin
from app.dependencies import get_current_user, require_role
from app.models.auth import User
from app.repositories.error_log import ErrorLogRepository
from app.schemas.organization import (
    ImpersonateResponse,
    OrgCreate,
    OrgDetail,
    OrgListResponse,
    OrgSubscriptionUpdate,
    OrgSummary,
    OrgSuspendRequest,
    OrgUpdate,
)
from app.schemas.superadmin import (
    AuditListResponse,
    AuditLogItem,
    ErrorBulkResolveRequest,
    ErrorDetail,
    ErrorListResponse,
    ErrorResolveRequest,
    ErrorSummary,
    MailingDetail,
    MailingListResponse,
    MailingRecipientsResponse,
    OrgUserResponse,
    OrgUserRoleUpdate,
    SuperAdminStats,
)
from app.services.superadmin import SuperAdminService

router = APIRouter(
    prefix="/superadmin",
    tags=["superadmin"],
    dependencies=[Depends(require_role("superadmin"))],
)


async def _get_superadmin_db(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncSession:
    """Dependency — устанавливает RLS superadmin для сессии."""
    await set_rls_superadmin(db)
    return db


def _get_service(
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> SuperAdminService:
    return SuperAdminService(session=db)


# ═══════════════════════════════════════════════════════════════════════════
# ОРГАНИЗАЦИИ
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/organizations",
    summary="Список организаций",
    description="Полный список организаций платформы с агрегированными счётчиками.",
)
async def list_organizations(
    service: Annotated[SuperAdminService, Depends(_get_service)],
    search: str | None = Query(default=None, description="Поиск по названию или slug"),
    access_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> OrgListResponse:
    """Список всех организаций платформы."""
    items, total = await service.list_organizations(
        search=search,
        access_status=access_status,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return OrgListResponse(
        items=[OrgSummary.model_validate(item) for item in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.post(
    "/organizations",
    status_code=status.HTTP_201_CREATED,
    summary="Создать организацию",
    description="Создаёт организацию и опционально owner пользователя.",
)
async def create_organization(
    data: OrgCreate,
    service: Annotated[SuperAdminService, Depends(_get_service)],
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> dict:
    """Создать новую организацию."""
    org = await service.create_org(
        name=data.name,
        slug=data.slug,
        max_users=data.max_users,
        max_avito_accounts=data.max_avito_accounts,
        subscription_until=data.subscription_until,
        owner_email=data.owner_email,
    )
    await db.commit()
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "access_status": org.access_status,
    }


@router.get(
    "/organizations/{org_id}",
    response_model=OrgDetail,
    summary="Детали организации",
)
async def get_organization(
    org_id: uuid.UUID,
    service: Annotated[SuperAdminService, Depends(_get_service)],
) -> OrgDetail:
    """Полные данные организации со статистикой."""
    data = await service.get_org_detail(org_id)
    return OrgDetail.model_validate(data)


@router.patch(
    "/organizations/{org_id}",
    response_model=OrgDetail,
    summary="Обновить организацию",
)
async def update_organization(
    org_id: uuid.UUID,
    data: OrgUpdate,
    service: Annotated[SuperAdminService, Depends(_get_service)],
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> OrgDetail:
    """Обновить настройки организации."""
    updates = data.model_dump(exclude_none=True)
    await service.update_org(org_id, updates)
    await db.commit()
    detail = await service.get_org_detail(org_id)
    return OrgDetail.model_validate(detail)


@router.post(
    "/organizations/{org_id}/suspend",
    status_code=status.HTTP_200_OK,
    summary="Приостановить организацию",
    description=(
        "Устанавливает access_status='suspended', "
        "инвалидирует Redis кеш и отправляет WebSocket broadcast."
    ),
)
async def suspend_organization(
    org_id: uuid.UUID,
    data: OrgSuspendRequest,
    service: Annotated[SuperAdminService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Приостановить доступ организации."""
    await service.suspend_org(
        org_id=org_id,
        reason=data.reason,
        suspended_by_id=current_user.id,
    )
    await db.commit()


@router.post(
    "/organizations/{org_id}/activate",
    status_code=status.HTTP_200_OK,
    summary="Активировать организацию",
    description="Снимает приостановку, инвалидирует кеш и отправляет WebSocket broadcast.",
)
async def activate_organization(
    org_id: uuid.UUID,
    service: Annotated[SuperAdminService, Depends(_get_service)],
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Активировать приостановленную организацию."""
    await service.activate_org(org_id)
    await db.commit()


@router.patch(
    "/organizations/{org_id}/subscription",
    status_code=status.HTTP_200_OK,
    summary="Обновить подписку",
    description="Обновляет subscription_until и инвалидирует кеш статуса орга.",
)
async def update_subscription(
    org_id: uuid.UUID,
    data: OrgSubscriptionUpdate,
    service: Annotated[SuperAdminService, Depends(_get_service)],
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Обновить дату окончания подписки организации."""
    await service.update_subscription(org_id, data.subscription_until)
    await db.commit()


@router.post(
    "/organizations/{org_id}/impersonate",
    response_model=ImpersonateResponse,
    summary="Войти от имени владельца",
    description=(
        "Создаёт временный access token для owner организации (TTL 1 час). "
        "Refresh токен НЕ выдаётся. Действие записывается в audit_log."
    ),
)
async def impersonate_organization(
    org_id: uuid.UUID,
    service: Annotated[SuperAdminService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ImpersonateResponse:
    """Получить временный токен для входа от имени owner организации."""
    token = await service.impersonate(org_id=org_id, superadmin_user=current_user)
    return ImpersonateResponse(access_token=token, expires_in=3600)


# ═══════════════════════════════════════════════════════════════════════════
# ПОЛЬЗОВАТЕЛИ ОРГАНИЗАЦИИ
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/organizations/{org_id}/users",
    summary="Пользователи организации",
)
async def list_org_users(
    org_id: uuid.UUID,
    service: Annotated[SuperAdminService, Depends(_get_service)],
) -> list[OrgUserResponse]:
    """Список пользователей организации."""
    users = await service.list_org_users(org_id)
    return [OrgUserResponse.model_validate(u) for u in users]


@router.patch(
    "/organizations/{org_id}/users/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Сменить роль пользователя",
)
async def change_user_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    data: OrgUserRoleUpdate,
    service: Annotated[SuperAdminService, Depends(_get_service)],
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Сменить роль пользователя в организации."""
    await service.change_user_role(org_id, user_id, data.role)
    await db.commit()


@router.delete(
    "/organizations/{org_id}/users/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить пользователя из организации",
)
async def remove_org_user(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    service: Annotated[SuperAdminService, Depends(_get_service)],
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Деактивировать пользователя организации."""
    await service.remove_user(org_id, user_id)
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# РАССЫЛКИ (просмотр всех организаций)
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/mailings",
    response_model=MailingListResponse,
    summary="Все рассылки платформы",
    description="Список рассылок всех организаций без RLS.",
)
async def list_mailings(
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
    org_id: uuid.UUID | None = Query(default=None),
    mailing_status: str | None = Query(default=None, alias="status"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> MailingListResponse:
    """Список рассылок всех организаций."""
    # Заглушка — реализация зависит от модели Mailing (Phase 3)
    return MailingListResponse(items=[], total=0, page=page, pages=1)


@router.get(
    "/mailings/{mailing_id}",
    response_model=MailingDetail,
    summary="Детали рассылки",
)
async def get_mailing(
    mailing_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> MailingDetail:
    """Детали рассылки с прогрессом из Redis."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рассылка не найдена")


@router.get(
    "/mailings/{mailing_id}/recipients",
    response_model=MailingRecipientsResponse,
    summary="Получатели рассылки",
)
async def get_mailing_recipients(
    mailing_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> MailingRecipientsResponse:
    """Постраничный список получателей рассылки."""
    return MailingRecipientsResponse(items=[], total=0, page=page, pages=1)


@router.post(
    "/mailings/{mailing_id}/pause",
    status_code=status.HTTP_200_OK,
    summary="Приостановить рассылку",
)
async def pause_mailing(
    mailing_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Приостановить выполнение рассылки."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рассылка не найдена")


@router.post(
    "/mailings/{mailing_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Отменить рассылку",
)
async def cancel_mailing(
    mailing_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Отменить рассылку."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рассылка не найдена")


@router.post(
    "/mailings/{mailing_id}/stop",
    status_code=status.HTTP_200_OK,
    summary="Принудительно остановить рассылку",
    description=(
        "Принудительно останавливает любую рассылку на платформе. "
        "Устанавливает статус 'cancelled' и записывает finished_at."
    ),
)
async def stop_mailing(
    mailing_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Принудительно остановить рассылку любой организации."""
    from sqlalchemy import text

    result = await db.execute(
        text("""
            UPDATE mailing_jobs
            SET status = 'cancelled',
                finished_at = now(),
                updated_at = now()
            WHERE id = :id
              AND status IN ('pending', 'running', 'paused', 'resuming')
            RETURNING id
        """),
        {"id": str(mailing_id)},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Рассылка не найдена или уже завершена",
        )
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# ОШИБКИ
# ═══════════════════════════════════════════════════════════════════════════

def _get_error_repo(
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> ErrorLogRepository:
    return ErrorLogRepository(db)


@router.get(
    "/errors",
    response_model=ErrorListResponse,
    summary="Журнал ошибок",
    description="Ошибки всех организаций, отсортированные по дате (новые сверху).",
)
async def list_errors(
    error_repo: Annotated[ErrorLogRepository, Depends(_get_error_repo)],
    org_id: uuid.UUID | None = Query(default=None),
    source: str | None = Query(default=None),
    layer: str | None = Query(default=None),
    resolved: bool | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> ErrorListResponse:
    """Список ошибок системы с фильтрами."""
    date_from_d = date_from.date() if date_from else None
    date_to_d = date_to.date() if date_to else None

    items, total, unresolved_count = await error_repo.list_errors(
        org_id=org_id,
        source=source,
        layer=layer,
        resolved=resolved,
        date_from=date_from_d,
        date_to=date_to_d,
        page=page,
        page_size=page_size,
    )

    return ErrorListResponse(
        items=[
            ErrorSummary(
                id=e.id,
                org_id=e.org_id,
                org_name=None,
                source=e.source,
                layer=e.layer,
                handler=e.handler,
                error_type=e.error_type,
                error_message=e.error_message,
                resolved=e.resolved,
                created_at=e.created_at,
            )
            for e in items
        ],
        total=total,
        unresolved_count=unresolved_count,
    )


@router.get(
    "/errors/{error_id}",
    response_model=ErrorDetail,
    summary="Детали ошибки",
)
async def get_error(
    error_id: uuid.UUID,
    error_repo: Annotated[ErrorLogRepository, Depends(_get_error_repo)],
) -> ErrorDetail:
    """Полные детали ошибки: stack_trace, request_id, org_name."""
    error = await error_repo.get_by_id(error_id)
    if error is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ошибка не найдена")
    return ErrorDetail.model_validate(error, from_attributes=True)


@router.post(
    "/errors/{error_id}/resolve",
    status_code=status.HTTP_200_OK,
    summary="Разрешить ошибку",
)
async def resolve_error(
    error_id: uuid.UUID,
    data: ErrorResolveRequest,
    error_repo: Annotated[ErrorLogRepository, Depends(_get_error_repo)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Отметить ошибку как решённую."""
    error = await error_repo.resolve(
        error_id=error_id,
        resolved_by=current_user.id,
        note=data.note,
    )
    if error is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ошибка не найдена")
    await db.commit()


@router.post(
    "/errors/resolve-bulk",
    status_code=status.HTTP_200_OK,
    summary="Массовое разрешение ошибок",
)
async def resolve_errors_bulk(
    data: ErrorBulkResolveRequest,
    error_repo: Annotated[ErrorLogRepository, Depends(_get_error_repo)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(_get_superadmin_db)],
) -> None:
    """Массово отметить ошибки как решённые."""
    await error_repo.resolve_bulk(ids=data.ids, resolved_by=current_user.id)
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# СТАТИСТИКА
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/stats",
    response_model=SuperAdminStats,
    summary="Глобальная статистика платформы",
)
async def get_stats(
    service: Annotated[SuperAdminService, Depends(_get_service)],
) -> SuperAdminStats:
    """Сводная статистика по всей платформе."""
    data = await service.get_stats()
    return SuperAdminStats.model_validate(data)


# ═══════════════════════════════════════════════════════════════════════════
# АУДИТ
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/audit",
    response_model=AuditListResponse,
    summary="Журнал аудита",
    description="Записи audit_log всех организаций с фильтрами.",
)
async def list_audit(
    service: Annotated[SuperAdminService, Depends(_get_service)],
    org_id: uuid.UUID | None = Query(default=None),
    user_id: uuid.UUID | None = Query(default=None),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> AuditListResponse:
    """Журнал аудита с фильтрацией по организации, пользователю, действию."""
    items, total = await service.list_audit(
        org_id=org_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return AuditListResponse(
        items=[AuditLogItem.model_validate(e) for e in items],
        total=total,
        page=page,
        pages=pages,
    )
