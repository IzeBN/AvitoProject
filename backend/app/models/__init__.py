"""
Импорт всех моделей для Alembic autogenerate.
Порядок важен: базовые сущности должны идти раньше зависимых.
"""

from app.models.base import Base, OrgMixin, SoftDeleteMixin, TimestampMixin
from app.models.auth import (
    Organization,
    RefreshToken,
    User,
    UserAuthProvider,
    UserCredentials,
)
from app.models.rbac import (
    Department,
    Permission,
    RolePermission,
    UserDepartment,
    UserPermission,
)
from app.models.avito import AvitoAccount, AvitoWebhookEndpoint
from app.models.crm import Candidate, CandidateTag, PipelineStage, Tag
from app.models.chat import ChatMessage, ChatMetadata
from app.models.mailing import MailingJob, MailingRecipient
from app.models.task import Task
from app.models.vacancy import Vacancy
from app.models.messaging import (
    AutoResponseRule,
    DefaultMessage,
    ItemMessage,
)
from app.models.chat import FastAnswer
from app.models.self_employed import SelfEmployedCheck
from app.models.audit import AuditLog
from app.models.error_log import ErrorLog

__all__ = [
    # Base
    "Base",
    "OrgMixin",
    "SoftDeleteMixin",
    "TimestampMixin",
    # Auth
    "Organization",
    "User",
    "UserCredentials",
    "UserAuthProvider",
    "RefreshToken",
    # RBAC
    "Department",
    "UserDepartment",
    "Permission",
    "RolePermission",
    "UserPermission",
    # Avito
    "AvitoAccount",
    "AvitoWebhookEndpoint",
    # CRM
    "PipelineStage",
    "Tag",
    "Candidate",
    "CandidateTag",
    # Chat
    "ChatMessage",
    "ChatMetadata",
    # Mailing
    "MailingJob",
    "MailingRecipient",
    # Task
    "Task",
    # Vacancy
    "Vacancy",
    # Messaging
    "DefaultMessage",
    "ItemMessage",
    "AutoResponseRule",
    "FastAnswer",
    # Self employed
    "SelfEmployedCheck",
    # Audit & Errors
    "AuditLog",
    "ErrorLog",
]
