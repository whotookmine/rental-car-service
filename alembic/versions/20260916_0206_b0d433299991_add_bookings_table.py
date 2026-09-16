"""add bookings table

Revision ID: b0d433299991
Revises: 95ac203c34d4
Create Date: 2026-09-16 02:06:41.060024+00:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b0d433299991'
down_revision: str | None = '95ac203c34d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('bookings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('provider_id', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bookings_provider_id'), 'bookings', ['provider_id'], unique=False)
    op.create_index(op.f('ix_bookings_user_id'), 'bookings', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_bookings_user_id'), table_name='bookings')
    op.drop_index(op.f('ix_bookings_provider_id'), table_name='bookings')
    op.drop_table('bookings')
