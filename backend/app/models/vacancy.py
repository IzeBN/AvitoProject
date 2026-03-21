"""
Модель вакансий (объявлений Avito).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Vacancy(Base, TimestampMixin):
    """
    Вакансия (объявление Avito), синхронизированная из API.
    """

    __tablename__ = "vacancies"

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
        ForeignKey("avito_accounts.id"),
        nullable=False,
    )
    avito_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 'active' | 'closed' | 'archived'
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )

    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "avito_item_id", name="uq_vacancy_org_item"),
        Index("idx_vacancies_org_account", "org_id", "avito_account_id"),
        Index("idx_vacancies_org_status", "org_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Vacancy id={self.id} title={self.title}>"
