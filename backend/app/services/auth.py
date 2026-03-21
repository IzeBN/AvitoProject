"""
AuthService — регистрация, вход, обновление и отзыв токенов.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.auth import Organization, RefreshToken, User, UserCredentials
from app.models.rbac import Permission, RolePermission
from app.repositories.organization import OrganizationRepository
from app.repositories.user import RefreshTokenRepository, UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.security.jwt import JWTService
from app.security.passwords import hash_password, verify_password

logger = logging.getLogger(__name__)

# Права по умолчанию для каждой роли при создании организации
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "owner": [
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
        "avito.accounts.manage",
        "admin.users.view",
        "admin.users.manage",
        "admin.departments.manage",
        "admin.settings.manage",
        "admin.audit.view",
    ],
    "admin": [
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
        "avito.accounts.manage",
        "admin.users.view",
        "admin.users.manage",
        "admin.departments.manage",
        "admin.audit.view",
    ],
    "manager": [
        "crm.candidates.view",
        "crm.candidates.create",
        "crm.candidates.edit",
        "mailing.view",
        "mailing.send",
        "vacancies.view",
    ],
}


def _hash_token(token: str) -> str:
    """Вычислить SHA-256 хеш токена для хранения в БД."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    """
    Сервис аутентификации.
    Управляет регистрацией, входом, ротацией токенов и выходом.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._jwt = JWTService(settings)
        self._user_repo = UserRepository(session)
        self._org_repo = OrganizationRepository(session)
        self._token_repo = RefreshTokenRepository(session)

    async def register(self, data: RegisterRequest) -> TokenResponse:
        """
        Личная регистрация пользователя без организации.

        1. Проверяет уникальность email и username
        2. Создаёт User с ролью 'manager' и org_id=NULL
        3. Создаёт UserCredentials с хешем пароля
        4. Выдаёт access + refresh токены
        Организацию назначает суперадмин через панель управления.
        """
        if await self._user_repo.email_exists(data.email.lower()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким email уже существует",
            )
        if await self._user_repo.username_exists(data.username.lower()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Имя пользователя уже занято",
            )

        user = User(
            org_id=None,
            email=data.email.lower(),
            username=data.username.lower(),
            full_name=data.full_name,
            role="manager",
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()

        credentials = UserCredentials(
            user_id=user.id,
            password_hash=hash_password(data.password),
        )
        self._session.add(credentials)
        await self._session.flush()

        return await self._issue_tokens(user)

    async def login(self, data: LoginRequest) -> TokenResponse:
        """
        Аутентифицировать пользователя по email и паролю.

        1. Находит пользователя по email
        2. Проверяет пароль
        3. Проверяет is_active
        4. Обновляет last_login_at
        5. Выдаёт токены
        """
        user = await self._user_repo.get_by_email(data.email.lower())
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )

        credentials = await self._user_repo.get_credentials(user.id)
        if credentials is None or not verify_password(data.password, credentials.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт деактивирован. Обратитесь к администратору.",
            )

        # Обновляем last_login_at
        await self._user_repo.update_last_login(user.id)

        return await self._issue_tokens(user)

    async def refresh(self, data: RefreshRequest) -> TokenResponse:
        """
        Обновить пару токенов по refresh токену.

        1. Декодирует JWT
        2. Находит токен в БД по хешу
        3. Проверяет что не отозван и не истёк
        4. Отзывает старый токен
        5. Выдаёт новую пару
        """
        from jose import JWTError

        try:
            payload = self._jwt.decode_refresh_token(data.refresh_token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Невалидный refresh токен",
            )

        token_hash = _hash_token(data.refresh_token)
        stored_token = await self._token_repo.get_by_hash(token_hash)

        if stored_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh токен не найден или уже отозван",
            )

        if stored_token.is_expired:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh токен истёк",
            )

        # Загружаем пользователя с организацией для JWT
        user = await self._user_repo.get_by_id_with_org(uuid.UUID(payload.sub))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден или деактивирован",
            )

        # Отзываем старый токен
        await self._token_repo.revoke(stored_token)

        # Выдаём новую пару
        return await self._issue_tokens(user)

    async def logout(self, refresh_token: str) -> None:
        """
        Отозвать refresh токен (выход из системы).
        Игнорирует невалидные токены — logout всегда успешен.
        """
        try:
            token_hash = _hash_token(refresh_token)
            stored_token = await self._token_repo.get_by_hash(token_hash)
            if stored_token:
                await self._token_repo.revoke(stored_token)
        except Exception:
            # Logout должен быть идемпотентным
            logger.debug("Failed to revoke token during logout (ignored)")

    async def _issue_tokens(self, user: User) -> TokenResponse:
        """Создать и сохранить новую пару access + refresh токенов."""
        access_token = self._jwt.create_access_token(
            user_id=user.id,
            org_id=user.org_id,
            role=user.role,
            org_name=user.organization.name if user.organization else None,
        )
        refresh_token_str, _jti = self._jwt.create_refresh_token(user_id=user.id)

        # Сохраняем refresh токен
        token_hash = _hash_token(refresh_token_str)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self._settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self._session.add(refresh_token_record)
        await self._session.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            expires_in=self._settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def _create_default_permissions(self, org_id: uuid.UUID) -> None:
        """
        Создать дефолтные права ролей для новой организации.
        Только для существующих в таблице permissions кодов.
        """
        from sqlalchemy import select

        # Загружаем все существующие коды прав
        result = await self._session.execute(
            select(Permission.code)
        )
        existing_codes = {row[0] for row in result.all()}

        for role, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
            for code in perm_codes:
                if code in existing_codes:
                    rp = RolePermission(
                        org_id=org_id,
                        role=role,
                        permission_code=code,
                    )
                    self._session.add(rp)

        await self._session.flush()
