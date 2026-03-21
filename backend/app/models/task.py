"""
Модель задач (TODO для менеджеров).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Task(Base, TimestampMixin):
    """
    Задача, привязанная к кандидату и ответственному менеджеру.
    """

    __tablename__ = "tasks"

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
    responsible_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",
        server_default="open",
    )

    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    __table_args__ = (
        Index("idx_tasks_org_responsible", "org_id", "responsible_id", "is_completed"),
        Index(
            "idx_tasks_org_deadline",
            "org_id",
            "deadline",
            postgresql_where="deadline IS NOT NULL AND is_completed = FALSE",
        ),
        Index(
            "idx_tasks_candidate",
            "candidate_id",
            postgresql_where="candidate_id IS NOT NULL",
        ),
    )

    # Relationships for eager loading
    assignee: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[responsible_id],
        lazy="raise",
    )
    candidate_rel: Mapped["Candidate | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Candidate",
        foreign_keys=[candidate_id],
        lazy="raise",
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title[:50]}>"
