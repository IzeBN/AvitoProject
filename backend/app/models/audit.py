"""
Модель журнала аудита (партиционирована по месяцам).
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, func
from sqlalchemy import TIMESTAMP
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """
    Запись аудита действия пользователя.
    Таблица партиционирована RANGE(created_at) по месяцам.
    Содержит как машиночитаемые поля, так и human_readable текст.
    """

    __tablename__ = "audit_log"

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
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    # Снапшот данных пользователя на момент действия
    user_full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Тип действия: 'candidate.create', 'user.login', 'mailing.start', etc.
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # Основная сущность
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entity_display: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Связанная сущность (например, вакансия для кандидата)
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    related_entity_display: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Детали изменений в JSON
    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Человекочитаемое описание: "Иван Иванов переместил кандидата Пётр в этап 'Интервью'"
    human_readable: Mapped[str] = mapped_column(Text, nullable=False)

    # HTTP контекст
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_audit_user_created", "org_id", "user_id", "created_at"),
        Index("idx_audit_entity", "org_id", "entity_type", "entity_id", "created_at"),
        Index("idx_audit_org_created", "org_id", "created_at"),
        Index("idx_audit_action", "org_id", "action", "created_at"),
        Index("idx_audit_global", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog action={self.action} org={self.org_id}>"
