"""
Модели Avito аккаунтов и вебхук эндпоинтов.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AvitoAccount(Base, TimestampMixin):
    """
    Avito аккаунт организации.
    client_id и client_secret хранятся в зашифрованном виде (AES-256-GCM).
    """

    __tablename__ = "avito_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avito_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Зашифрованные OAuth credentials Avito
    client_id_enc: Mapped[str] = mapped_column(Text, nullable=False)
    client_secret_enc: Mapped[str] = mapped_column(Text, nullable=False)

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    webhook_endpoints: Mapped[list["AvitoWebhookEndpoint"]] = relationship(
        "AvitoWebhookEndpoint",
        back_populates="avito_account",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("org_id", "avito_user_id", name="uq_avito_account_org_user"),
        Index("idx_avito_accounts_org", "org_id"),
        Index(
            "idx_avito_accounts_org_active",
            "org_id",
            "is_active",
            postgresql_where="is_active = TRUE",
        ),
    )

    def __repr__(self) -> str:
        return f"<AvitoAccount id={self.id} name={self.account_name}>"


class AvitoWebhookEndpoint(Base):
    """
    Вебхук эндпоинт для получения событий от Avito API.
    Каждый аккаунт + тип события = уникальный endpoint с токеном.
    """

    __tablename__ = "avito_webhook_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    avito_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("avito_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 'new_response' | 'new_message' | 'message_read' | 'chat_blocked'
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Уникальный токен для идентификации вебхука
    account_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    last_received_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    avito_account: Mapped["AvitoAccount"] = relationship(
        "AvitoAccount",
        back_populates="webhook_endpoints",
    )

    __table_args__ = (
        UniqueConstraint(
            "avito_account_id",
            "event_type",
            name="uq_webhook_account_event",
        ),
        Index(
            "idx_webhook_token",
            "account_token",
            postgresql_where="is_active = TRUE",
        ),
    )

    def __repr__(self) -> str:
        return f"<AvitoWebhookEndpoint account={self.avito_account_id} event={self.event_type}>"
