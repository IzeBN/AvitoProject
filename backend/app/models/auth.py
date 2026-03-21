"""
Модели аутентификации и организаций.
Organization, User, UserCredentials, UserAuthProvider, RefreshToken.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Organization(Base, TimestampMixin):
    """
    Организация — корневой тенант системы.
    Каждый клиент CRM имеет свою организацию.
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # 'active' | 'suspended' | 'expired' | 'inactive'
    access_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )

    suspended_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    suspended_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, name="fk_org_suspended_by"),
        nullable=True,
    )
    suspend_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # NULL = бессрочная подписка
    subscription_until: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    max_users: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        server_default="50",
    )
    max_avito_accounts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        server_default="5",
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        foreign_keys="User.org_id",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "idx_orgs_status",
            "access_status",
            postgresql_where="access_status != 'inactive'",
        ),
        Index(
            "idx_orgs_subscription",
            "subscription_until",
            postgresql_where="subscription_until IS NOT NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug}>"


class User(Base, TimestampMixin):
    """
    Пользователь системы.
    Привязан к организации, имеет роль.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # 'superadmin' | 'owner' | 'admin' | 'manager'
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manager",
        server_default="manager",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    # Relationships
    organization: Mapped["Organization | None"] = relationship(
        "Organization",
        back_populates="users",
        foreign_keys=[org_id],
    )
    credentials: Mapped["UserCredentials | None"] = relationship(
        "UserCredentials",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    auth_providers: Mapped[list["UserAuthProvider"]] = relationship(
        "UserAuthProvider",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_users_org", "org_id"),
        Index("idx_users_org_role", "org_id", "role"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"


class UserCredentials(Base):
    """
    Учётные данные для локальной авторизации (email+password).
    Отделены от User для поддержки OAuth без пароля.
    """

    __tablename__ = "user_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="credentials")

    def __repr__(self) -> str:
        return f"<UserCredentials user_id={self.user_id}>"


class UserAuthProvider(Base):
    """
    OAuth провайдеры для авторизации.
    Задел для Google, GitHub, Yandex.
    """

    __tablename__ = "user_auth_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 'google' | 'github' | 'yandex'
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Зашифрованные токены OAuth
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="auth_providers")

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_auth_provider_user"),
        Index("idx_auth_providers_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<UserAuthProvider user_id={self.user_id} provider={self.provider}>"


class RefreshToken(Base):
    """
    Refresh токены для ротации JWT.
    Хранится хеш токена, не сам токен.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SHA-256 от оригинального токена
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index(
            "idx_refresh_tokens_user",
            "user_id",
            postgresql_where="revoked_at IS NULL",
        ),
        Index(
            "idx_refresh_tokens_hash",
            "token_hash",
            postgresql_where="revoked_at IS NULL",
        ),
    )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        from datetime import timezone
        return self.expires_at < datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<RefreshToken user_id={self.user_id} revoked={self.is_revoked}>"
