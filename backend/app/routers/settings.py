"""
Роутер настроек организации.

Этапы воронки:
GET    /api/v1/settings/stages
POST   /api/v1/settings/stages
PATCH  /api/v1/settings/stages/{id}
DELETE /api/v1/settings/stages/{id}
POST   /api/v1/settings/stages/reorder

Теги:
GET    /api/v1/settings/tags
POST   /api/v1/settings/tags
PATCH  /api/v1/settings/tags/{id}
DELETE /api/v1/settings/tags/{id}

Отделы:
GET    /api/v1/settings/departments
POST   /api/v1/settings/departments
PATCH  /api/v1/settings/departments/{id}
DELETE /api/v1/settings/departments/{id}

Права ролей:
GET    /api/v1/settings/permissions          — матрица {role: {permission_key: bool}}
POST   /api/v1/settings/permissions          — обновить права роли

(Legacy) Role-permissions по роли:
GET    /api/v1/settings/role-permissions/{role}
PUT    /api/v1/settings/role-permissions/{role}
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_permission, require_role
from app.models.auth import User
from app.redis import get_redis
from app.repositories.settings import DepartmentRepository, StageRepository, TagRepository
from app.schemas.settings import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    PermissionsMatrixResponse,
    PermissionsUpdateRequest,
    StageCreate,
    StageReorderRequest,
    StageResponse,
    StageUpdate,
    TagCreate,
    TagResponse,
    TagUpdate,
)
from app.services.cache import CacheService

router = APIRouter(prefix="/settings", tags=["settings"])


async def _invalidate_settings(cache: CacheService, org_id: uuid.UUID) -> None:
    """Инвалидировать кеши настроек и фильтров."""
    await cache.invalidate_org_all(org_id)


# ===========================================================================
# Pipeline Stages
# ===========================================================================


@router.get(
    "/stages",
    response_model=list[StageResponse],
    summary="Список этапов воронки",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def list_stages(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[StageResponse]:
    org_id = request.state.org_id
    repo = StageRepository(db)
    stages = await repo.get_by_org(org_id)
    return [StageResponse.model_validate(s) for s in stages]


@router.post(
    "/stages",
    response_model=StageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать этап",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def create_stage(
    data: StageCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> StageResponse:
    org_id = request.state.org_id
    repo = StageRepository(db)

    if await repo.name_exists(org_id, data.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Этап с именем '{data.name}' уже существует",
        )

    stage = await repo.create(org_id=org_id, **data.model_dump())
    await db.commit()
    await db.refresh(stage)

    await _invalidate_settings(CacheService(redis), org_id)
    return StageResponse.model_validate(stage)


@router.post(
    "/stages/reorder",
    status_code=status.HTTP_200_OK,
    summary="Переупорядочить этапы",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def reorder_stages(
    data: StageReorderRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    org_id = request.state.org_id
    repo = StageRepository(db)
    items = [{"id": item.id, "sort_order": item.sort_order} for item in data.stages]
    await repo.reorder(org_id, items)
    await db.commit()
    await _invalidate_settings(CacheService(redis), org_id)


@router.patch(
    "/stages/{stage_id}",
    response_model=StageResponse,
    summary="Обновить этап",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def update_stage(
    stage_id: uuid.UUID,
    data: StageUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> StageResponse:
    org_id = request.state.org_id
    repo = StageRepository(db)
    stage = await repo.get_by_id_org(org_id, stage_id)

    if stage is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Этап не найден")

    update_dict = data.model_dump(exclude_none=True)
    if "name" in update_dict and await repo.name_exists(org_id, update_dict["name"], exclude_id=stage_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Этап с именем '{update_dict['name']}' уже существует",
        )

    if update_dict:
        await repo.update(stage, **update_dict)
        await db.commit()
        await db.refresh(stage)
        await _invalidate_settings(CacheService(redis), org_id)

    return StageResponse.model_validate(stage)


@router.delete(
    "/stages/{stage_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить этап",
    description="Нельзя удалить этап если есть кандидаты на этом этапе.",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def delete_stage(
    stage_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    org_id = request.state.org_id
    repo = StageRepository(db)
    stage = await repo.get_by_id_org(org_id, stage_id)

    if stage is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Этап не найден")

    # Проверяем нет ли кандидатов на этом этапе
    from sqlalchemy import func
    from app.models.crm import Candidate

    count_result = await db.execute(
        select(func.count(Candidate.id)).where(
            Candidate.stage_id == stage_id,
            Candidate.org_id == org_id,
            Candidate.deleted_at.is_(None),
        )
    )
    if count_result.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить этап: есть кандидаты на данном этапе",
        )

    await repo.delete(stage)
    await db.commit()
    await _invalidate_settings(CacheService(redis), org_id)


# Legacy PUT reorder alias
@router.put(
    "/stages/reorder",
    status_code=status.HTTP_200_OK,
    summary="Переупорядочить этапы (legacy PUT)",
    include_in_schema=False,
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def legacy_reorder_stages(
    data: StageReorderRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    org_id = request.state.org_id
    repo = StageRepository(db)
    items = [{"id": item.id, "sort_order": item.sort_order} for item in data.stages]
    await repo.reorder(org_id, items)
    await db.commit()
    await _invalidate_settings(CacheService(redis), org_id)


# ===========================================================================
# Tags
# ===========================================================================


@router.get(
    "/tags",
    response_model=list[TagResponse],
    summary="Список тегов",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def list_tags(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[TagResponse]:
    org_id = request.state.org_id
    repo = TagRepository(db)
    tags = await repo.get_by_org(org_id)
    return [TagResponse.model_validate(t) for t in tags]


@router.post(
    "/tags",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать тег",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def create_tag(
    data: TagCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> TagResponse:
    org_id = request.state.org_id
    repo = TagRepository(db)

    if await repo.name_exists(org_id, data.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Тег с именем '{data.name}' уже существует",
        )

    tag = await repo.create(org_id=org_id, **data.model_dump())
    await db.commit()
    await db.refresh(tag)
    await _invalidate_settings(CacheService(redis), org_id)
    return TagResponse.model_validate(tag)


@router.patch(
    "/tags/{tag_id}",
    response_model=TagResponse,
    summary="Обновить тег",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def update_tag(
    tag_id: uuid.UUID,
    data: TagUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> TagResponse:
    org_id = request.state.org_id
    repo = TagRepository(db)
    tag = await repo.get_by_id_org(org_id, tag_id)

    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тег не найден")

    update_dict = data.model_dump(exclude_none=True)
    if "name" in update_dict and await repo.name_exists(org_id, update_dict["name"], exclude_id=tag_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Тег с именем '{update_dict['name']}' уже существует",
        )

    if update_dict:
        await repo.update(tag, **update_dict)
        await db.commit()
        await db.refresh(tag)
        await _invalidate_settings(CacheService(redis), org_id)

    return TagResponse.model_validate(tag)


@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить тег",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def delete_tag(
    tag_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    org_id = request.state.org_id
    repo = TagRepository(db)
    tag = await repo.get_by_id_org(org_id, tag_id)

    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тег не найден")

    await repo.delete(tag)
    await db.commit()
    await _invalidate_settings(CacheService(redis), org_id)


# ===========================================================================
# Departments
# ===========================================================================


@router.get(
    "/departments",
    response_model=list[DepartmentResponse],
    summary="Список отделов",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def list_departments(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> list[DepartmentResponse]:
    org_id = request.state.org_id
    repo = DepartmentRepository(db)
    depts = await repo.get_by_org(org_id)
    return [DepartmentResponse.model_validate(d) for d in depts]


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать отдел",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def create_department(
    data: DepartmentCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> DepartmentResponse:
    org_id = request.state.org_id
    repo = DepartmentRepository(db)

    if await repo.name_exists(org_id, data.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Отдел с именем '{data.name}' уже существует",
        )

    dept = await repo.create(org_id=org_id, name=data.name)
    await db.commit()
    await db.refresh(dept)
    await _invalidate_settings(CacheService(redis), org_id)
    return DepartmentResponse.model_validate(dept)


@router.patch(
    "/departments/{dept_id}",
    response_model=DepartmentResponse,
    summary="Обновить отдел",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def update_department(
    dept_id: uuid.UUID,
    data: DepartmentUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> DepartmentResponse:
    org_id = request.state.org_id
    repo = DepartmentRepository(db)
    dept = await repo.get_by_id_org(org_id, dept_id)

    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отдел не найден")

    update_dict = data.model_dump(exclude_none=True)
    if "name" in update_dict and await repo.name_exists(org_id, update_dict["name"], exclude_id=dept_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Отдел с именем '{update_dict['name']}' уже существует",
        )

    if update_dict:
        await repo.update(dept, **update_dict)
        await db.commit()
        await db.refresh(dept)
        await _invalidate_settings(CacheService(redis), org_id)

    return DepartmentResponse.model_validate(dept)


@router.delete(
    "/departments/{dept_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить отдел",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def delete_department(
    dept_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    org_id = request.state.org_id
    repo = DepartmentRepository(db)
    dept = await repo.get_by_id_org(org_id, dept_id)

    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Отдел не найден")

    await repo.delete(dept)
    await db.commit()
    await _invalidate_settings(CacheService(redis), org_id)


# ===========================================================================
# Permissions matrix
# ===========================================================================


@router.get(
    "/permissions",
    response_model=PermissionsMatrixResponse,
    summary="Матрица прав ролей",
    description="Возвращает dict {role: {permission_key: bool}} для всей организации.",
    dependencies=[Depends(require_role("owner"))],
)
async def get_permissions_matrix(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> PermissionsMatrixResponse:
    """Матрица прав: для каждой роли — список разрешённых прав."""
    org_id = request.state.org_id

    from app.models.rbac import Permission, RolePermission

    # Загружаем все доступные права
    perms_result = await db.execute(select(Permission.code, Permission.description))
    all_perms = {row.code: row.description for row in perms_result.all()}

    # Загружаем права ролей организации
    role_perms_result = await db.execute(
        select(RolePermission.role, RolePermission.permission_code)
        .where(RolePermission.org_id == org_id)
    )

    matrix: dict[str, dict[str, bool]] = {}
    for row in role_perms_result.all():
        if row.role not in matrix:
            matrix[row.role] = {code: False for code in all_perms}
        matrix[row.role][row.permission_code] = True

    # Дополняем роли у которых нет записей
    for role in ("owner", "admin", "manager"):
        if role not in matrix:
            matrix[role] = {code: False for code in all_perms}

    return PermissionsMatrixResponse(matrix=matrix)


@router.post(
    "/permissions",
    status_code=status.HTTP_200_OK,
    summary="Обновить права роли",
    description="Полная замена списка прав для указанной роли. Инвалидирует кеш пользователей.",
    dependencies=[Depends(require_role("owner"))],
)
async def update_role_permissions(
    data: PermissionsUpdateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Обновить права роли для всей организации."""
    org_id = request.state.org_id

    from app.models.auth import User as UserModel
    from app.models.rbac import RolePermission
    from app.services.user_management import UserManagementService

    svc = UserManagementService(session=db, request=request)
    await svc.set_role_permissions(
        org_id=org_id,
        role=data.role,
        permissions=data.permissions,
        updated_by=current_user,
    )

    # Инвалидируем кеш прав всех пользователей с этой ролью
    result = await db.execute(
        select(UserModel.id).where(
            UserModel.org_id == org_id,
            UserModel.role == data.role,
        )
    )
    for row in result.all():
        await redis.delete(f"user:{row.id}:permissions")


