"""chat_messages: avito_message_id dedup note (no-op)

chat_messages is partitioned by created_at; PostgreSQL requires all partition
key columns in unique indexes, so a standalone unique index on avito_message_id
is not possible. Deduplication is handled at the application layer via
WHERE NOT EXISTS in webhook_worker.py.

Revision ID: 0007
Revises: 82af915d0331
Create Date: 2026-03-23 00:00:00.000000
"""
from typing import Sequence, Union

revision: str = "0007"
down_revision: Union[str, None] = "82af915d0331"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
