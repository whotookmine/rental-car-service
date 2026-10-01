"""The BlackoutWindow model: a period when one vehicle is off the road.

Scheduled per vehicle rather than per vehicle class, because that is what the
requirement asks for and because it is the truth: a workshop takes one car in, not
a category. This is the feature ticket 24 modelled individual units for.

A window says nothing about bookings on its own. Ticket 40 makes availability
count only cars that are on the road, and ticket 41 refuses bookings that would
need a car that is in the workshop. Until then a window is a record and nothing
more, which is deliberate -- the schedule has to exist before anything can be
enforced against it.
"""

from datetime import date

from sqlalchemy import Date, ForeignKey, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.vehicles.models import Vehicle


class BlackoutWindow(Base):
    __tablename__ = "blackout_windows"

    # Two windows on the same car may not overlap, and this is the guarantee
    # rather than the lookup in the router that produces the readable message.
    # `daterange(start, end, '[]')` is inclusive at both ends, matching how every
    # other period in this system is counted: a window from the 1st to the 1st is
    # one day, and one ending on the 5th does not overlap one starting on the 6th.
    #
    # The `&&` operator is "ranges overlap"; `vehicle_id WITH =` scopes the
    # constraint to one car, so two cars may be in the workshop on the same days.
    # Integer equality inside a GiST index needs the `btree_gist` extension, which
    # the migration creates.
    __table_args__ = (
        ExcludeConstraint(
            ("vehicle_id", "="),
            (text("daterange(start_date, end_date, '[]')"), "&&"),
            name="no_overlapping_blackout_windows_per_vehicle",
            using="gist",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # RESTRICT, matching every other reference to a vehicle and to a vehicle
    # class: removing a car that has a service history must be refused, not
    # quietly take the history with it. `delete_vehicle` already turns the
    # resulting IntegrityError into a 409, so this is the key that makes that
    # refusal real rather than theoretical.
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Plain dates, inclusive at both ends, exactly like a rental period. A window
    # may sit wholly in the past: a service that already happened is a fact worth
    # recording, and an admin correcting last month's schedule is ordinary work.
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    vehicle: Mapped[Vehicle] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BlackoutWindow id={self.id} vehicle={self.vehicle_id} "
            f"{self.start_date}..{self.end_date}>"
        )
