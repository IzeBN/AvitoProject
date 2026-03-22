"""tasks — align columns to model (assigned_to→responsible_id, status→is_completed)

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename assigned_to → responsible_id
    op.alter_column("tasks", "assigned_to", new_column_name="responsible_id")

    # Add is_completed boolean (derived from status='done')
    op.add_column(
        "tasks",
        sa.Column(
            "is_completed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    # Migrate existing data: status='done' → is_completed=true
    op.execute("UPDATE tasks SET is_completed = TRUE WHERE status = 'done'")

    # Drop status and priority columns (not used in model)
    op.drop_index("ix_tasks_org_status", table_name="tasks")
    op.drop_column("tasks", "status")
    op.drop_column("tasks", "priority")

    # Drop old index on assigned_to (now responsible_id)
    op.drop_index("ix_tasks_assigned_to", table_name="tasks")

    # Create new indexes matching model __table_args__
    op.create_index(
        "idx_tasks_org_responsible",
        "tasks",
        ["org_id", "responsible_id", "is_completed"],
    )
    op.create_index(
        "idx_tasks_candidate",
        "tasks",
        ["candidate_id"],
        postgresql_where=sa.text("candidate_id IS NOT NULL"),
    )
    op.create_index(
        "idx_tasks_org_deadline",
        "tasks",
        ["org_id", "deadline"],
        postgresql_where=sa.text("deadline IS NOT NULL AND is_completed = FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_org_deadline", table_name="tasks")
    op.drop_index("idx_tasks_candidate", table_name="tasks")
    op.drop_index("idx_tasks_org_responsible", table_name="tasks")

    op.add_column(
        "tasks",
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
    )
    op.add_column(
        "tasks",
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.execute("UPDATE tasks SET status = 'done' WHERE is_completed = TRUE")
    op.create_index("ix_tasks_org_status", "tasks", ["org_id", "status"])
    op.drop_column("tasks", "is_completed")

    op.alter_column("tasks", "responsible_id", new_column_name="assigned_to")
    op.create_index("ix_tasks_assigned_to", "tasks", ["assigned_to"])
