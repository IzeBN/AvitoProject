"""
Модели чата: сообщения (партиционированы по месяцам) и метаданные.
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
from sqlalchemy.dialects.postgresql import UUID
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatMessage(Base):
    """
    Сообщение чата.
    Таблица партиционирована по RANGE(created_at) — по месяцам.
    Партиции создаются автоматически в lifespan приложения.
    """

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    chat_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # 'account' | 'candidate' | 'system'
    author_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'text' | 'image' | 'file' | 'link'
    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="text",
        server_default="text",
    )

    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    avito_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
        # Входит в PRIMARY KEY для партиционирования
    )

    # Партиционирование описывается в DDL миграции, здесь только маппинг
    __table_args__ = (
        Index("idx_chat_msgs_chat_created", "chat_id", "created_at"),
        Index("idx_chat_msgs_candidate", "candidate_id", "created_at"),
        Index(
            "idx_chat_msgs_avito_id",
            "avito_message_id",
            unique=True,
            postgresql_where="avito_message_id IS NOT NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} chat_id={self.chat_id}>"


class ChatMetadata(Base):
    """
    Агрегированные метаданные чата.
    Обновляется при каждом новом сообщении для быстрого отображения списка чатов.
    """

    __tablename__ = "chat_metadata"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    chat_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    unread_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    is_blocked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_chat_meta_org_last", "org_id", "last_message_at"),
        Index(
            "idx_chat_meta_unread",
            "org_id",
            "unread_count",
            postgresql_where="unread_count > 0",
        ),
        Index("idx_chat_meta_chatid", "chat_id"),
    )

    def __repr__(self) -> str:
        return f"<ChatMetadata candidate_id={self.candidate_id} unread={self.unread_count}>"


class FastAnswer(Base):
    """
    Быстрый ответ — заготовленный шаблон сообщения для оператора.
    Отображается в интерфейсе чата для ускорения ответов.
    """

    __tablename__ = "fast_answers"

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
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_fast_answers_org_id", "org_id"),
    )

    def __repr__(self) -> str:
        return f"<FastAnswer id={self.id} title={self.title!r}>"
