"""candidates: add vacancy_id FK to vacancies table

Revision ID: 0008
Revises: 82af915d0331
Create Date: 2026-03-23 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'candidates',
        sa.Column(
            'vacancy_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('vacancies.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.create_index('idx_candidates_vacancy_id', 'candidates', ['vacancy_id'])


def downgrade() -> None:
    op.drop_index('idx_candidates_vacancy_id', table_name='candidates')
    op.drop_column('candidates', 'vacancy_id')
