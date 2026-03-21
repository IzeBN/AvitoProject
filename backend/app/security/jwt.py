"""
JWT токены: создание access/refresh и декодирование.

Access token: HS256, TTL = ACCESS_TOKEN_EXPIRE_MINUTES
    payload: { sub, org_id, role, type: 'access', exp, iat }

Refresh token: HS256, TTL = REFRESH_TOKEN_EXPIRE_DAYS
    payload: { sub, type: 'refresh', jti, exp, iat }
    jti используется как идентификатор для отзыва.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import Settings


@dataclass(frozen=True)
class TokenPayload:
    """Декодированный payload JWT токена."""

    sub: str          # user_id
    token_type: str   # 'access' | 'refresh'
    exp: datetime
    iat: datetime
    # Только для access токенов
    org_id: str | None = None
    role: str | None = None
    # Только для refresh токенов
    jti: str | None = None


class JWTService:
    """Сервис работы с JWT токенами."""

    ALGORITHM = "HS256"

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.SECRET_KEY
        self._access_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self._refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS

    def create_access_token(
        self,
        user_id: str | uuid.UUID,
        org_id: str | uuid.UUID | None,
        role: str,
        org_name: str | None = None,
    ) -> str:
        """
        Создать access JWT токен.

        Args:
            user_id: идентификатор пользователя
            org_id: идентификатор организации
            role: роль пользователя

        Returns:
            JWT строка
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self._access_ttl)

        payload = {
            "sub": str(user_id),
            "org_id": str(org_id) if org_id is not None else None,
            "role": role,
            "org_name": org_name,
            "type": "access",
            "iat": now,
            "exp": expire,
        }
        return jwt.encode(payload, self._secret, algorithm=self.ALGORITHM)

    def create_refresh_token(self, user_id: str | uuid.UUID) -> tuple[str, str]:
        """
        Создать refresh JWT токен.

        Args:
            user_id: идентификатор пользователя

        Returns:
            Кортеж (jwt_строка, jti) — jti нужен для отзыва токена
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self._refresh_ttl)
        jti = str(uuid.uuid4())

        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "jti": jti,
            "iat": now,
            "exp": expire,
        }
        token = jwt.encode(payload, self._secret, algorithm=self.ALGORITHM)
        return token, jti

    def decode_token(self, token: str) -> TokenPayload:
        """
        Декодировать и валидировать JWT токен.

        Args:
            token: JWT строка

        Returns:
            TokenPayload с данными из токена

        Raises:
            JWTError: если токен невалидный, истёк или подпись неверная
        """
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self.ALGORITHM])
        except JWTError as exc:
            raise exc

        return TokenPayload(
            sub=payload["sub"],
            token_type=payload["type"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            org_id=payload.get("org_id"),
            role=payload.get("role"),
            jti=payload.get("jti"),
        )

    def decode_access_token(self, token: str) -> TokenPayload:
        """Декодировать access токен с проверкой типа."""
        payload = self.decode_token(token)
        if payload.token_type != "access":
            raise JWTError("Invalid token type: expected 'access'")
        return payload

    def decode_refresh_token(self, token: str) -> TokenPayload:
        """Декодировать refresh токен с проверкой типа."""
        payload = self.decode_token(token)
        if payload.token_type != "refresh":
            raise JWTError("Invalid token type: expected 'refresh'")
        return payload
