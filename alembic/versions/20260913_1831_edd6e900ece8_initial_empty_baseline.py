"""initial empty baseline

Ticket 01 is scaffold only: there are no models yet, so this baseline creates no
tables. Its purpose is to establish the migration chain and the alembic_version
table against an empty database. Later tickets add their tables on top.

Revision ID: edd6e900ece8
Revises: 
Create Date: 2026-09-13 18:31:22.075558+00:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'edd6e900ece8'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Intentionally empty: ticket 01 is scaffold only and defines no models. This
    # revision exists to establish the migration chain and the alembic_version
    # table. Later tickets add their tables on top of it.
    pass


def downgrade() -> None:
    # Nothing to undo; this revision creates no schema objects.
    pass
