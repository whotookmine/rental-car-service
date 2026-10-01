"""blackout windows per vehicle (ticket 39)

Revision ID: 6d61ecfdaaf8
Revises: 1228c9d212a5
Create Date: 2026-10-01 18:03:56.574689+00:00

A period during which one vehicle is off the road for servicing.

Two things here were written by hand rather than by autogeneration, and both
matter:

- **`CREATE EXTENSION btree_gist`.** The exclusion constraint compares an integer
  for equality inside a GiST index, which core PostgreSQL cannot do. Alembic
  rendered the constraint but not the extension it depends on, so the generated
  migration failed on a clean database. `btree_gist` is a bundled contrib module
  and is trusted from PostgreSQL 13, so the database owner can create it without
  superuser rights -- verified against the Compose database as the `rental` user.
- **The downgrade leaves the extension in place.** Dropping it would break anything
  else that came to depend on it, and an unused extension costs nothing. Dropping
  a table is reversible; guessing that nobody else wanted an extension is not.

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '6d61ecfdaaf8'
down_revision: str | None = '1228c9d212a5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        'blackout_windows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        # No two windows on one vehicle may share a day. `daterange(start, end,
        # '[]')` is inclusive at both ends, matching how every other period in
        # this system is counted, so a window ending on the 5th does not clash
        # with one starting on the 6th. Scoped by `vehicle_id WITH =`, so two
        # different cars may be in the workshop on the same days.
        postgresql.ExcludeConstraint(
            (sa.column('vehicle_id'), '='),
            (sa.text("daterange(start_date, end_date, '[]')"), '&&'),
            using='gist',
            name='no_overlapping_blackout_windows_per_vehicle',
        ),
        # RESTRICT, matching every other reference to a vehicle: removing a car
        # that has a service history is refused rather than cascading the history
        # away. `DELETE /vehicles/{id}` turns the resulting error into a 409.
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_blackout_windows_vehicle_id'),
        'blackout_windows',
        ['vehicle_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_blackout_windows_vehicle_id'), table_name='blackout_windows')
    op.drop_table('blackout_windows')
    # btree_gist is deliberately left installed. See the module docstring.