# ===========================================================================
# Role-permissions: per-role endpoints (используются фронтендом)
# ===========================================================================


@router.get(
    "/role-permissions/{role}",
    summary="Получить права конкретной роли",
    dependencies=[Depends(require_role("owner", "admin"))],
)
async def get_role_permissions(
    role: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Возвращает {permission_codes: [...]} для указанной роли."""
    from app.models.rbac import RolePermission

    org_id = request.state.org_id
    result = await db.execute(
        select(RolePermission.permission_code).where(
            RolePermission.org_id == org_id,
            RolePermission.role == role,
        )
    )
    codes = [row[0] for row in result.all()]
    return {"permission_codes": codes}


class _RolePermissionsBody(BaseModel):
    permission_codes: list[str] = []


@router.put(
    "/role-permissions/{role}",
    status_code=status.HTTP_200_OK,
    summary="Заменить права конкретной роли",
    dependencies=[Depends(require_role("owner"))],
)
async def set_role_permissions(
    role: str,
    data: _RolePermissionsBody,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Полная замена прав роли. Тело: {permission_codes: [...]}."""
    from sqlalchemy import delete as sa_delete
    from app.models.auth import User as UserModel
    from app.models.rbac import RolePermission

    org_id = request.state.org_id

    # Удаляем старые права роли
    await db.execute(
        sa_delete(RolePermission).where(
            RolePermission.org_id == org_id,
            RolePermission.role == role,
        )
    )

    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.models.rbac import Permission

    # Убедимся что все коды существуют в таблице permissions
    for code in data.permission_codes:
        await db.execute(
            pg_insert(Permission).values(code=code).on_conflict_do_nothing()
        )

    # Вставляем новые права роли
    for code in data.permission_codes:
        stmt = pg_insert(RolePermission).values(
            org_id=org_id,
            role=role,
            permission_code=code,
        ).on_conflict_do_nothing()
        await db.execute(stmt)

    await db.commit()

    # Инвалидируем кеш пользователей с этой ролью
    users_result = await db.execute(
        select(UserModel.id).where(
            UserModel.org_id == org_id,
            UserModel.role == role,
        )
    )
    for row in users_result.all():
        await redis.delete(f"user:{row.id}:permissions")

    return {"ok": True}


# ===========================================================================
# Org settings (auto-tag etc.)
# ===========================================================================

class OrgSettingsResponse(BaseModel):
    auto_tag_id: str | None = None

class OrgSettingsUpdate(BaseModel):
    auto_tag_id: str | None = None


@router.get(
    "/org",
    response_model=OrgSettingsResponse,
    summary="Настройки организации",
    dependencies=[Depends(require_permission("crm.candidates.view"))],
)
async def get_org_settings(
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> OrgSettingsResponse:
    org_id = request.state.org_id
    auto_tag_id = await redis.get(f"org:{org_id}:auto_tag_id")
    if auto_tag_id is None:
        decoded_tag_id = None
    elif isinstance(auto_tag_id, bytes):
        decoded_tag_id = auto_tag_id.decode()
    else:
        decoded_tag_id = auto_tag_id
    return OrgSettingsResponse(auto_tag_id=decoded_tag_id)


@router.put(
    "/org",
    response_model=OrgSettingsResponse,
    summary="Обновить настройки организации",
    dependencies=[Depends(require_permission("crm.settings.manage"))],
)
async def update_org_settings(
    data: OrgSettingsUpdate,
    request: Request,
    redis: Annotated[Redis, Depends(get_redis)],
    _current_user: Annotated[User, Depends(get_current_user)],
) -> OrgSettingsResponse:
    org_id = request.state.org_id
    if data.auto_tag_id:
        await redis.set(f"org:{org_id}:auto_tag_id", data.auto_tag_id)
    else:
        await redis.delete(f"org:{org_id}:auto_tag_id")
    return OrgSettingsResponse(auto_tag_id=data.auto_tag_id)
