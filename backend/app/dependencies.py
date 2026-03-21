"""
FastAPI зависимости (Depends).
Предоставляют: сессию БД, Redis, текущего пользователя, проверку ролей/прав.
"""

import json
import logging
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db, set_rls_org, set_rls_superadmin
from app.models.auth import User
from app.models.rbac import RolePermission, UserPermission
from app.redis import get_redis
from app.security.jwt import JWTService

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Кеш прав пользователя в Redis
USER_PERMISSIONS_TTL = 300  # 5 минут
USER_CACHE_TTL = 300  # 5 минут


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """
    Dependency — возвращает текущего аутентифицированного пользователя.

    1. Декодирует JWT из Authorization: Bearer
    2. Проверяет кеш Redis (TTL 5 мин)
    3. Загружает из БД если нет в кеше
    4. Устанавливает RLS контекст для сессии
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не авторизован",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exc

    # Декодируем JWT
    try:
        jwt_service = JWTService(settings)
        payload = jwt_service.decode_access_token(token)
    except JWTError:
        raise credentials_exc

    user_id = payload.sub
    org_id = payload.org_id

    # Проверяем кеш
    cache_key = f"user:{user_id}"
    cached_data = await redis.get(cache_key)

    if cached_data:
        try:
            user_data = json.loads(cached_data)
            # Для кешированных данных создаём частичный объект User
            # Полная загрузка из БД нужна только при промахе кеша
        except Exception:
            cached_data = None

    # Загружаем из БД
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(User)
        .options(selectinload(User.organization))
        .where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exc

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт деактивирован",
        )

    # Пользователь без организации не имеет доступа к API (кроме /auth/*)
    if user.role != "superadmin" and user.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт не привязан к организации",
        )

    # Устанавливаем RLS контекст
    if user.role == "superadmin":
        await set_rls_superadmin(db)
    elif user.org_id:
        await set_rls_org(db, user.org_id)

    # Кешируем базовые данные пользователя
    await redis.setex(
        cache_key,
        USER_CACHE_TTL,
        json.dumps({"id": str(user.id), "org_id": str(user.org_id) if user.org_id else None, "role": user.role}),
    )

    return user


def require_role(*roles: str):
    """
    Dependency factory для проверки роли пользователя.

    Использование:
        @router.get("/admin", dependencies=[Depends(require_role("admin", "owner"))])
    """

    async def _check_role(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles and current_user.role != "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Требуется роль: {', '.join(roles)}",
            )
        return current_user

    return _check_role


def require_permission(code: str):
    """
    Dependency factory для проверки конкретного права доступа.

    Алгоритм:
    1. Superadmin — всегда пропускает
    2. Проверяет user_permissions (персональные переопределения)
    3. Если нет — проверяет role_permissions
    4. Кеширует результат в Redis TTL 5 мин

    Использование:
        @router.post("/mailing", dependencies=[Depends(require_permission("mailing.send"))])
    """

    async def _check_permission(
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
        redis: Annotated[Redis, Depends(get_redis)],
    ) -> User:
        # Superadmin и owner имеют доступ ко всему
        if current_user.role in ("superadmin", "owner"):
            return current_user

        user_id = str(current_user.id)
        org_id = str(current_user.org_id) if current_user.org_id else ""
        cache_key = f"user:{user_id}:permissions"

        # Пробуем кеш
        cached = await redis.get(cache_key)
        if cached:
            permissions: dict = json.loads(cached)
        else:
            # Загружаем права пользователя
            permissions = await _load_permissions(db, current_user)
            await redis.setex(
                cache_key,
                USER_PERMISSIONS_TTL,
                json.dumps(permissions),
            )

        # Проверяем право
        if code in permissions.get("denied", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Право '{code}' отозвано для вашего аккаунта",
            )

        if code in permissions.get("granted", []):
            return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Недостаточно прав: требуется '{code}'",
        )

    return _check_permission


async def _load_permissions(db: AsyncSession, user: User) -> dict:
    """
    Загрузить права пользователя из БД.
    Возвращает dict с ключами 'granted' и 'denied'.
    """
    # Персональные права (override)
    user_perms_result = await db.execute(
        select(UserPermission.permission_code, UserPermission.granted)
        .where(UserPermission.user_id == user.id)
    )
    user_perms = {row.permission_code: row.granted for row in user_perms_result.all()}

    # Права роли
    role_perms_result = await db.execute(
        select(RolePermission.permission_code)
        .where(
            RolePermission.org_id == user.org_id,
            RolePermission.role == user.role,
        )
    )
    role_perms = {row[0] for row in role_perms_result.all()}

    # Объединяем: user_permissions имеют приоритет
    granted = set(role_perms)
    denied: set = set()

    for perm_code, is_granted in user_perms.items():
        if is_granted:
            granted.add(perm_code)
        else:
            granted.discard(perm_code)
            denied.add(perm_code)

    return {
        "granted": list(granted),
        "denied": list(denied),
    }
