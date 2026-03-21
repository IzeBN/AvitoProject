"""
Репозиторий пользователей.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.auth import RefreshToken, User, UserCredentials
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Репозиторий для работы с пользователями."""

    model = User

    async def get_by_email(self, email: str) -> User | None:
        """Найти пользователя по email (с организацией для JWT)."""
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.organization))
            .where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Найти пользователя по username."""
        result = await self._session.execute(
            select(User).where(User.username == username.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_org(self, user_id: uuid.UUID) -> User | None:
        """Загрузить пользователя с данными организации (один запрос)."""
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.organization))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_credentials(self, user_id: uuid.UUID) -> UserCredentials | None:
        """Получить учётные данные пользователя."""
        result = await self._session.execute(
            select(UserCredentials).where(UserCredentials.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        """Обновить время последнего входа."""
        result = await self._session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            self._session.add(user)
            await self._session.flush()

    async def email_exists(self, email: str) -> bool:
        """Проверить что email уже занят."""
        result = await self._session.execute(
            select(User.id).where(User.email == email.lower())
        )
        return result.scalar_one_or_none() is not None

    async def username_exists(self, username: str) -> bool:
        """Проверить что username уже занят."""
        result = await self._session.execute(
            select(User.id).where(User.username == username.lower())
        )
        return result.scalar_one_or_none() is not None


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Репозиторий refresh токенов."""

    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Найти активный refresh токен по хешу."""
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        """Отозвать refresh токен."""
        token.revoked_at = datetime.now(timezone.utc)
        self._session.add(token)
        await self._session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Отозвать все refresh токены пользователя (logout everywhere)."""
        from sqlalchemy import update

        await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self._session.flush()
