"""
SuperAdminService — управление организациями, impersonation, статистика.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.auth import Organization, User
from app.models.error_log import ErrorLog
from app.repositories.error_log import ErrorLogRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class SuperAdminService:
    """
    Сервис суперадмина.
    Работает без RLS — видит данные всех организаций.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._org_repo = OrganizationRepository(session)
        self._user_repo = UserRepository(session)
        self._error_repo = ErrorLogRepository(session)

    # ─── Организации ─────────────────────────────────────────────────────────

    async def list_organizations(
        self,
        search: str | None = None,
        access_status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """
        Список организаций с агрегированными счётчиками.
        Возвращает (items, total).
        """
        base_q = select(Organization)
        count_q = select(func.count(Organization.id))

        if search:
            pattern = f"%{search}%"
            base_q = base_q.where(
                Organization.name.ilike(pattern) | Organization.slug.ilike(pattern)
            )
            count_q = count_q.where(
                Organization.name.ilike(pattern) | Organization.slug.ilike(pattern)
            )

        if access_status:
            base_q = base_q.where(Organization.access_status == access_status)
            count_q = count_q.where(Organization.access_status == access_status)

        total_result = await self._session.execute(count_q)
        total = total_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self._session.execute(
            base_q.order_by(Organization.created_at.desc()).offset(offset).limit(page_size)
        )
        orgs = list(result.scalars().all())

        # Агрегируем счётчики пользователей
        org_ids = [o.id for o in orgs]
        users_count_map: dict[uuid.UUID, int] = {}
        if org_ids:
            uc_result = await self._session.execute(
                select(User.org_id, func.count(User.id).label("cnt"))
                .where(User.org_id.in_(org_ids))
                .group_by(User.org_id)
            )
            users_count_map = {row.org_id: row.cnt for row in uc_result.all()}

        items = []
        for org in orgs:
            items.append({
                "id": org.id,
                "name": org.name,
                "slug": org.slug,
                "access_status": org.access_status,
                "subscription_until": org.subscription_until,
                "users_count": users_count_map.get(org.id, 0),
                "avito_accounts_count": 0,  # TODO: агрегировать из avito_accounts
                "created_at": org.created_at,
                "suspended_reason": org.suspend_reason,
            })

        return items, total

    async def get_org_detail(self, org_id: uuid.UUID) -> dict:
        """Полные данные организации со статистикой."""
        org = await self._org_repo.get_by_id(org_id)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Организация не найдена",
            )

        # Счётчики
        uc_result = await self._session.execute(
            select(func.count(User.id)).where(User.org_id == org_id)
        )
        users_count = uc_result.scalar_one()

        return {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "access_status": org.access_status,
            "subscription_until": org.subscription_until,
            "settings": org.settings,
            "max_users": org.max_users,
            "max_avito_accounts": org.max_avito_accounts,
            "suspended_at": org.suspended_at,
            "suspended_by": org.suspended_by,
            "suspend_reason": org.suspend_reason,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
            "users_count": users_count,
            "avito_accounts_count": 0,
            "candidates_count": 0,
            "mailings_count": 0,
        }

    async def create_org(
        self,
        name: str,
        slug: str | None,
        max_users: int,
        max_avito_accounts: int,
        subscription_until: datetime | None,
        owner_email: str | None,
    ) -> Organization:
        """Создать организацию, опционально — owner пользователя."""
        if slug is None:
            slug = await self._org_repo.generate_unique_slug(name)
        elif await self._org_repo.slug_exists(slug):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slug уже занят",
            )

        org = Organization(
            name=name,
            slug=slug,
            access_status="active",
            max_users=max_users,
            max_avito_accounts=max_avito_accounts,
            subscription_until=subscription_until,
        )
        self._session.add(org)
        await self._session.flush()

        # Засеиваем дефолтные права ролей для новой организации
        await self._seed_default_role_permissions(org.id)

        if owner_email:
            import secrets
            from app.models.auth import UserCredentials
            from app.security.passwords import hash_password

            # Проверяем, существует ли пользователь с таким email
            existing_result = await self._session.execute(
                select(User).where(User.email == owner_email.lower())
            )
            existing_user = existing_result.scalars().first()

            if existing_user is not None:
                # Привязываем существующего пользователя к новой организации
                existing_user.org_id = org.id
                existing_user.role = "owner"
                existing_user.is_active = True
                await self._session.flush()
            else:
                username = owner_email.split("@")[0].lower()
                # Проверяем уникальность username
                if await self._user_repo.username_exists(username):
                    username = f"{username}_{secrets.token_hex(4)}"

                new_owner = User(
                    org_id=org.id,
                    email=owner_email.lower(),
                    username=username,
                    full_name=owner_email,
                    role="owner",
                    is_active=True,
                )
                self._session.add(new_owner)
                await self._session.flush()

                temp_password = secrets.token_urlsafe(12)
                creds = UserCredentials(
                    user_id=new_owner.id,
                    password_hash=hash_password(temp_password),
                )
                self._session.add(creds)
                await self._session.flush()

        return org

    async def update_org(self, org_id: uuid.UUID, updates: dict) -> Organization:
        """Обновить настройки организации."""
        org = await self._org_repo.get_by_id(org_id)
        if org is None:
            raise HTTPException(status_code=404, detail="Организация не найдена")

        return await self._org_repo.update(org, **{k: v for k, v in updates.items() if v is not None})

    async def suspend_org(
        self,
        org_id: uuid.UUID,
        reason: str,
        suspended_by_id: uuid.UUID,
    ) -> None:
        """
        Приостановить организацию.
        Инвалидирует кеш статуса и отправляет WebSocket broadcast.
        """
        org = await self._org_repo.get_by_id(org_id)
        if org is None:
            raise HTTPException(status_code=404, detail="Организация не найдена")

        await self._org_repo.update(
            org,
            access_status="suspended",
            suspended_at=datetime.now(timezone.utc),
            suspended_by=suspended_by_id,
            suspend_reason=reason,
        )

        # Инвалидируем Redis кеш статуса орга
        await self._delete_org_status_cache(org_id)

        # WebSocket broadcast
        await self._broadcast_org_access_changed(
            org_id,
            status="suspended",
            reason=reason,
        )

    async def activate_org(self, org_id: uuid.UUID) -> None:
        """
        Активировать приостановленную организацию.
        Инвалидирует кеш и отправляет WebSocket broadcast.
        """
        org = await self._org_repo.get_by_id(org_id)
        if org is None:
            raise HTTPException(status_code=404, detail="Организация не найдена")

        await self._org_repo.update(
            org,
            access_status="active",
            suspended_at=None,
            suspended_by=None,
            suspend_reason=None,
        )

        await self._delete_org_status_cache(org_id)
        await self._broadcast_org_access_changed(org_id, status="active")

    async def update_subscription(
        self, org_id: uuid.UUID, subscription_until: datetime | None
    ) -> None:
        """Обновить дату подписки организации."""
        org = await self._org_repo.get_by_id(org_id)
        if org is None:
            raise HTTPException(status_code=404, detail="Организация не найдена")

        await self._org_repo.update(org, subscription_until=subscription_until)
        await self._delete_org_status_cache(org_id)

    async def impersonate(
        self,
        org_id: uuid.UUID,
        superadmin_user: User,
    ) -> str:
        """
        Создать временный access token для owner организации.
        Записывает в audit_log. Возвращает только access_token (без refresh).
        """
        # Получаем owner орга
        owner_result = await self._session.execute(
            select(User).where(
                User.org_id == org_id,
                User.role == "owner",
                User.is_active.is_(True),
            )
        )
        owner = owner_result.scalars().first()

        if owner is None:
            # Попытка найти любого активного пользователя в организации
            any_user_result = await self._session.execute(
                select(User).where(
                    User.org_id == org_id,
                    User.is_active.is_(True),
                ).limit(1)
            )
            owner = any_user_result.scalars().first()

        if owner is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="В организации нет активных пользователей для входа",
            )

        # Загружаем org
        org = await self._org_repo.get_by_id(org_id)
        org_name = org.name if org else str(org_id)

        # Создаём access token с доп. claim impersonated_by
        from app.config import get_settings
        from app.security.jwt import JWTService
        from jose import jwt as jose_jwt

        settings = get_settings()
        now = datetime.now(timezone.utc)
        expire = now + timedelta(hours=1)

        payload = {
            "sub": str(owner.id),
            "org_id": str(org_id),
            "role": owner.role,
            "type": "access",
            "impersonated_by": str(superadmin_user.id),
            "iat": now,
            "exp": expire,
        }
        token = jose_jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

        # Пишем в audit_log
        from app.database import get_session_factory
        from sqlalchemy import text as sa_text

        factory = get_session_factory()
        async with factory() as audit_session:
            await audit_session.execute(sa_text("SET LOCAL app.is_superadmin = 'true'"))
            entry = AuditLog(
                org_id=org_id,
                user_id=superadmin_user.id,
                user_full_name=superadmin_user.full_name,
                user_role=superadmin_user.role,
                action="org.impersonated",
                entity_type="organization",
                entity_id=org_id,
                entity_display=org_name,
                details={"impersonated_user_id": str(owner.id)},
                human_readable=(
                    f"SuperAdmin {superadmin_user.full_name} вошёл от имени "
                    f"owner организации {org_name}"
                ),
            )
            audit_session.add(entry)
            await audit_session.commit()

        return token

    # ─── Пользователи орга ───────────────────────────────────────────────────

    async def list_org_users(self, org_id: uuid.UUID) -> list[dict]:
        """Список пользователей организации."""
        result = await self._session.execute(
            select(User).where(User.org_id == org_id).order_by(User.created_at)
        )
        users = list(result.scalars().all())
        return [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active,
                "last_login_at": u.last_login_at,
                "created_at": u.created_at,
            }
            for u in users
        ]

    async def change_user_role(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        new_role: str,
    ) -> None:
        """Сменить роль пользователя организации."""
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.org_id == org_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        user.role = new_role
        self._session.add(user)
        await self._session.flush()

        # Инвалидируем кеш прав
        await self._invalidate_user_cache(user_id)

    async def remove_user(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Удалить пользователя из организации (soft delete)."""
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.org_id == org_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        user.is_active = False
        self._session.add(user)
        await self._session.flush()
        await self._invalidate_user_cache(user_id)

    # ─── Статистика ───────────────────────────────────────────────────────────

    async def get_stats(self) -> dict:
        """Глобальная статистика для дашборда суперадмина."""
        # Организации
        org_total = await self._scalar(select(func.count(Organization.id)))
        org_active = await self._scalar(
            select(func.count(Organization.id)).where(Organization.access_status == "active")
        )
        org_suspended = await self._scalar(
            select(func.count(Organization.id)).where(Organization.access_status == "suspended")
        )
        org_expired = await self._scalar(
            select(func.count(Organization.id)).where(Organization.access_status == "expired")
        )

        # Пользователи
        user_total = await self._scalar(select(func.count(User.id)))

        # Ошибки
        error_today = await self._error_repo.count_today()
        error_unresolved = await self._error_repo.count_unresolved()

        return {
            "organizations": {
                "total": org_total,
                "active": org_active,
                "suspended": org_suspended,
                "expired": org_expired,
            },
            "users": {"total": user_total},
            "mailings": {"today_started": 0, "running_now": 0, "total": 0},
            "webhooks": {"last_hour_count": 0},
            "errors": {
                "today_count": error_today,
                "unresolved_count": error_unresolved,
            },
        }

    # ─── Аудит ────────────────────────────────────────────────────────────────

    async def list_audit(
        self,
        org_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        """Список записей audit_log с фильтрами."""
        cond = []
        if org_id:
            cond.append(AuditLog.org_id == org_id)
        if user_id:
            cond.append(AuditLog.user_id == user_id)
        if action:
            cond.append(AuditLog.action == action)
        if entity_type:
            cond.append(AuditLog.entity_type == entity_type)
        if date_from:
            cond.append(AuditLog.created_at >= date_from)
        if date_to:
            cond.append(AuditLog.created_at <= date_to)

        count_result = await self._session.execute(
            select(func.count(AuditLog.id)).where(*cond)
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self._session.execute(
            select(AuditLog)
            .where(*cond)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())

        return items, total

    # ─── Приватные методы ─────────────────────────────────────────────────────

    async def _seed_default_role_permissions(self, org_id: uuid.UUID) -> None:
        """Засеить дефолтные права ролей для новой организации."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from app.models.rbac import RolePermission

        MANAGER_PERMISSIONS = [
            "crm.candidates.view",
            "crm.candidates.create",
            "crm.candidates.edit",
            "crm.candidates.delete",
            "crm.stages.manage",
            "crm.tags.manage",
            "mailing.view",
            "mailing.send",
            "mailing.manage",
            "vacancies.view",
            "vacancies.manage",
            "messaging.view",
            "messaging.send",
            "messaging.auto_response",
            "self_employed.check",
            "analytics.view",
        ]

        ADMIN_EXTRA_PERMISSIONS = [
            "avito.accounts.view",
            "avito.accounts.manage",
            "avito.webhooks.manage",
            "admin.users.view",
            "admin.users.manage",
            "admin.departments.manage",
            "admin.settings.manage",
            "admin.audit.view",
            "admin.errors.view",
        ]

        from app.models.rbac import Permission

        all_codes = list(dict.fromkeys(MANAGER_PERMISSIONS + ADMIN_EXTRA_PERMISSIONS))
        for code in all_codes:
            await self._session.execute(
                pg_insert(Permission).values(code=code).on_conflict_do_nothing()
            )

        role_codes: list[tuple[str, str]] = (
            [("manager", code) for code in MANAGER_PERMISSIONS]
            + [("admin", code) for code in MANAGER_PERMISSIONS + ADMIN_EXTRA_PERMISSIONS]
        )

        for role, code in role_codes:
            await self._session.execute(
                pg_insert(RolePermission)
                .values(org_id=org_id, role=role, permission_code=code)
                .on_conflict_do_nothing()
            )
        await self._session.flush()

    async def _scalar(self, query) -> int:
        result = await self._session.execute(query)
        return result.scalar_one() or 0

    async def _delete_org_status_cache(self, org_id: uuid.UUID) -> None:
        """Удалить кеш статуса организации из Redis."""
        try:
            from app.redis import get_pool
            from redis.asyncio import Redis

            pool = get_pool()
            redis = Redis(connection_pool=pool)
            await redis.delete(f"org_status:{org_id}")
            await redis.aclose()
        except Exception:
            logger.warning("Failed to delete org_status cache for %s", org_id)

    async def _broadcast_org_access_changed(
        self,
        org_id: uuid.UUID,
        status: str,
        reason: str | None = None,
    ) -> None:
        """Отправить WebSocket broadcast всем пользователям организации."""
        try:
            from app.routers.ws import ws_manager

            payload: dict = {"type": "org_access_changed", "status": status}
            if reason:
                payload["reason"] = reason
            await ws_manager.broadcast_org(org_id, payload)
        except Exception:
            logger.warning(
                "Failed to broadcast org_access_changed for org %s", org_id
            )

    async def _invalidate_user_cache(self, user_id: uuid.UUID) -> None:
        """Инвалидировать Redis кеши пользователя."""
        try:
            from app.redis import get_pool
            from redis.asyncio import Redis

            pool = get_pool()
            redis = Redis(connection_pool=pool)
            await redis.delete(f"user:{user_id}", f"user:{user_id}:permissions")
            await redis.aclose()
        except Exception:
            logger.warning("Failed to invalidate user cache for %s", user_id)
