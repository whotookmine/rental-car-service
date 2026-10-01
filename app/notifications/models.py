"""The Notification model: something the system has to tell one user.

Records the user polls, not email. SMTP would mean credentials, deliverability and
an external dependency the brief never asks for, and none of it can be shown in
Postman -- which is the project's only demonstration. A row in a table can be.

**Nothing in the service writes one yet.** This is the place the waitlist notifies
into when a cancellation releases a car (tickets 43 to 46); until then the table is
read-only in practice, and the fixture seeds a couple so the surface can be
demonstrated at all. `app/seed.py` says so where it creates them.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class NotificationKind(StrEnum):
    """What produced a notification.

    Only the kinds that actually exist are listed. The waitlist tickets add theirs
    when they add the code that emits them -- inventing those names here would be
    guessing at an interface that does not exist yet, and a kind nothing produces
    is worse than a missing one because it reads as a promise.
    """

    booking_confirmed = "booking_confirmed"
    booking_ended = "booking_ended"


class Notification(Base):
    __tablename__ = "notifications"

    # The only query this table serves: one user's notifications, newest first.
    __table_args__ = (
        Index(
            "ix_notifications_user_id_created_at",
            "user_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # CASCADE, matching a booking's owner: a notification is addressed to one
    # person and means nothing without them. There is no history worth keeping
    # once the recipient is gone, which is why this is the one place a cascade is
    # right where vehicles and classes use RESTRICT.
    # No `index=True`: the composite index above starts with `user_id`, so it
    # already serves a lookup by user alone. A second single-column index would be
    # dead weight on every insert for no query that needs it.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # A short machine-readable tag, so a client can style or filter without
    # parsing prose. Stored as a string rather than a PostgreSQL enum: the set of
    # kinds grows every time a feature starts emitting one, and a database enum
    # would make each of those a migration for no guarantee anyone needs.
    # `NotificationKind` above is the list of kinds that exist.
    kind: Mapped[str] = mapped_column(String(50), nullable=False)

    # The sentence a person reads. Written when the notification is created and
    # never rewritten: it describes what was true at that moment, and editing it
    # later would make the record lie about what the user was told.
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # An instant, not a date -- see `app/core/clock.py` for why that distinction
    # is deliberate. `timezone=True` so the offset is stored rather than guessed.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Null until the user marks it read, then the moment they did. A timestamp
    # rather than a boolean because it answers strictly more -- "has it been read"
    # is `read_at is not None` -- and because "when did they see this" is the
    # question anyone debugging a missed notification actually asks.
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def is_read(self) -> bool:
        """Derived, never stored. One fact, one column."""
        return self.read_at is not None

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Notification id={self.id} user={self.user_id} "
            f"kind={self.kind!r} read={self.is_read}>"
        )
