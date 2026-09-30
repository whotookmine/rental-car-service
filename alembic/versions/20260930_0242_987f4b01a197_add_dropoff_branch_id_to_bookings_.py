"""add dropoff_branch_id to bookings (ticket 32)

Revision ID: 987f4b01a197
Revises: dea85e5ae1f0
Create Date: 2026-09-30 02:42:30.573189+00:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '987f4b01a197'
down_revision: str | None = 'dea85e5ae1f0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('dropoff_branch_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_bookings_dropoff_branch_id'), 'bookings', ['dropoff_branch_id'], unique=False)
    op.create_foreign_key(
        'fk_bookings_dropoff_branch_id_branches',
        'bookings', 'branches',
        ['dropoff_branch_id'], ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint('fk_bookings_dropoff_branch_id_branches', 'bookings', type_='foreignkey')
    op.drop_index(op.f('ix_bookings_dropoff_branch_id'), table_name='bookings')
    op.drop_column('bookings', 'dropoff_branch_id')
