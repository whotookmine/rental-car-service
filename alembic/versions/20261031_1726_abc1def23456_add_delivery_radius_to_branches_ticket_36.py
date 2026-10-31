"""add delivery_radius_km to branches (ticket 36)

Revision ID: abc1def23456
Revises: 1228c9d212a5
Create Date: 2026-10-31 17:26:00.000000+00:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'abc1def23456'
down_revision: str | None = '1228c9d212a5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('branches', sa.Column('delivery_radius_km', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('branches', 'delivery_radius_km')
