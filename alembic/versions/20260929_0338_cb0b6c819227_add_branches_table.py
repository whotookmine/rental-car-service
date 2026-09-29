"""Add branches table; seed one branch per existing provider.

Revision ID: cb0b6c819227
Revises: 40c06d630c4a
Create Date: 2026-09-29 03:38:38.741215+00:00

A provider previously had a single address column of its own. Branches replace
that as the concept of "where you pick up a car", but the provider row keeps its
address and telephone columns unchanged. They remain the general business contact
details (used in booking responses and the provider catalogue); a branch address
is the specific pickup location a booking will later name.

For every existing provider, this migration inserts one branch named "Main Branch"
carrying the provider's current address and telephone, so no provider is left
without a branch and no address is lost.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'cb0b6c819227'
down_revision: str | None = '40c06d630c4a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'branches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=False),
        sa.Column('telephone', sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_branches_provider_id'), 'branches', ['provider_id'], unique=False
    )

    # Seed one "Main Branch" for every existing provider, copying its address and
    # telephone, so the at-least-one-branch invariant holds from the moment this
    # migration is applied to a database that already has data.
    op.execute(
        sa.text(
            """
            INSERT INTO branches (provider_id, name, address, telephone)
            SELECT id, 'Main Branch', address, telephone
            FROM providers
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_branches_provider_id'), table_name='branches')
    op.drop_table('branches')
