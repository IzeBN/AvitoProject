"""
Базовые классы и миксины для SQLAlchemy моделей.
"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID

TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class TimestampMixin:
    """Миксин для автоматических временных меток создания и обновления."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Миксин для мягкого удаления записей."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMPTZ,
        nullable=True,
        default=None,
    )


class OrgMixin:
    """
    Миксин для привязки записи к организации.
    Используется совместно с RLS политиками PostgreSQL.
    """

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
