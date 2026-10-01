"""The WaitlistEntry model: one person's place in one queue.

A **queue** is identified by a provider, a vehicle class and an exact date range.
Two people wanting overlapping but different ranges are in different queues, which
is what the requirement describes -- capacity released for the 10th to the 12th is
not capacity for the 9th to the 15th, and pretending otherwise would offer people
cars they cannot use.

Position in a queue is **never stored**, only derived from join order. A stored
position would have to be rewritten for everyone behind someone who leaves, and the
first missed update would leave two people believing they were third.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.vehicle_classes.models import VehicleClass


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    __table_args__ = (
        # One person, one place in any given queue. The second attempt is a
        # conflict rather than a silent no-op, so a caller who thinks they joined
        # twice learns they did not.
        UniqueConstraint(
            "user_id",
            "vehicle_class_id",
            "start_date",
            "end_date",
            name="uq_waitlist_entries_one_place_per_queue",
        ),
        # The query ticket 44 runs on every cancellation: one queue, in join order.
        Index(
            "ix_waitlist_entries_queue_order",
            "vehicle_class_id",
            "start_date",
            "end_date",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # CASCADE, like a booking's owner: a place in a queue belongs to a person and
    # means nothing without them.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Stored rather than derived through the class, matching how a booking carries
    # both. The requirement describes the queue as being per provider as well as
    # per class, and a reader of this table should not have to join to see whose
    # queue they are looking at.
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id"), nullable=False, index=True
    )

    # RESTRICT, matching bookings: a class someone is queueing for cannot be
    # deleted out from under them.
    # No `index=True`: `ix_waitlist_entries_queue_order` above starts with this
    # column, so it already serves a lookup by class alone. A second single-column
    # index would cost every insert and serve no query.
    vehicle_class_id: Mapped[int] = mapped_column(
        ForeignKey("vehicle_classes.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # The exact range wanted. Part of the queue's identity, not a preference.
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # An instant, not a date -- see `app/core/clock.py`. The order of this column
    # *is* the FIFO order the requirement demands, so it has to distinguish two
    # entries made a moment apart. A date could not.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Set when released capacity has been offered to this entry, null until then.
    # An offered entry is out of contention for the next release: that is what makes
    # two cancellations in quick succession reach the first and second person in the
    # queue rather than both reaching the first.
    #
    # An instant rather than a flag, for the reason `read_at` on a notification is:
    # it answers strictly more, and "when was this offered" is the question anyone
    # investigating a queue actually asks. Ticket 45 gives the offer an expiry.
    offered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # When the offer stops being exclusive. Set alongside `offered_at` from the
    # configured claim window, so the two are always written together -- an offer
    # without a deadline would hold a car forever.
    claim_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Set when the holder turns the claim into a booking. The claim is then spent:
    # it cannot be taken again, and it no longer holds anything, because the booking
    # it became does.
    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # The booking the claim became. `SET NULL` rather than `CASCADE`: if that
    # booking is later deleted, the record that this entry was once converted must
    # survive -- otherwise the entry would look like it is still waiting, and the
    # queue would offer it capacity a second time. `converted_at` is what the rules
    # read; this is for anyone tracing where a booking came from.
    # The constraint is named here as well as in the migration. Autogenerate emitted
    # an unnamed one, whose downgrade -- `drop_constraint(None, ...)` -- cannot work,
    # because PostgreSQL has no way to drop a constraint you cannot name. Naming it
    # in the model keeps a future autogenerate from reintroducing the same problem.
    converted_booking_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "bookings.id",
            ondelete="SET NULL",
            name="fk_waitlist_entries_converted_booking_id",
        ),
        nullable=True,
        default=None,
    )

    # Set when the holder gives the claim up early. Distinct from expiry on purpose:
    # declining is a decision and releases the car immediately, while expiry is the
    # absence of one. Both end the claim, and ticket 46 passes both on the same way.
    declined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    vehicle_class: Mapped[VehicleClass] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<WaitlistEntry id={self.id} user={self.user_id} "
            f"class={self.vehicle_class_id} {self.start_date}..{self.end_date}>"
        )
