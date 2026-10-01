"""Request and response shapes for waitlist entries."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.bookings.schemas import validate_rental_period
from app.core.clock import today
from app.vehicle_classes.schemas import VehicleClassSummary


class WaitlistEntryCreate(BaseModel):
    """The queue to join: a vehicle class and an exact date range.

    The provider is in the path, as it is for a booking, because a queue cannot
    exist without one. The user is from the token and never from the body.
    """

    model_config = ConfigDict(extra="forbid")

    vehicle_class_id: int = Field(ge=1, le=2147483647)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate_period(self) -> "WaitlistEntryCreate":
        # Exactly the rules booking creation applies, including the no-past-dates
        # one. Queueing for a range that has already gone is not a thing anyone
        # can be offered, so it is refused at the shape level rather than accepted
        # and then quietly ignored.
        validate_rental_period(self.start_date, self.end_date)
        if self.start_date < today():
            raise ValueError("start_date must not be in the past")
        return self


class WaitlistEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    provider_id: int
    start_date: date
    end_date: date
    created_at: datetime

    # The summary, for the reason `BookingRead` nests the summary: `vehicle_count`
    # comes from an aggregate query rather than the model, so the full read shape
    # would report a confident zero here.
    vehicle_class: VehicleClassSummary

    # Derived at read time, never stored. 1 is the front of the queue.
    position: int

    # False once the range has passed. Such an entry is inert: it stays visible as
    # the holder's own record, but no release will ever be offered to it, because
    # the dates it wanted are gone.
    is_active: bool

    # Null until released capacity has been offered to this entry. Once set, the
    # entry is out of contention for the next release.
    offered_at: datetime | None = None
