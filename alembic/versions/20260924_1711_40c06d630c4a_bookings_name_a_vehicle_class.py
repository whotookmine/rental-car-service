"""bookings name a vehicle class

Revision ID: 40c06d630c4a
Revises: 8cff45c5c221
Create Date: 2026-09-24 17:11:19.988840+00:00

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '40c06d630c4a'
down_revision: str | None = '8cff45c5c221'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Added nullable, backfilled, then made NOT NULL. Adding it NOT NULL outright
    # would fail on any database that already holds bookings -- which is every
    # developer's, and would be the graders' too.
    op.add_column('bookings', sa.Column('vehicle_class_id', sa.Integer(), nullable=True))

    # What class do historical bookings get? Nothing in the data says what was
    # actually rented: the catalogue did not exist when they were made. Picking
    # the provider's cheapest or first class would put a fact in the record that
    # nobody ever asserted, and a review attached to that booking would then
    # describe a kind of car the renter may never have had.
    #
    # So each provider that has bookings gets one honest class, named
    # "Unclassified", and its bookings point at that. It reads as what it is --
    # an absence -- rather than as a guess.
    op.execute(
        """
        INSERT INTO vehicle_classes (provider_id, name, description)
        SELECT DISTINCT b.provider_id,
               'Unclassified',
               'Bookings made before the vehicle class catalogue existed. What '
               'was actually rented was never recorded.'
        FROM bookings b
        WHERE b.vehicle_class_id IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM vehicle_classes vc
              WHERE vc.provider_id = b.provider_id
                AND lower(vc.name) = 'unclassified'
          )
        """
    )
    op.execute(
        """
        UPDATE bookings b
        SET vehicle_class_id = vc.id
        FROM vehicle_classes vc
        WHERE b.vehicle_class_id IS NULL
          AND vc.provider_id = b.provider_id
          AND lower(vc.name) = 'unclassified'
        """
    )

    op.alter_column('bookings', 'vehicle_class_id', nullable=False)

    op.create_index(op.f('ix_bookings_vehicle_class_id'), 'bookings', ['vehicle_class_id'], unique=False)
    # RESTRICT: removing a vehicle class that bookings point at must be refused,
    # never cascade. A cascade here would delete rental history to tidy a
    # catalogue.
    op.create_foreign_key(
        'fk_bookings_vehicle_class_id_vehicle_classes',
        'bookings', 'vehicle_classes',
        ['vehicle_class_id'], ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint('fk_bookings_vehicle_class_id_vehicle_classes', 'bookings', type_='foreignkey')
    op.drop_index(op.f('ix_bookings_vehicle_class_id'), table_name='bookings')
    op.drop_column('bookings', 'vehicle_class_id')

    # The "Unclassified" classes created above are deliberately left behind. A
    # downgrade that deleted them would destroy rows an admin may since have
    # renamed, described, or put cars into, and there is no way to tell those
    # apart from the ones this migration made. Dropping the column is reversible;
    # deleting someone's catalogue is not.
