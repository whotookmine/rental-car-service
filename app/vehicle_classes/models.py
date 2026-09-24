"""The VehicleClass model: one kind of car a provider rents out.

A provider used to be the whole of what a booking pointed at; `CONTEXT.md` said
in so many words that individual vehicles were not modelled. The second round of
requirements talks about a fully-booked vehicle class and a waitlist that queues
for one, so the kind of car is now a thing in its own right.

A class belongs to exactly one provider for its whole life. Nothing moves it: the
provider is set at creation and the update shape has no field for it, because a
booking that named a class would otherwise silently change which business it was
with.
"""

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.providers.models import Provider


class VehicleClass(Base):
    __tablename__ = "vehicle_classes"

    # Names are unique per provider, compared without regard to case: "SUV" and
    # "suv" are the same kind of car to a reader, so letting both exist under one
    # provider would make the catalogue lie. Two providers may of course both
    # offer an "SUV", hence the constraint is per provider and not global.
    __table_args__ = (
        Index(
            "uq_vehicle_classes_provider_id_lower_name",
            "provider_id",
            text("lower(name)"),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[Provider] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<VehicleClass id={self.id} provider={self.provider_id} "
            f"name={self.name!r}>"
        )
