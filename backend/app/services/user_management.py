"""
UserManagementService — управление сотрудниками организации.
"""

import logging
import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.rbac import (
    Department,
    Permission,
    RolePermission,
    UserDepartment,
    UserPermission,
)
from app.repositories.user import UserRepository
from app.schemas.user_management import (
    UserInviteRequest,
    UserListResponse,
    UserPermissionsResponse,
    UserResponse,
)
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


class UserManagementService:
    """
    Сервис управления сотрудниками.
    Invite, role change, deactivate, permissions, departments.
    """

    def __init__(
        self,
        session: AsyncSession,
        request: Request,
    ) -> None:
        self._session = session
        self._request = request
        self._user_repo = UserRepository(session)
        self._audit = AuditService(db=session, request=request)

    async def list_users(
        self,
        org_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        role: str | None = None,
        department_id: uuid.UUID | None = None,
        is_active: bool | None = None,
    ) -> UserListResponse:
        """Список сотрудников организации с фильтрами."""
        from sqlalchemy import func

        conditions = [User.org_id == org_id]
        if role is not None:
            conditions.append(User.role == role)
        if is_active is not None:
            conditions.append(User.is_active == is_active)

        base_query = select(User).where(*conditions)

        if department_id is not None:
            base_query = base_query.join(
                UserDepartment,
                (UserDepartment.user_id == User.id)
                & (UserDepartment.department_id == department_id),
            )

        count_result = await self._session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self._session.execute(
            base_query
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())
        pages = (total + page_size - 1) // page_size if total > 0 else 1

        return UserListResponse(
            items=[UserResponse.model_validate(u) for u in items],
            total=total,
            page=page,
            pages=pages,
        )

    async def invite_user(
        self,
        org_id: uuid.UUID,
        data: UserInviteRequest,
        invited_by: User,
    ) -> UserResponse:
        """
        Пригласить нового сотрудника.
        Создаёт user + credentials с временным паролем.
        Отправляет welcome email. Пишет в audit_log.
        """
        raw = data.login_or_email.strip().lower()
        is_email = "@" in raw

        # Находим существующего пользователя по логину или email
        if is_email:
            result = await self._session.execute(
                select(User).where(User.email == raw)
            )
        else:
            result = await self._session.execute(
                select(User).where(User.username == raw)
            )
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )

        if user.org_id is not None and user.org_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь уже состоит в другой организации",
            )

        if user.org_id == org_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь уже добавлен в эту организацию",
            )

        # Проверяем лимит пользователей
        from sqlalchemy import func
        from app.models.auth import Organization

        count_result = await self._session.execute(
            select(func.count(User.id)).where(
                User.org_id == org_id,
                User.is_active.is_(True),
            )
        )
        active_count = count_result.scalar_one()

        org_result = await self._session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = org_result.scalar_one_or_none()
        if org and active_count >= org.max_users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Достигнут лимит пользователей: {org.max_users}",
            )

        # Привязываем к организации и назначаем роль
        user.org_id = org_id
        user.role = data.role
        user.is_active = True
        self._session.add(user)
        await self._session.flush()

        # Audit log
        await self._audit.log(
            action="user.added",
            entity_type="user",
            entity_id=user.id,
            entity_display=user.username,
            human_readable=(
                f"{invited_by.full_name} добавил сотрудника {user.username} с ролью {data.role}"
            ),
            details={"role": data.role, "login_or_email": raw},
        )

        return UserResponse.model_validate(user)

    async def update_user(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        updates: dict,
        updated_by: User,
    ) -> UserResponse:
        """Обновить данные сотрудника (роль, имя)."""
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.org_id == org_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )

        old_role = user.role
        for key, value in updates.items():
            setattr(user, key, value)
        self._session.add(user)
        await self._session.flush()

        # Инвалидируем кеш прав при смене роли
        if "role" in updates and updates["role"] != old_role:
            await self._invalidate_user_permissions_cache(user_id)

        await self._audit.log(
            action="user.updated",
            entity_type="user",
            entity_id=user.id,
            entity_display=user.email,
            human_readable=f"{updated_by.full_name} обновил данные сотрудника {user.full_name}",
            details=updates,
        )

        return UserResponse.model_validate(user)

    async def deactivate_user(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        deactivated_by: User,
    ) -> None:
        """Деактивировать сотрудника (soft delete)."""
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.org_id == org_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )

        if user.role == "owner":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя деактивировать владельца организации",
            )

        user.is_active = False
        self._session.add(user)
        await self._session.flush()

        await self._invalidate_user_permissions_cache(user_id)

        await self._audit.log(
            action="user.deactivated",
            entity_type="user",
            entity_id=user.id,
            entity_display=user.email,
            human_readable=f"{deactivated_by.full_name} деактивировал сотрудника {user.full_name}",
            details={},
        )

    async def reactivate_user(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        reactivated_by: User,
    ) -> UserResponse:
        """Восстановить деактивированного сотрудника."""
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.org_id == org_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден",
            )

        user.is_active = True
        self._session.add(user)
        await self._session.flush()

        await self._audit.log(
            action="user.reactivated",
            entity_type="user",
            entity_id=user.id,
            entity_display=user.email,
            human_readable=f"{reactivated_by.full_name} восстановил доступ сотрудника {user.full_name}",
            details={},
        )

        return UserResponse.model_validate(user)

    async def get_user_permissions(
        self, user_id: uuid.UUID, org_id: uuid.UUID
    ) -> UserPermissionsResponse:
        """Получить текущие права пользователя."""
        # Права роли
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.org_id == org_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        role_perms_result = await self._session.execute(
            select(RolePermission.permission_code).where(
                RolePermission.org_id == org_id,
                RolePermission.role == user.role,
            )
        )
        role_perms = {row[0] for row in role_perms_result.all()}

        # Персональные права
        user_perms_result = await self._session.execute(
            select(UserPermission.permission_code, UserPermission.granted).where(
                UserPermission.user_id == user_id
            )
        )
        user_perms = {row.permission_code: row.granted for row in user_perms_result.all()}

        granted = set(role_perms)
        denied: set[str] = set()
        for code, is_granted in user_perms.items():
            if is_granted:
                granted.add(code)
            else:
                granted.discard(code)
                denied.add(code)

        return UserPermissionsResponse(
            granted=sorted(granted),
            denied=sorted(denied),
        )

    async def set_user_permissions(
        self,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        permissions: list[dict],
        updated_by: User,
    ) -> UserPermissionsResponse:
        """
        Установить индивидуальные права пользователя (полная замена).
        permissions = [{"code": "...", "granted": True/False}]
        """
        # Удаляем старые
        await self._session.execute(
            delete(UserPermission).where(UserPermission.user_id == user_id)
        )

        # Вставляем новые
        for perm in permissions:
            up = UserPermission(
                user_id=user_id,
                org_id=org_id,
                permission_code=perm["code"],
                granted=perm.get("granted", True),
            )
            self._session.add(up)

        await self._session.flush()
        await self._invalidate_user_permissions_cache(user_id)

        await self._audit.log(
            action="user.permissions_updated",
            entity_type="user",
            entity_id=user_id,
            entity_display=str(user_id),
            human_readable=f"{updated_by.full_name} обновил права пользователя",
            details={"count": len(permissions)},
        )

        return await self.get_user_permissions(user_id, org_id)

    async def get_user_departments(
        self, user_id: uuid.UUID, org_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Получить список отделов пользователя."""
        result = await self._session.execute(
            select(UserDepartment.department_id).where(
                UserDepartment.user_id == user_id,
                UserDepartment.org_id == org_id,
            )
        )
        return [row[0] for row in result.all()]

    async def set_user_departments(
        self,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        department_ids: list[uuid.UUID],
    ) -> list[uuid.UUID]:
        """Заменить список отделов пользователя."""
        # Удаляем старые
        await self._session.execute(
            delete(UserDepartment).where(
                UserDepartment.user_id == user_id,
                UserDepartment.org_id == org_id,
            )
        )

        # Вставляем новые
        for dept_id in department_ids:
            ud = UserDepartment(
                user_id=user_id,
                department_id=dept_id,
                org_id=org_id,
            )
            self._session.add(ud)

        await self._session.flush()
        return department_ids

    async def get_role_permissions(
        self, org_id: uuid.UUID, role: str
    ) -> list[str]:
        """Права роли в организации."""
        result = await self._session.execute(
            select(RolePermission.permission_code).where(
                RolePermission.org_id == org_id,
                RolePermission.role == role,
            )
        )
        return [row[0] for row in result.all()]

    async def set_role_permissions(
        self,
        org_id: uuid.UUID,
        role: str,
        permissions: list[str],
        updated_by: User,
    ) -> list[str]:
        """
        Установить права роли (полная замена).
        Инвалидирует кеш прав всех пользователей с этой ролью.
        """
        # Удаляем старые
        await self._session.execute(
            delete(RolePermission).where(
                RolePermission.org_id == org_id,
                RolePermission.role == role,
            )
        )

        # Вставляем новые
        for code in permissions:
            rp = RolePermission(
                org_id=org_id,
                role=role,
                permission_code=code,
            )
            self._session.add(rp)

        await self._session.flush()

        # Инвалидируем кеш прав для всех пользователей с этой ролью
        await self._invalidate_role_permissions_cache(org_id, role)

        await self._audit.log(
            action="role.permissions_updated",
            entity_type="role",
            entity_id=None,
            entity_display=role,
            human_readable=(
                f"{updated_by.full_name} обновил права роли {role} "
                f"({len(permissions)} прав)"
            ),
            details={"role": role, "count": len(permissions)},
        )

        return permissions

    async def _invalidate_user_permissions_cache(self, user_id: uuid.UUID) -> None:
        """Инвалидировать кеш прав конкретного пользователя."""
        try:
            from app.redis import get_pool
            from redis.asyncio import Redis

            pool = get_pool()
            redis = Redis(connection_pool=pool)
            await redis.delete(f"user:{user_id}:permissions")
            await redis.aclose()
        except Exception:
            logger.warning("Failed to invalidate permissions cache for user %s", user_id)

    async def _invalidate_role_permissions_cache(
        self, org_id: uuid.UUID, role: str
    ) -> None:
        """Инвалидировать кеш прав для всех пользователей роли в организации."""
        try:
            from app.redis import get_pool
            from redis.asyncio import Redis

            # Получаем всех пользователей с этой ролью
            result = await self._session.execute(
                select(User.id).where(
                    User.org_id == org_id,
                    User.role == role,
                )
            )
            user_ids = [row[0] for row in result.all()]

            if not user_ids:
                return

            pool = get_pool()
            redis = Redis(connection_pool=pool)
            keys = [f"user:{uid}:permissions" for uid in user_ids]
            await redis.delete(*keys)
            await redis.aclose()
        except Exception:
            logger.warning(
                "Failed to invalidate role permissions cache for role=%s org=%s",
                role,
                org_id,
            )
