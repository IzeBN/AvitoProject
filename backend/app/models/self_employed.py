"""
Модель проверки самозанятости.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy import TIMESTAMP
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SelfEmployedCheck(Base):
    """
    Запись проверки статуса самозанятого по ИНН.
    """

    __tablename__ = "self_employed_checks"

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
    inn: Mapped[str] = mapped_column(String(12), nullable=False)

    # 'active' | 'inactive' | 'unknown'
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    checked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("idx_self_emp_org_inn", "org_id", "inn"),
        Index("idx_self_emp_org_date", "org_id", "checked_at"),
    )

    def __repr__(self) -> str:
        return f"<SelfEmployedCheck inn={self.inn} status={self.status}>"
