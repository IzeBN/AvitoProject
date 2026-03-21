"""
Auth роутер: регистрация, вход, обновление токена, выход, профиль.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db, set_rls_superadmin
from app.dependencies import get_current_user
from app.models.auth import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import OrgInfo, UserProfile
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(session=db, settings=settings)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация новой организации",
    description=(
        "Создаёт новую организацию и пользователя-владельца. "
        "Возвращает пару access/refresh токенов."
    ),
)
async def register(
    data: RegisterRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    # Суперадмин обход RLS для регистрации (создаём новый тенант)
    await set_rls_superadmin(db)

    service = AuthService(session=db, settings=settings)
    result = await service.register(data)
    await db.commit()

    logger.info(
        "New user registered: %s (request_id=%s)",
        data.email,
        getattr(request.state, "request_id", None),
    )
    return result


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход в систему",
    description="Аутентификация по email и паролю. Возвращает пару токенов.",
)
async def login(
    data: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    # Для логина нужен доступ ко всем пользователям (без RLS)
    await set_rls_superadmin(db)

    service = AuthService(session=db, settings=settings)
    result = await service.login(data)
    await db.commit()

    logger.info(
        "User logged in: %s (request_id=%s)",
        data.email,
        getattr(request.state, "request_id", None),
    )
    return result


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновление токенов",
    description="Ротация refresh токена. Старый токен отзывается, выдаётся новая пара.",
)
async def refresh_tokens(
    data: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    await set_rls_superadmin(db)

    service = AuthService(session=db, settings=settings)
    result = await service.refresh(data)
    await db.commit()

    return result


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Выход из системы",
    description="Отзывает refresh токен. Всегда возвращает 204.",
)
async def logout(
    data: LogoutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await set_rls_superadmin(db)

    service = AuthService(session=db, settings=settings)
    await service.logout(data.refresh_token)
    await db.commit()


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Профиль текущего пользователя",
    description="Возвращает данные авторизованного пользователя с информацией об организации.",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserProfile:
    org = current_user.organization
    return UserProfile(
        id=current_user.id,
        org_id=current_user.org_id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        last_login_at=current_user.last_login_at,
        created_at=current_user.created_at,
        organization=OrgInfo(
            id=org.id,
            name=org.name,
            slug=org.slug,
            access_status=org.access_status,
        ) if org is not None else None,
    )
