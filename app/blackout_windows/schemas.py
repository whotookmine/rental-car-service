"""Request and response shapes for maintenance blackout windows."""

from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator


def validate_window(start: date, end: date) -> None:
    """The shape rules a blackout window must satisfy, however it arrived.

    Deliberately shorter than a rental period's rules, and the differences are
    the point:

    - **No no-past-dates rule.** A rental cannot be created in the past because a
      user cannot rent a car for days that have gone. A service can absolutely
      have happened last week, and recording it is how the schedule stays honest.
    - **No maximum length.** A rental period caps at thirty days so that one
      booking cannot occupy a slot indefinitely. A car can be off the road for
      months after a crash, and inventing a cap here would mean an admin had to
      lie about it in instalments.

    What survives is the one rule that is about the shape of a period rather than
    about renting: it ends on or after it starts, counted inclusively.
    """
    if end < start:
        raise ValueError("end_date must not be before start_date")


class BlackoutWindowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate(self) -> "BlackoutWindowCreate":
        validate_window(self.start_date, self.end_date)
        return self


class BlackoutWindowUpdate(BaseModel):
    """New dates for an existing window.

    Both dates are required: a window is one value with two halves, so replacing
    it wholesale keeps the rules on the schema where they answer 422.

    The vehicle is absent on purpose and `extra` is forbidden, so an attempt to
    move a window to another car is refused rather than ignored. A window records
    what happened to a particular car; pointing it at a different one would not be
    an edit but a fabrication. The way to say "the wrong car was booked in" is to
    cancel this window and schedule one on the right car.
    """

    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate(self) -> "BlackoutWindowUpdate":
        validate_window(self.start_date, self.end_date)
        return self


class BlackoutWindowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    start_date: date
    end_date: date
