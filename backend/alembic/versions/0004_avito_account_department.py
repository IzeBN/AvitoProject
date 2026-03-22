"""avito_accounts — add department_id FK

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "avito_accounts",
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_avito_accounts_department",
        "avito_accounts",
        ["department_id"],
        postgresql_where=sa.text("department_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_avito_accounts_department", table_name="avito_accounts")
    op.drop_column("avito_accounts", "department_id")
