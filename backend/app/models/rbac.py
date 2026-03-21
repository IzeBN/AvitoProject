"""
Модели RBAC — права доступа, роли, отделы.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
TIMESTAMPTZ = TIMESTAMP(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Department(Base):
    """Отдел организации. Пользователь может состоять в нескольких отделах."""

    __tablename__ = "departments"

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
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        server_default=func.now(),
        nullable=False,
    )

    user_departments: Mapped[list["UserDepartment"]] = relationship(
        "UserDepartment",
        back_populates="department",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_dept_org_name"),
        Index("idx_departments_org", "org_id"),
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name}>"


class UserDepartment(Base):
    """Связь пользователя с отделом (M2M)."""

    __tablename__ = "user_departments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )

    department: Mapped["Department"] = relationship(
        "Department",
        back_populates="user_departments",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "department_id", name="uq_user_department"),
        Index("idx_user_departments_user", "user_id"),
        Index("idx_user_departments_dept", "department_id"),
    )


class Permission(Base):
    """
    Каталог всех прав доступа системы.
    Например: 'crm.candidates.view', 'mailing.send', 'admin.users.manage'.
    """

    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    # Уникальный код права: 'crm.candidates.view'
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 'crm' | 'mailing' | 'vacancies' | 'admin' | 'avito'
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<Permission code={self.code}>"


class RolePermission(Base):
    """
    Права по умолчанию для роли в рамках организации.
    Позволяет кастомизировать права ролей под конкретный тенант.
    """

    __tablename__ = "role_permissions"

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
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    permission_code: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("permissions.code"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id", "role", "permission_code",
            name="uq_role_permission",
        ),
        Index("idx_role_perms_org_role", "org_id", "role"),
    )

    def __repr__(self) -> str:
        return f"<RolePermission org={self.org_id} role={self.role} perm={self.permission_code}>"


class UserPermission(Base):
    """
    Индивидуальные права пользователя.
    Переопределяют права роли: granted=True выдаёт, False отзывает.
    """

    __tablename__ = "user_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    permission_code: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("permissions.code"),
        nullable=False,
    )
    # True = выдать право, False = явно отозвать
    granted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "permission_code", name="uq_user_permission"),
        Index("idx_user_perms_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<UserPermission user={self.user_id} perm={self.permission_code} granted={self.granted}>"
