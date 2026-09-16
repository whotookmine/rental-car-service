"""Request and response shapes for bookings."""

from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.clock import today
from app.providers.schemas import ProviderRead

# A rental period is counted inclusively: a booking from the 1st to the 30th is
# thirty days, not twenty-nine. The cap exists so that one booking cannot occupy
# a slot indefinitely.
MAX_RENTAL_DAYS = 30


def rental_period_days(start: date, end: date) -> int:
    """Length of a rental period in days, counting both endpoints."""
    return (end - start).days + 1


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate_period_for_creation(self) -> "BookingCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")

        length = rental_period_days(self.start_date, self.end_date)
        if length > MAX_RENTAL_DAYS:
            raise ValueError(
                f"a rental period may be at most {MAX_RENTAL_DAYS} days; this one is {length}"
            )

        # Only on creation. Editing a booking may touch past dates, so that a
        # rental already underway can be extended and history can be corrected.
        # today() reads the configured business timezone, never the system clock.
        if self.start_date < today():
            raise ValueError("start_date must not be in the past")

        return self


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    start_date: date
    end_date: date

    # Nested rather than a bare provider_id: a booking is only useful if you can
    # see who it is with and how to reach them.
    provider: ProviderRead
