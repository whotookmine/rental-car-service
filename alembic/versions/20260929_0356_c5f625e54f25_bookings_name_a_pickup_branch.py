"""Bookings name a pickup branch; backfill existing rows.

Revision ID: c5f625e54f25
Revises: cb0b6c819227
Create Date: 2026-09-29 03:56:26.622686+00:00

Every booking now records which branch the car is collected from. The column is
fixed at creation like the provider and vehicle class — it describes the rental
that actually happened.

For existing bookings the pickup branch was never recorded. Each one is assigned
its provider's branch with the lowest id, which is the "Main Branch" that
migration cb0b6c819227 seeded from the provider's own address. This is a known
approximation: the actual pickup location when these bookings were made was simply
the provider's address. Assigning the corresponding "Main Branch" is the
closest honest value available.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c5f625e54f25'
down_revision: str | None = 'cb0b6c819227'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Added nullable first so the column can be added to a table that already
    # holds rows. Making it NOT NULL outright would fail on any populated
    # database. Same pattern as migration 40c06d630c4a (vehicle_class_id).
    op.add_column('bookings', sa.Column('pickup_branch_id', sa.Integer(), nullable=True))

    # Backfill: assign each existing booking the first (lowest-id) branch of its
    # provider. That branch is the "Main Branch" seeded by cb0b6c819227 from the
    # provider's own address — the best approximation of what was true when these
    # bookings were made.
    op.execute(
        sa.text(
            """
            UPDATE bookings b
            SET pickup_branch_id = (
                SELECT br.id
                FROM branches br
                WHERE br.provider_id = b.provider_id
                ORDER BY br.id
                LIMIT 1
            )
            WHERE b.pickup_branch_id IS NULL
            """
        )
    )

    op.alter_column('bookings', 'pickup_branch_id', nullable=False)
    op.create_index(
        op.f('ix_bookings_pickup_branch_id'), 'bookings', ['pickup_branch_id'], unique=False
    )
    # RESTRICT: removing a branch that bookings name must be refused, never
    # cascade. A cascade would delete rental history to tidy a catalogue.
    op.create_foreign_key(
        'fk_bookings_pickup_branch_id_branches',
        'bookings', 'branches',
        ['pickup_branch_id'], ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint('fk_bookings_pickup_branch_id_branches', 'bookings', type_='foreignkey')
    op.drop_index(op.f('ix_bookings_pickup_branch_id'), table_name='bookings')
    op.drop_column('bookings', 'pickup_branch_id')
