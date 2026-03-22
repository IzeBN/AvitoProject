"""users.org_id nullable — пользователи без организации

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-19
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "org_id", nullable=True)


def downgrade() -> None:
    # Перед откатом убедись, что нет строк с org_id IS NULL
    op.execute("DELETE FROM users WHERE org_id IS NULL")
    op.alter_column("users", "org_id", nullable=False)
