"""
CRM модели: этапы воронки, теги, кандидаты.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
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

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class PipelineStage(Base):
    """Этап воронки найма. Порядок задаётся sort_order."""

    __tablename__ = "pipeline_stages"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
    )
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # HEX цвет
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_stage_org_name"),
        Index("idx_stages_org_order", "org_id", "sort_order"),
    )

    def __repr__(self) -> str:
        return f"<PipelineStage name={self.name} order={self.sort_order}>"


class Tag(Base):
    """Тег для классификации кандидатов."""

    __tablename__ = "tags"

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
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_tag_org_name"),
        Index("idx_tags_org", "org_id"),
    )

    def __repr__(self) -> str:
        return f"<Tag name={self.name}>"


class Candidate(Base, TimestampMixin, SoftDeleteMixin):
    """
    Кандидат CRM. Центральная сущность системы.
    Телефон хранится зашифрованным, для поиска используется HMAC хеш.
    """

    __tablename__ = "candidates"

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
    avito_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("avito_accounts.id"),
        nullable=True,
    )
    chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avito_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    avito_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Телефон зашифрован AES-256-GCM
    phone_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # HMAC-SHA256(phone, SEARCH_HASH_KEY) — детерминированный поиск
    phone_search_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_stages.id"),
        nullable=True,
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id"),
        nullable=True,
    )
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vacancy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    has_new_message: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    stage: Mapped["PipelineStage | None"] = relationship(
        "PipelineStage",
        foreign_keys=[stage_id],
        lazy="raise",
    )
    department: Mapped["Department | None"] = relationship(
        "Department",
        foreign_keys=[department_id],
        lazy="raise",
    )
    responsible: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[responsible_id],
        lazy="raise",
    )
    tags: Mapped[list["CandidateTag"]] = relationship(
        "CandidateTag",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Основные индексы с фильтром на активных кандидатов
        Index(
            "idx_cand_org_created",
            "org_id",
            "created_at",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_cand_org_stage",
            "org_id",
            "stage_id",
            "created_at",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_cand_org_responsible",
            "org_id",
            "responsible_id",
            "created_at",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_cand_org_department",
            "org_id",
            "department_id",
            "created_at",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_cand_org_account",
            "org_id",
            "avito_account_id",
            "created_at",
            postgresql_where="deleted_at IS NULL",
        ),
        Index(
            "idx_cand_org_new_msg",
            "org_id",
            "has_new_message",
            "created_at",
            postgresql_where="deleted_at IS NULL AND has_new_message = TRUE",
        ),
        Index(
            "idx_cand_org_duedate",
            "org_id",
            "due_date",
            postgresql_where="deleted_at IS NULL AND due_date IS NOT NULL",
        ),
        Index(
            "idx_cand_phone_hash",
            "org_id",
            "phone_search_hash",
            postgresql_where="deleted_at IS NULL",
        ),
        UniqueConstraint(
            "org_id",
            "chat_id",
            name="uq_cand_org_chatid",
            # postgresql_where="deleted_at IS NULL AND chat_id IS NOT NULL",
        ),
        Index(
            "idx_cand_stage_responsible",
            "org_id",
            "stage_id",
            "responsible_id",
            "created_at",
            postgresql_where="deleted_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        return f"<Candidate id={self.id} name={self.name}>"


class CandidateTag(Base):
    """Связь кандидата с тегом (M2M)."""

    __tablename__ = "candidate_tags"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    candidate: Mapped["Candidate"] = relationship(
        "Candidate",
        back_populates="tags",
    )

    __table_args__ = (
        Index("idx_candidate_tags_tag", "tag_id"),
        Index("idx_candidate_tags_org", "org_id"),
    )
