"""
Роутер управления сотрудниками и профилем текущего пользователя.

GET    /api/v1/users                         — список сотрудников
POST   /api/v1/users/invite                  — пригласить
PATCH  /api/v1/users/{id}                    — обновить (роль, имя, отделы)
POST   /api/v1/users/{id}/deactivate         — деактивировать
POST   /api/v1/users/{id}/activate           — активировать
DELETE /api/v1/users/{id}                    — деактивировать (legacy alias)
POST   /api/v1/users/{id}/reactivate         — активировать (legacy alias)
GET    /api/v1/users/{id}/activity           — аудит лог сотрудника
GET    /api/v1/users/{id}/permissions        — права пользователя
PUT    /api/v1/users/{id}/permissions        — установить права
GET    /api/v1/users/{id}/departments        — отделы пользователя
PUT    /api/v1/users/{id}/departments        — установить отделы

GET    /api/v1/users/me                      — профиль текущего пользователя
PATCH  /api/v1/users/me                      — обновить профиль (full_name, avatar_url)
POST   /api/v1/users/me/change-password      — сменить пароль

GET    /api/v1/settings/role-permissions/{role}   — права роли
PUT    /api/v1/settings/role-permissions/{role}   — обновить права роли
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.audit import AuditLog
from app.models.auth import User, UserCredentials
from app.redis import get_redis
from app.schemas.user import UserMeResponse, UserMeUpdate, ChangePasswordRequest
from app.schemas.user_management import (
    RolePermissionsResponse,
    RolePermissionsUpdate,
    UserDepartmentsResponse,
    UserDepartmentsUpdate,
    UserInviteRequest,
    UserListResponse,
    UserPermissionsResponse,
    UserPermissionsUpdate,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user_management import UserManagementService

router = APIRouter(tags=["users"])


def _get_service(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserManagementService:
    return UserManagementService(session=db, request=request)


# ===========================================================================
# Current user (me) — ВАЖНО: до /{user_id} чтобы "me" не конфликтовало
# ===========================================================================


@router.get(
    "/users/me",
    response_model=UserMeResponse,
    summary="Профиль текущего пользователя",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> UserMeResponse:
    """Возвращает профиль авторизованного пользователя с last_active_at из Redis."""
    last_active_at = None
    raw = await redis.get(f"user:{current_user.id}:last_active")
    if raw:
        from datetime import datetime, timezone
        try:
            last_active_at = datetime.fromisoformat(
                raw if isinstance(raw, str) else raw.decode()
            )
        except (ValueError, AttributeError):
            pass

    return UserMeResponse(
        id=current_user.id,
        org_id=current_user.org_id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        last_login_at=current_user.last_login_at,
        last_active_at=last_active_at,
        created_at=current_user.created_at,
    )


@router.patch(
    "/users/me",
    response_model=UserMeResponse,
    summary="Обновить собственный профиль",
    description="Пользователь может обновить своё имя и URL аватара.",
)
async def update_me(
    data: UserMeUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> UserMeResponse:
    update_dict = data.model_dump(exclude_none=True)
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет данных для обновления",
        )
    for key, value in update_dict.items():
        setattr(current_user, key, value)
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    last_active_at = None
    raw = await redis.get(f"user:{current_user.id}:last_active")
    if raw:
        from datetime import datetime
        try:
            last_active_at = datetime.fromisoformat(
                raw if isinstance(raw, str) else raw.decode()
            )
        except (ValueError, AttributeError):
            pass

    return UserMeResponse(
        id=current_user.id,
        org_id=current_user.org_id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        last_login_at=current_user.last_login_at,
        last_active_at=last_active_at,
        created_at=current_user.created_at,
    )


@router.post(
    "/users/me/change-password",
    status_code=status.HTTP_200_OK,
    summary="Сменить пароль",
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Смена пароля: проверяет текущий пароль, хеширует и сохраняет новый."""
    from app.security.passwords import hash_password, verify_password

    # Загружаем credentials
    creds_result = await db.execute(
        select(UserCredentials).where(UserCredentials.user_id == current_user.id)
    )
    creds = creds_result.scalar_one_or_none()
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У вашего аккаунта нет пароля (OAuth авторизация)",
        )

    if not verify_password(data.current_password, creds.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль",
        )

    creds.password_hash = hash_password(data.new_password)
    db.add(creds)
    await db.commit()


# ===========================================================================
# List & invite
# ===========================================================================


@router.get(
    "/users/me/permissions",
    summary="Права текущего пользователя",
)
async def get_my_permissions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict:
    """Возвращает эффективные права текущего пользователя."""
    if current_user.role in ("superadmin", "owner"):
        return {"all": True, "granted": []}
    from app.dependencies import _load_permissions
    permissions = await _load_permissions(db, current_user)
    return {"all": False, "granted": permissions["granted"]}


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="Список сотрудников",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def list_users(
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
    db: Annotated[AsyncSession, Depends(get_db)],
    role: str | None = Query(default=None, description="Фильтр по роли"),
    department_id: uuid.UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
) -> UserListResponse:
    """Список всех сотрудников организации с фильтрами."""
    return await service.list_users(
        org_id=current_user.org_id,
        page=page,
        page_size=per_page,
        role=role,
        department_id=department_id,
        is_active=is_active,
    )


