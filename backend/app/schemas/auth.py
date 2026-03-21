"""
Схемы для аутентификации и авторизации.
"""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """Запрос на личную регистрацию. Организацию назначает суперадмин."""

    email: EmailStr = Field(description="Email пользователя")
    username: str = Field(
        min_length=3,
        max_length=100,
        description="Уникальное имя пользователя (латиница, цифры, _)",
        examples=["ivan_ivanov"],
    )
    full_name: str = Field(
        min_length=2,
        max_length=255,
        description="Полное имя",
        examples=["Иван Иванов"],
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Пароль (минимум 8 символов)",
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username может содержать только латинские буквы, цифры и _")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Пароль должен содержать минимум одну заглавную букву")
        if not any(c.isdigit() for c in v):
            raise ValueError("Пароль должен содержать минимум одну цифру")
        return v


class LoginRequest(BaseModel):
    """Запрос на вход в систему."""

    email: EmailStr = Field(description="Email пользователя")
    password: str = Field(description="Пароль")


class RefreshRequest(BaseModel):
    """Запрос на обновление токенов."""

    refresh_token: str = Field(description="Refresh JWT токен")


class LogoutRequest(BaseModel):
    """Запрос на выход из системы."""

    refresh_token: str = Field(description="Refresh JWT токен для отзыва")


class TokenResponse(BaseModel):
    """Ответ с парой JWT токенов."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Время жизни access токена в секундах")
