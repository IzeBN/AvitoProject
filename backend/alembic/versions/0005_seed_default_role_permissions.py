"""seed default role permissions for existing orgs

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

MANAGER_PERMISSIONS = [
    "crm.candidates.view",
    "crm.candidates.create",
    "crm.candidates.edit",
    "crm.candidates.delete",
    "crm.stages.manage",
    "crm.tags.manage",
    "mailing.view",
    "mailing.send",
    "mailing.manage",
    "vacancies.view",
    "vacancies.manage",
    "messaging.view",
    "messaging.send",
    "messaging.auto_response",
    "self_employed.check",
    "analytics.view",
]

ADMIN_EXTRA_PERMISSIONS = [
    "avito.accounts.view",
    "avito.accounts.manage",
    "avito.webhooks.manage",
    "admin.users.view",
    "admin.users.manage",
    "admin.departments.manage",
    "admin.settings.manage",
    "admin.audit.view",
    "admin.errors.view",
]

ADMIN_PERMISSIONS = MANAGER_PERMISSIONS + ADMIN_EXTRA_PERMISSIONS


def upgrade() -> None:
    conn = op.get_bind()

    # Сначала убеждаемся что все коды есть в таблице permissions (FK)
    all_codes = list(dict.fromkeys(MANAGER_PERMISSIONS + ADMIN_EXTRA_PERMISSIONS))
    for code in all_codes:
        conn.execute(
            sa.text("INSERT INTO permissions (code) VALUES (:code) ON CONFLICT DO NOTHING"),
            {"code": code},
        )

    # Получаем все org_id
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()

    for (org_id,) in orgs:
        for code in MANAGER_PERMISSIONS:
            conn.execute(
                sa.text("""
                    INSERT INTO role_permissions (org_id, role, permission_code)
                    VALUES (:org_id, 'manager', :code)
                    ON CONFLICT DO NOTHING
                """),
                {"org_id": str(org_id), "code": code},
            )
        for code in ADMIN_PERMISSIONS:
            conn.execute(
                sa.text("""
                    INSERT INTO role_permissions (org_id, role, permission_code)
                    VALUES (:org_id, 'admin', :code)
                    ON CONFLICT DO NOTHING
                """),
                {"org_id": str(org_id), "code": code},
            )


def downgrade() -> None:
    pass
