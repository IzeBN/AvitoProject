"""chat_messages: make idx_chat_msgs_avito_id unique

Revision ID: 0007
Revises: 82af915d0331
Create Date: 2026-03-23 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "82af915d0331"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("idx_chat_msgs_avito_id", table_name="chat_messages")
    op.create_index(
        "idx_chat_msgs_avito_id",
        "chat_messages",
        ["avito_message_id"],
        unique=True,
        postgresql_where=sa.text("avito_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_chat_msgs_avito_id", table_name="chat_messages")
    op.create_index(
        "idx_chat_msgs_avito_id",
        "chat_messages",
        ["avito_message_id"],
        unique=False,
        postgresql_where=sa.text("avito_message_id IS NOT NULL"),
    )
