"""add users table

Revision ID: 3fb08066c5cf
Revises: edd6e900ece8
Create Date: 2026-09-13 18:47:22.767395+00:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '3fb08066c5cf'
down_revision: str | None = 'edd6e900ece8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('telephone', sa.String(length=40), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column(
            'role',
            sa.Enum('user', 'admin', name='user_role'),
            server_default='user',
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )


def downgrade() -> None:
    op.drop_table('users')
    # Dropping the table leaves the enum type behind in PostgreSQL, and the next
    # upgrade would then fail with "type user_role already exists".
    sa.Enum(name='user_role').drop(op.get_bind(), checkfirst=True)
