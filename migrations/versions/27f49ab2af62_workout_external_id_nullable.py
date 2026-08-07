"""workout external_id nullable

Revision ID: 27f49ab2af62
Revises: e2a993655b7d
Create Date: 2026-08-06 21:45:01.089298

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '27f49ab2af62'
down_revision: Union[str, None] = 'e2a993655b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('raw_workouts') as batch_op:
        batch_op.alter_column('external_id',
                   existing_type=sa.VARCHAR(length=255),
                   nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('raw_workouts') as batch_op:
        batch_op.alter_column('external_id',
                   existing_type=sa.VARCHAR(length=255),
                   nullable=False)
