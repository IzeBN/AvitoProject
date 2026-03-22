"""Initial schema — все таблицы, индексы, RLS политики, партиции, permissions

Revision ID: 0001
Revises:
Create Date: 2026-03-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Расширения PostgreSQL
    # ------------------------------------------------------------------
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ------------------------------------------------------------------
    # organizations
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("access_status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("suspended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("suspended_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("suspend_reason", sa.Text, nullable=True),
        sa.Column("subscription_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("max_users", sa.Integer, nullable=False, server_default="50"),
        sa.Column("max_avito_accounts", sa.Integer, nullable=False, server_default="5"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_orgs_status", "organizations", ["access_status"],
                    postgresql_where=sa.text("access_status != 'inactive'"))
    op.create_index("idx_orgs_subscription", "organizations", ["subscription_until"],
                    postgresql_where=sa.text("subscription_until IS NOT NULL"))

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="manager"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_users_org", "users", ["org_id"])
    op.create_index("idx_users_org_role", "users", ["org_id", "role"])

    # FK suspended_by → users (добавляем после создания users)
    op.create_foreign_key(
        "fk_org_suspended_by",
        "organizations", "users",
        ["suspended_by"], ["id"],
        use_alter=True,
    )

    # ------------------------------------------------------------------
    # user_credentials
    # ------------------------------------------------------------------
    op.create_table(
        "user_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # user_auth_providers
    # ------------------------------------------------------------------
    op.create_table(
        "user_auth_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("access_token_enc", sa.Text, nullable=True),
        sa.Column("refresh_token_enc", sa.Text, nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_auth_provider_user"),
    )
    op.create_index("idx_auth_providers_user", "user_auth_providers", ["user_id"])

    # ------------------------------------------------------------------
    # refresh_tokens
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("idx_refresh_tokens_user", "refresh_tokens", ["user_id"],
                    postgresql_where=sa.text("revoked_at IS NULL"))
    op.create_index("idx_refresh_tokens_hash", "refresh_tokens", ["token_hash"],
                    postgresql_where=sa.text("revoked_at IS NULL"))

    # ------------------------------------------------------------------
    # permissions
    # ------------------------------------------------------------------
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
    )

    # ------------------------------------------------------------------
    # departments
    # ------------------------------------------------------------------
    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "name", name="uq_dept_org_name"),
    )
    op.create_index("idx_departments_org", "departments", ["org_id"])

    # ------------------------------------------------------------------
    # user_departments
    # ------------------------------------------------------------------
    op.create_table(
        "user_departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.UniqueConstraint("user_id", "department_id", name="uq_user_department"),
    )
    op.create_index("idx_user_departments_user", "user_departments", ["user_id"])
    op.create_index("idx_user_departments_dept", "user_departments", ["department_id"])

    # ------------------------------------------------------------------
    # role_permissions
    # ------------------------------------------------------------------
    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("permission_code", sa.String(100), sa.ForeignKey("permissions.code"), nullable=False),
        sa.UniqueConstraint("org_id", "role", "permission_code", name="uq_role_permission"),
    )
    op.create_index("idx_role_perms_org_role", "role_permissions", ["org_id", "role"])

    # ------------------------------------------------------------------
    # user_permissions
    # ------------------------------------------------------------------
    op.create_table(
        "user_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("permission_code", sa.String(100), sa.ForeignKey("permissions.code"), nullable=False),
        sa.Column("granted", sa.Boolean, nullable=False, server_default="true"),
        sa.UniqueConstraint("user_id", "permission_code", name="uq_user_permission"),
    )
    op.create_index("idx_user_perms_user", "user_permissions", ["user_id"])

    # ------------------------------------------------------------------
    # avito_accounts
    # ------------------------------------------------------------------
    op.create_table(
        "avito_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("avito_user_id", sa.BigInteger, nullable=False),
        sa.Column("client_id_enc", sa.Text, nullable=False),
        sa.Column("client_secret_enc", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "avito_user_id", name="uq_avito_account_org_user"),
    )
    op.create_index("idx_avito_accounts_org", "avito_accounts", ["org_id"])
    op.create_index("idx_avito_accounts_org_active", "avito_accounts", ["org_id", "is_active"],
                    postgresql_where=sa.text("is_active = TRUE"))

    # ------------------------------------------------------------------
    # avito_webhook_endpoints
    # ------------------------------------------------------------------
    op.create_table(
        "avito_webhook_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avito_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("avito_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("account_token", sa.String(64), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_received_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("avito_account_id", "event_type", name="uq_webhook_account_event"),
    )
    op.create_index("idx_webhook_token", "avito_webhook_endpoints", ["account_token"],
                    postgresql_where=sa.text("is_active = TRUE"))

    # ------------------------------------------------------------------
    # pipeline_stages
    # ------------------------------------------------------------------
    op.create_table(
        "pipeline_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "name", name="uq_stage_org_name"),
    )
    op.create_index("idx_stages_org_order", "pipeline_stages", ["org_id", "sort_order"])

    # ------------------------------------------------------------------
    # tags
    # ------------------------------------------------------------------
    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "name", name="uq_tag_org_name"),
    )
    op.create_index("idx_tags_org", "tags", ["org_id"])

    # ------------------------------------------------------------------
    # candidates
    # ------------------------------------------------------------------
    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avito_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("avito_accounts.id"), nullable=True),
        sa.Column("chat_id", sa.String(255), nullable=True),
        sa.Column("avito_user_id", sa.BigInteger, nullable=True),
        sa.Column("avito_item_id", sa.BigInteger, nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("phone_enc", sa.Text, nullable=True),
        sa.Column("phone_search_hash", sa.String(64), nullable=True),
        sa.Column("stage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pipeline_stages.id"), nullable=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("responsible_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("vacancy", sa.String(500), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("has_new_message", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    # Индексы кандидатов
    op.create_index("idx_cand_org_created", "candidates", ["org_id", "created_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_cand_org_stage", "candidates", ["org_id", "stage_id", "created_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_cand_org_responsible", "candidates", ["org_id", "responsible_id", "created_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_cand_org_department", "candidates", ["org_id", "department_id", "created_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_cand_org_account", "candidates", ["org_id", "avito_account_id", "created_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_cand_org_new_msg", "candidates", ["org_id", "has_new_message", "created_at"],
                    postgresql_where=sa.text("deleted_at IS NULL AND has_new_message = TRUE"))
    op.create_index("idx_cand_org_duedate", "candidates", ["org_id", "due_date"],
                    postgresql_where=sa.text("deleted_at IS NULL AND due_date IS NOT NULL"))
    op.create_index("idx_cand_phone_hash", "candidates", ["org_id", "phone_search_hash"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("idx_cand_chatid", "candidates", ["org_id", "chat_id"],
                    unique=True,
                    postgresql_where=sa.text("deleted_at IS NULL AND chat_id IS NOT NULL"))
    op.create_index("idx_cand_stage_responsible", "candidates", ["org_id", "stage_id", "responsible_id", "created_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    # GIN индекс для поиска по имени через pg_trgm
    op.execute(
        "CREATE INDEX idx_cand_name_trgm ON candidates USING gin (name gin_trgm_ops) "
        "WHERE deleted_at IS NULL"
    )

    # ------------------------------------------------------------------
    # candidate_tags
    # ------------------------------------------------------------------
    op.create_table(
        "candidate_tags",
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_candidate_tags_tag", "candidate_tags", ["tag_id"])
    op.create_index("idx_candidate_tags_org", "candidate_tags", ["org_id"])

    # ------------------------------------------------------------------
    # chat_messages (партиционированная)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE chat_messages (
            id UUID DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id),
            candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
            chat_id VARCHAR(255) NOT NULL,
            author_type VARCHAR(20) NOT NULL,
            message_type VARCHAR(20) NOT NULL DEFAULT 'text',
            content TEXT,
            avito_message_id VARCHAR(255),
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)
    op.create_index("idx_chat_msgs_chat_created", "chat_messages", ["chat_id", "created_at"])
    op.create_index("idx_chat_msgs_candidate", "chat_messages", ["candidate_id", "created_at"])
    op.create_index("idx_chat_msgs_avito_id", "chat_messages", ["avito_message_id"],
                    unique=True, postgresql_where=sa.text("avito_message_id IS NOT NULL"))

    # ------------------------------------------------------------------
    # chat_metadata
    # ------------------------------------------------------------------
    op.create_table(
        "chat_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("chat_id", sa.String(255), nullable=False, unique=True),
        sa.Column("unread_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_blocked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_message", sa.Text, nullable=True),
        sa.Column("last_message_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_chat_meta_org_last", "chat_metadata", ["org_id", "last_message_at"])
    op.create_index("idx_chat_meta_unread", "chat_metadata", ["org_id", "unread_count"],
                    postgresql_where=sa.text("unread_count > 0"))
    op.create_index("idx_chat_meta_chatid", "chat_metadata", ["chat_id"])

    # ------------------------------------------------------------------
    # mailing_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "mailing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("file_url", sa.Text, nullable=True),
        sa.Column("criteria", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rate_limit_ms", sa.Integer, nullable=False, server_default="1000"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("paused_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resumed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("arq_job_id", sa.String(255), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_mailing_jobs_org_status", "mailing_jobs", ["org_id", "status"])
    op.create_index("idx_mailing_jobs_org_created", "mailing_jobs", ["org_id", "created_at"])
    op.create_index("idx_mailing_jobs_scheduled", "mailing_jobs", ["scheduled_at"],
                    postgresql_where=sa.text("status = 'pending' AND scheduled_at IS NOT NULL"))
    op.create_index("idx_mailing_jobs_status_global", "mailing_jobs", ["status", "created_at"])

    # ------------------------------------------------------------------
    # mailing_recipients
    # ------------------------------------------------------------------
    op.create_table(
        "mailing_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("mailing_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mailing_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.UniqueConstraint("mailing_job_id", "candidate_id", name="uq_mailing_recipient"),
    )
    op.create_index("idx_mailing_recip_job_status", "mailing_recipients", ["mailing_job_id", "status"])
    op.create_index("idx_mailing_recip_job_pending", "mailing_recipients", ["mailing_job_id"],
                    postgresql_where=sa.text("status = 'pending'"))

    # ------------------------------------------------------------------
    # tasks
    # ------------------------------------------------------------------
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("deadline", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_org_id", "tasks", ["org_id"])
    op.create_index("ix_tasks_assigned_to", "tasks", ["assigned_to"])
    op.create_index("ix_tasks_deadline", "tasks", ["deadline"],
                    postgresql_where=sa.text("deadline IS NOT NULL"))
    op.create_index("ix_tasks_org_status", "tasks", ["org_id", "status"])

    # ------------------------------------------------------------------
    # vacancies
    # ------------------------------------------------------------------
    op.create_table(
        "vacancies",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avito_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("avito_accounts.id"), nullable=False),
        sa.Column("avito_item_id", sa.BigInteger, nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
        sa.Column("synced_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("org_id", "avito_item_id", name="uq_vacancy_org_item"),
    )
    op.create_index("idx_vacancies_org_account", "vacancies", ["org_id", "avito_account_id"])
    op.create_index("idx_vacancies_org_status", "vacancies", ["org_id", "status"])

    # ------------------------------------------------------------------
    # default_messages
    # ------------------------------------------------------------------
    op.create_table(
        "default_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avito_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("avito_accounts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # item_messages
    # ------------------------------------------------------------------
    op.create_table(
        "item_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avito_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("avito_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avito_item_id", sa.BigInteger, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("avito_account_id", "avito_item_id", name="uq_item_message_account_item"),
    )
    op.create_index("idx_item_msgs_org", "item_messages", ["org_id"])
    op.create_index("idx_item_msgs_item", "item_messages", ["avito_account_id", "avito_item_id"],
                    postgresql_where=sa.text("is_active = TRUE"))

    # ------------------------------------------------------------------
    # auto_response_rules
    # ------------------------------------------------------------------
    op.create_table(
        "auto_response_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avito_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("avito_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avito_item_id", sa.BigInteger, nullable=True),
        sa.Column("auto_type", sa.String(50), nullable=False, server_default="on_response"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_auto_rules_account", "auto_response_rules", ["org_id", "avito_account_id", "is_active"],
                    postgresql_where=sa.text("is_active = TRUE"))

    # ------------------------------------------------------------------
    # fast_answers
    # ------------------------------------------------------------------
    op.create_table(
        "fast_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_fast_answers_org_id", "fast_answers", ["org_id"])
    op.create_index("ix_fast_answers_org_sort", "fast_answers", ["org_id", "sort_order"])

    # ------------------------------------------------------------------
    # self_employed_checks
    # ------------------------------------------------------------------
    op.create_table(
        "self_employed_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inn", sa.String(12), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("checked_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("checked_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("raw_response", postgresql.JSONB, nullable=True),
    )
    op.create_index("idx_self_emp_org_inn", "self_employed_checks", ["org_id", "inn"])
    op.create_index("idx_self_emp_org_date", "self_employed_checks", ["org_id", "checked_at"])

    # ------------------------------------------------------------------
    # audit_log (партиционированная)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE audit_log (
            id UUID DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id),
            user_id UUID REFERENCES users(id),
            user_full_name VARCHAR(255),
            user_role VARCHAR(20),
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            entity_id UUID,
            entity_display VARCHAR(500),
            related_entity_type VARCHAR(50),
            related_entity_id UUID,
            related_entity_display VARCHAR(500),
            details JSONB NOT NULL DEFAULT '{}',
            human_readable TEXT NOT NULL,
            ip_address INET,
            user_agent VARCHAR(500),
            request_id VARCHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)
    op.create_index("idx_audit_user_created", "audit_log", ["org_id", "user_id", "created_at"])
    op.create_index("idx_audit_entity", "audit_log", ["org_id", "entity_type", "entity_id", "created_at"])
    op.create_index("idx_audit_org_created", "audit_log", ["org_id", "created_at"])
    op.create_index("idx_audit_action", "audit_log", ["org_id", "action", "created_at"])
    op.create_index("idx_audit_global", "audit_log", ["created_at"])

    # ------------------------------------------------------------------
    # error_log (партиционированная)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE error_log (
            id UUID DEFAULT gen_random_uuid(),
            org_id UUID REFERENCES organizations(id),
            user_id UUID REFERENCES users(id),
            source VARCHAR(50) NOT NULL,
            layer VARCHAR(100) NOT NULL,
            handler VARCHAR(255) NOT NULL,
            request_method VARCHAR(10),
            request_path VARCHAR(500),
            request_id VARCHAR(64),
            error_type VARCHAR(100) NOT NULL,
            error_message TEXT NOT NULL,
            stack_trace TEXT,
            job_type VARCHAR(50),
            job_id UUID,
            status_code INTEGER,
            resolved BOOLEAN NOT NULL DEFAULT FALSE,
            resolved_by UUID REFERENCES users(id),
            resolved_at TIMESTAMPTZ,
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
    """)
    op.create_index("idx_error_log_org_created", "error_log", ["org_id", "created_at"])
    op.create_index("idx_error_log_global_created", "error_log", ["created_at"])
    op.create_index("idx_error_log_source", "error_log", ["source", "created_at"])
    op.create_index("idx_error_log_unresolved", "error_log", ["resolved", "created_at"],
                    postgresql_where=sa.text("resolved = FALSE"))

    # ------------------------------------------------------------------
    # Партиции для текущего и следующего месяца
    # ------------------------------------------------------------------
    import datetime
    today = datetime.date.today()

    for month_offset in range(2):
        year = today.year
        month = today.month + month_offset
        if month > 12:
            month -= 12
            year += 1
        start = datetime.date(year, month, 1)
        if month == 12:
            end = datetime.date(year + 1, 1, 1)
        else:
            end = datetime.date(year, month + 1, 1)
        suffix = f"{year}_{month:02d}"

        for table in ("chat_messages", "audit_log", "error_log"):
            op.execute(
                f"CREATE TABLE IF NOT EXISTS {table}_{suffix} "
                f"PARTITION OF {table} "
                f"FOR VALUES FROM ('{start}') TO ('{end}')"
            )

    # ------------------------------------------------------------------
    # Row Level Security
    # ------------------------------------------------------------------
    rls_tables = [
        "organizations", "users", "user_credentials", "user_auth_providers",
        "refresh_tokens", "departments", "user_departments", "role_permissions",
        "user_permissions", "avito_accounts", "avito_webhook_endpoints",
        "pipeline_stages", "tags", "candidates", "candidate_tags",
        "chat_messages", "chat_metadata", "mailing_jobs", "mailing_recipients",
        "tasks", "vacancies", "default_messages", "item_messages",
        "auto_response_rules", "fast_answers", "self_employed_checks",
        "audit_log", "error_log",
    ]

    for table in rls_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # Политики RLS:
    # 1. Суперадмин видит всё
    # 2. Обычный пользователь видит только свою организацию

    # organizations — суперадмин видит все, остальные только свою
    op.execute("""
        CREATE POLICY org_superadmin ON organizations
            USING (current_setting('app.is_superadmin', true) = 'true')
    """)
    op.execute("""
        CREATE POLICY org_tenant ON organizations
            USING (id::text = current_setting('app.current_org_id', true))
    """)

    # Для всех остальных таблиц с org_id
    tenant_tables = [
        "users", "departments", "user_departments",
        "role_permissions", "user_permissions", "avito_accounts",
        "avito_webhook_endpoints", "pipeline_stages", "tags",
        "candidates", "candidate_tags", "chat_messages", "chat_metadata",
        "mailing_jobs", "mailing_recipients", "tasks", "vacancies",
        "default_messages", "item_messages", "auto_response_rules",
        "fast_answers", "self_employed_checks", "audit_log", "error_log",
    ]

    for table in tenant_tables:
        # Суперадмин политика
        op.execute(f"""
            CREATE POLICY {table}_superadmin ON {table}
                USING (current_setting('app.is_superadmin', true) = 'true')
        """)
        # Тенант политика (для таблиц с org_id)
        if table not in ("user_credentials", "user_auth_providers", "refresh_tokens"):
            op.execute(f"""
                CREATE POLICY {table}_tenant ON {table}
                    USING (org_id::text = current_setting('app.current_org_id', true))
            """)

    # user_credentials, user_auth_providers, refresh_tokens — через JOIN с users
    for table in ("user_credentials", "user_auth_providers", "refresh_tokens"):
        op.execute(f"""
            CREATE POLICY {table}_superadmin ON {table}
                USING (current_setting('app.is_superadmin', true) = 'true')
        """)
        op.execute(f"""
            CREATE POLICY {table}_tenant ON {table}
                USING (
                    user_id IN (
                        SELECT id FROM users
                        WHERE org_id::text = current_setting('app.current_org_id', true)
                    )
                )
        """)

    # ------------------------------------------------------------------
    # Начальный набор permissions
    # ------------------------------------------------------------------
    permissions = [
        # CRM
        ("crm.candidates.view", "Просмотр кандидатов", "crm"),
        ("crm.candidates.create", "Создание кандидатов", "crm"),
        ("crm.candidates.edit", "Редактирование кандидатов", "crm"),
        ("crm.candidates.delete", "Удаление кандидатов", "crm"),
        ("crm.stages.manage", "Управление этапами воронки", "crm"),
        ("crm.tags.manage", "Управление тегами", "crm"),
        # Рассылки
        ("mailing.view", "Просмотр рассылок", "mailing"),
        ("mailing.send", "Создание и отправка рассылок", "mailing"),
        ("mailing.manage", "Управление рассылками (пауза, остановка)", "mailing"),
        # Вакансии
        ("vacancies.view", "Просмотр вакансий", "vacancies"),
        ("vacancies.manage", "Управление вакансиями", "vacancies"),
        # Avito
        ("avito.accounts.view", "Просмотр Avito аккаунтов", "avito"),
        ("avito.accounts.manage", "Управление Avito аккаунтами", "avito"),
        ("avito.webhooks.manage", "Управление вебхуками Avito", "avito"),
        # Администрирование
        ("admin.users.view", "Просмотр пользователей организации", "admin"),
        ("admin.users.manage", "Управление пользователями", "admin"),
        ("admin.departments.manage", "Управление отделами", "admin"),
        ("admin.settings.manage", "Настройки организации", "admin"),
        ("admin.audit.view", "Просмотр журнала аудита", "admin"),
        ("admin.errors.view", "Просмотр журнала ошибок", "admin"),
    ]

    for code, description, category in permissions:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, description, category) "
                "VALUES (:code, :description, :category) "
                "ON CONFLICT (code) DO NOTHING"
            ).bindparams(code=code, description=description, category=category)
        )


def downgrade() -> None:
    # Удаляем в обратном порядке зависимостей
    tables_to_drop = [
        "error_log", "audit_log", "self_employed_checks", "fast_answers",
        "auto_response_rules", "item_messages", "default_messages",
        "vacancies", "tasks", "mailing_recipients", "mailing_jobs",
        "chat_metadata", "chat_messages", "candidate_tags", "candidates",
        "tags", "pipeline_stages", "avito_webhook_endpoints", "avito_accounts",
        "user_permissions", "role_permissions", "user_departments", "departments",
        "permissions", "refresh_tokens", "user_auth_providers", "user_credentials",
        "users", "organizations",
    ]

    # Сначала удаляем FK suspended_by
    op.execute("ALTER TABLE organizations DROP CONSTRAINT IF EXISTS fk_org_suspended_by")

    for table in tables_to_drop:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