@router.post(
    "/users/invite",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Пригласить сотрудника",
    description=(
        "Создаёт пользователя с временным паролем и отправляет welcome email. "
        "Записывает действие в audit_log."
    ),
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def invite_user(
    data: UserInviteRequest,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    result = await service.invite_user(
        org_id=current_user.org_id,
        data=data,
        invited_by=current_user,
    )
    await db.commit()
    return result


# ===========================================================================
# PATCH / activate / deactivate
# ===========================================================================


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Обновить сотрудника",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdateRequest,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет данных для обновления",
        )
    return await service.update_user(
        org_id=current_user.org_id,
        user_id=user_id,
        updates=updates,
        updated_by=current_user,
    )


@router.post(
    "/users/{user_id}/deactivate",
    status_code=status.HTTP_200_OK,
    summary="Деактивировать сотрудника",
    description="Soft delete — пользователь теряет доступ, данные сохраняются.",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def deactivate_user(
    user_id: uuid.UUID,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.deactivate_user(
        org_id=current_user.org_id,
        user_id=user_id,
        deactivated_by=current_user,
    )


@router.post(
    "/users/{user_id}/activate",
    response_model=UserResponse,
    summary="Активировать сотрудника",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def activate_user(
    user_id: uuid.UUID,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return await service.reactivate_user(
        org_id=current_user.org_id,
        user_id=user_id,
        reactivated_by=current_user,
    )


# Legacy aliases
@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Деактивировать сотрудника (legacy DELETE)",
    include_in_schema=False,
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def legacy_deactivate_user(
    user_id: uuid.UUID,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await service.deactivate_user(
        org_id=current_user.org_id,
        user_id=user_id,
        deactivated_by=current_user,
    )


@router.post(
    "/users/{user_id}/reactivate",
    response_model=UserResponse,
    summary="Восстановить доступ сотрудника (legacy)",
    include_in_schema=False,
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def legacy_reactivate_user(
    user_id: uuid.UUID,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return await service.reactivate_user(
        org_id=current_user.org_id,
        user_id=user_id,
        reactivated_by=current_user,
    )


# ===========================================================================
# Activity
# ===========================================================================


@router.get(
    "/users/{user_id}/activity",
    summary="Активность пользователя",
    description="Paginated audit log действий конкретного сотрудника.",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def get_user_activity(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict:
    cond = [
        AuditLog.org_id == current_user.org_id,
        AuditLog.user_id == user_id,
    ]

    count_result = await db.execute(select(func.count(AuditLog.id)).where(*cond))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(AuditLog)
        .where(*cond)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = result.scalars().all()
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return {
        "items": [
            {
                "id": str(e.id),
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_display": e.entity_display,
                "human_readable": e.human_readable,
                "created_at": e.created_at.isoformat(),
            }
            for e in items
        ],
        "total": total,
        "page": page,
        "pages": pages,
    }


# ===========================================================================
# Permissions
# ===========================================================================


@router.get(
    "/users/{user_id}/permissions",
    response_model=UserPermissionsResponse,
    summary="Права пользователя",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def get_user_permissions(
    user_id: uuid.UUID,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPermissionsResponse:
    return await service.get_user_permissions(
        user_id=user_id,
        org_id=current_user.org_id,
    )


@router.put(
    "/users/{user_id}/permissions",
    response_model=UserPermissionsResponse,
    summary="Установить индивидуальные права",
    dependencies=[Depends(require_role("owner"))],
)
async def set_user_permissions(
    user_id: uuid.UUID,
    data: UserPermissionsUpdate,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPermissionsResponse:
    return await service.set_user_permissions(
        user_id=user_id,
        org_id=current_user.org_id,
        permissions=data.permissions,
        updated_by=current_user,
    )


# ===========================================================================
# Departments
# ===========================================================================


@router.get(
    "/users/{user_id}/departments",
    response_model=UserDepartmentsResponse,
    summary="Отделы пользователя",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def get_user_departments(
    user_id: uuid.UUID,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserDepartmentsResponse:
    dept_ids = await service.get_user_departments(
        user_id=user_id,
        org_id=current_user.org_id,
    )
    return UserDepartmentsResponse(department_ids=dept_ids)


@router.put(
    "/users/{user_id}/departments",
    response_model=UserDepartmentsResponse,
    summary="Установить отделы пользователя",
    dependencies=[Depends(require_role("admin", "owner"))],
)
async def set_user_departments(
    user_id: uuid.UUID,
    data: UserDepartmentsUpdate,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserDepartmentsResponse:
    dept_ids = await service.set_user_departments(
        user_id=user_id,
        org_id=current_user.org_id,
        department_ids=data.department_ids,
    )
    return UserDepartmentsResponse(department_ids=dept_ids)


# ===========================================================================
# Role permissions (settings domain)
# ===========================================================================


@router.get(
    "/settings/role-permissions/{role}",
    response_model=RolePermissionsResponse,
    summary="Права роли",
    dependencies=[Depends(require_role("owner"))],
)
async def get_role_permissions(
    role: str,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RolePermissionsResponse:
    permissions = await service.get_role_permissions(
        org_id=current_user.org_id,
        role=role,
    )
    return RolePermissionsResponse(role=role, permissions=permissions)


@router.put(
    "/settings/role-permissions/{role}",
    response_model=RolePermissionsResponse,
    summary="Обновить права роли",
    dependencies=[Depends(require_role("owner"))],
)
async def set_role_permissions(
    role: str,
    data: RolePermissionsUpdate,
    service: Annotated[UserManagementService, Depends(_get_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RolePermissionsResponse:
    permissions = await service.set_role_permissions(
        org_id=current_user.org_id,
        role=role,
        permissions=data.permissions,
        updated_by=current_user,
    )
    return RolePermissionsResponse(role=role, permissions=permissions)
