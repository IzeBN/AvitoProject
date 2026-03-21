"""
Модели рассылок: задания и получатели.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class MailingJob(Base, TimestampMixin):
    """
    Задание рассылки.
    Отправка сообщений группе кандидатов с контролем скорости.
    """

    __tablename__ = "mailing_jobs"

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
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # 'pending' | 'running' | 'paused' | 'resuming' | 'stopping' | 'done' | 'failed' | 'cancelled'
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Критерии выборки кандидатов
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    scheduled_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    rate_limit_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1000,
        server_default="1000",
    )

    # Статистика
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    resumed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)

    arq_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    recipients: Mapped[list["MailingRecipient"]] = relationship(
        "MailingRecipient",
        back_populates="mailing_job",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_mailing_jobs_org_status", "org_id", "status"),
        Index("idx_mailing_jobs_org_created", "org_id", "created_at"),
        Index(
            "idx_mailing_jobs_scheduled",
            "scheduled_at",
            postgresql_where="status = 'pending' AND scheduled_at IS NOT NULL",
        ),
        Index("idx_mailing_jobs_status_global", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<MailingJob id={self.id} status={self.status}>"


class MailingRecipient(Base):
    """Получатель рассылки с отслеживанием статуса отправки."""

    __tablename__ = "mailing_recipients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    mailing_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mailing_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )

    # 'pending' | 'sent' | 'failed' | 'skipped'
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    mailing_job: Mapped["MailingJob"] = relationship(
        "MailingJob",
        back_populates="recipients",
    )

    __table_args__ = (
        UniqueConstraint(
            "mailing_job_id",
            "candidate_id",
            name="uq_mailing_recipient",
        ),
        Index("idx_mailing_recip_job_status", "mailing_job_id", "status"),
        Index(
            "idx_mailing_recip_job_pending",
            "mailing_job_id",
            postgresql_where="status = 'pending'",
        ),
    )

    def __repr__(self) -> str:
        return f"<MailingRecipient job={self.mailing_job_id} candidate={self.candidate_id}>"
