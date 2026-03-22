"""
Модели шаблонов сообщений: дефолтные, по объявлению, авто-ответы, быстрые ответы.
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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DefaultMessage(Base, TimestampMixin):
    """
    Дефолтное сообщение для Avito аккаунта.
    Одно сообщение на один аккаунт.
    """

    __tablename__ = "default_messages"

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
        unique=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<DefaultMessage account={self.avito_account_id}>"


class ItemMessage(Base):
    """
    Сообщение для конкретного объявления Avito.
    Приоритетнее DefaultMessage.
    """

    __tablename__ = "item_messages"

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
    avito_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "avito_account_id",
            "avito_item_id",
            name="uq_item_message_account_item",
        ),
        Index("idx_item_msgs_org", "org_id"),
        Index(
            "idx_item_msgs_item",
            "avito_account_id",
            "avito_item_id",
            postgresql_where="is_active = TRUE",
        ),
    )

    def __repr__(self) -> str:
        return f"<ItemMessage account={self.avito_account_id} item={self.avito_item_id}>"


class AutoResponseRule(Base):
    """
    Правило авто-ответа на отклики/сообщения.
    avito_item_id = NULL означает правило для всех объявлений аккаунта.
    """

    __tablename__ = "auto_response_rules"

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
    # NULL = для всех объявлений аккаунта; список ID объявлений
    avito_item_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    # Кастомный текст автоответа (если None — используется DefaultMessage)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="on_response",
        server_default="on_response",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "idx_auto_rules_account",
            "org_id",
            "avito_account_id",
            "is_active",
            postgresql_where="is_active = TRUE",
        ),
    )

    def __repr__(self) -> str:
        return f"<AutoResponseRule account={self.avito_account_id} type={self.auto_type}>"


# FastAnswer model is defined in app.models.chat
