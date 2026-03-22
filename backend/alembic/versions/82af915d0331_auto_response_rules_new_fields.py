"""auto_response_rules: add avito_item_ids and message fields

Revision ID: 82af915d0331
Revises: 0006
Create Date: 2026-03-22 16:41:40.376146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '82af915d0331'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('auto_response_rules', sa.Column('avito_item_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('auto_response_rules', sa.Column('message', sa.Text(), nullable=True))
    op.drop_column('auto_response_rules', 'avito_item_id')


def downgrade() -> None:
    op.add_column('auto_response_rules', sa.Column('avito_item_id', sa.BIGINT(), autoincrement=False, nullable=True))
    op.drop_column('auto_response_rules', 'message')
    op.drop_column('auto_response_rules', 'avito_item_ids')
