"""add delivery fields to bookings (ticket 37)

Revision ID: bcd2ef34567a
Revises: abc1def23456
Create Date: 2026-10-31 17:44:00.000000+00:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'bcd2ef34567a'
down_revision: tuple[str, ...] | None = ('77cc8d1d47ac', 'abc1def23456')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('delivery_address', sa.String(500), nullable=True))
    op.add_column('bookings', sa.Column('delivery_distance_km', sa.Integer(), nullable=True))
    op.add_column('bookings', sa.Column('collection_address', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('bookings', 'collection_address')
    op.drop_column('bookings', 'delivery_distance_km')
    op.drop_column('bookings', 'delivery_address')
