"""The Vehicle model: one individual car in a provider's fleet.

A vehicle class says what kind of car; a vehicle is a particular one of them,
identified by its plate. Two later features need the individual unit rather than
the kind: capacity in ticket 26 is a count of these, and a maintenance blackout
in ticket 39 takes one car off the road, not a whole category.
"""

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.vehicle_classes.models import VehicleClass


class Vehicle(Base):
    __tablename__ = "vehicles"

    # Plates are unique across the whole system, not per provider: a plate
    # identifies a car on the road, and the same one appearing under two
    # providers would mean one of them has it wrong. Compared without regard to
    # case, as with vehicle class names, because "1กก1234" and "1KK1234" being
    # distinguishable by shift key would let the same car be entered twice.
    __table_args__ = (
        Index(
            "uq_vehicles_lower_plate",
            text("lower(plate)"),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # RESTRICT, not CASCADE: removing a class that still has cars in it must be
    # refused, so that catalogue housekeeping can never quietly delete a fleet.
    # This is the foreign key that makes ticket 23's "vehicle class is in use"
    # refusal real rather than theoretical.
    vehicle_class_id: Mapped[int] = mapped_column(
        ForeignKey("vehicle_classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    plate: Mapped[str] = mapped_column(String(20), nullable=False)

    vehicle_class: Mapped[VehicleClass] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Vehicle id={self.id} class={self.vehicle_class_id} "
            f"plate={self.plate!r}>"
        )
