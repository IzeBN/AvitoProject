"""tasks: add priority and status columns

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-19

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add priority column
    op.add_column(
        "tasks",
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="medium",
        ),
    )

    # Add status column
    op.add_column(
        "tasks",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="open",
        ),
    )

    # Migrate existing completed tasks to status 'done'
    op.execute("UPDATE tasks SET status = 'done' WHERE is_completed = TRUE")


def downgrade() -> None:
    op.drop_column("tasks", "status")
    op.drop_column("tasks", "priority")
