"""
Модель журнала ошибок (партиционирована по месяцам).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ErrorLog(Base):
    """
    Запись об ошибке в системе.
    Партиционирована RANGE(created_at) по месяцам.
    Используется для мониторинга и дебаггинга.
    """

    __tablename__ = "error_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # 'api' | 'worker' | 'webhook' | 'scheduler'
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # Модуль/класс: 'app.services.auth'
    layer: Mapped[str] = mapped_column(String(100), nullable=False)
    # Функция/метод: 'AuthService.login'
    handler: Mapped[str] = mapped_column(String(255), nullable=False)

    # HTTP контекст
    request_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Тип и сообщение ошибки
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Контекст воркера
    job_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Статус разрешения проблемы
    resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_error_log_org_created", "org_id", "created_at"),
        Index("idx_error_log_global_created", "created_at"),
        Index("idx_error_log_source", "source", "created_at"),
        Index(
            "idx_error_log_unresolved",
            "resolved",
            "created_at",
            postgresql_where="resolved = FALSE",
        ),
    )

    def __repr__(self) -> str:
        return f"<ErrorLog type={self.error_type} source={self.source}>"
