"""The Booking model: one registered user's rental period with one provider.

There is no Car. A booking reserves a period with a provider; the brief models
providers, not fleets, and reviews rate the provider. See `CONTEXT.md`.
"""

from datetime import date

from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.providers.models import Provider


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The owner, always taken from the access token and never from a request.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Fixed at creation. A booking can be re-dated but never re-pointed, which
    # is what keeps a review attached to the provider actually rented from.
    # Providers are retired rather than deleted, so there is nothing to cascade.
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id"), nullable=False, index=True
    )

    # Plain dates. A rental has no pickup or return time in this domain, and
    # storing an instant would invite timezone conversion to shift the day.
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Joined eagerly: every route that returns a booking reports who it is with,
    # so a lazy load would mean one extra query per booking in a list.
    provider: Mapped[Provider] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Booking id={self.id} user={self.user_id} "
            f"provider={self.provider_id} {self.start_date}..{self.end_date}>"
        )
