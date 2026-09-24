"""Request and response shapes for bookings."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.clock import today
from app.providers.schemas import ProviderRead
from app.vehicle_classes.schemas import VehicleClassSummary

# A rental period is counted inclusively: a booking from the 1st to the 30th is
# thirty days, not twenty-nine. The cap exists so that one booking cannot occupy
# a slot indefinitely.
MAX_RENTAL_DAYS = 30


def rental_period_days(start: date, end: date) -> int:
    """Length of a rental period in days, counting both endpoints."""
    return (end - start).days + 1


def validate_rental_period(start: date, end: date) -> None:
    """The shape rules a rental period must satisfy, however it arrived.

    Creation and re-dating share exactly these. They deliberately do not include
    the no-past-dates rule: that one applies only when a booking is first made,
    because a rental already underway must still be extendable and an admin must
    be able to correct history.
    """
    if end < start:
        raise ValueError("end_date must not be before start_date")

    length = rental_period_days(start, end)
    if length > MAX_RENTAL_DAYS:
        raise ValueError(
            f"a rental period may be at most {MAX_RENTAL_DAYS} days; this one is {length}"
        )


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Required, with no default. A booking without a kind of car cannot be
    # matched against capacity or queued on a waitlist, so there is no sensible
    # thing to fall back to; omitting it is a 422.
    vehicle_class_id: int = Field(ge=1, le=2147483647)

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate_period_for_creation(self) -> "BookingCreate":
        validate_rental_period(self.start_date, self.end_date)

        # Creation only. Re-dating may touch past dates, so that a rental already
        # underway can be extended and history can be corrected. today() reads the
        # configured business timezone, never the system clock.
        if self.start_date < today():
            raise ValueError("start_date must not be in the past")

        return self


class BookingUpdate(BaseModel):
    """New dates for an existing booking.

    Both dates are required: a rental period is one value with two halves, and
    replacing it wholesale keeps the rules on the schema, where they answer 422,
    rather than in the handler. The provider and the vehicle class are absent on
    purpose and `extra` is forbidden, so an attempt to move a booking to another
    provider, or to change what kind of car it is for, is refused loudly instead
    of being silently ignored. Both are fixed at creation for the same reason: a
    review must keep describing what was actually rented.
    """

    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate_period(self) -> "BookingUpdate":
        validate_rental_period(self.start_date, self.end_date)
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

    # The summary, not the full read shape: `vehicle_count` comes from an
    # aggregate query rather than from the model, so nesting the full shape here
    # would report a confident zero for every booking.
    vehicle_class: VehicleClassSummary
