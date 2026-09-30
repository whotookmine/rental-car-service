"""Request and response shapes for vehicle classes."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.core.money import Money


def _require_content(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class VehicleClassCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)

    # Optional at creation. Null means unpriced; zero means free.
    daily_rate: Decimal | None = Field(default=None, ge=0)

    @field_validator("name", "description")
    @classmethod
    def _strip_and_require_content(cls, value: str) -> str:
        return _require_content(value)


class VehicleClassUpdate(BaseModel):
    """Only the name, description, and daily rate are editable.

    There is deliberately no `provider_id` here. A class belongs to one provider
    for its whole life; leaving the field out is what enforces that, rather than
    accepting it and then refusing it.

    `daily_rate` uses `model_fields_set` in the router to distinguish "not sent"
    (no change) from "sent as null" (remove the price / mark unpriced).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=1000)

    # None here can mean either "not sent" or "set to null". The router checks
    # `model_fields_set` to tell them apart.
    daily_rate: Decimal | None = Field(default=None, ge=0)

    @field_validator("name", "description")
    @classmethod
    def _strip_and_require_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_content(value)


class VehicleClassSummary(BaseModel):
    """A vehicle class as it appears *inside* another resource, such as a booking.

    Deliberately carries no `vehicle_count`. That number is produced by an
    aggregate query, not by reading the model, so a schema validated straight
    from a `VehicleClass` object would fall back to the default and report a
    confident zero. A field that is sometimes a lie is worse than an absent one.

    `daily_rate` is null when the class has not been priced yet. Null and zero
    mean different things: zero is free, null is unpriced.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    name: str
    description: str
    daily_rate: Money | None = None

    @field_validator("daily_rate", mode="before")
    @classmethod
    def _coerce_to_money(cls, value: object) -> Money | None:
        """Convert a raw Decimal (from the ORM) to a Money object.

        `VehicleClass.daily_rate` stores a `Decimal`; this validator wraps it
        in `Money` with the configured currency so the schema never exposes a
        bare number. A `Money` that arrives pre-built (e.g. from a test) passes
        through unchanged.
        """
        if value is None:
            return None
        if isinstance(value, Money):
            return value
        return Money(amount=Decimal(str(value)), currency=get_settings().currency)


class VehicleClassRead(VehicleClassSummary):
    """A vehicle class as its own resource, where the count is computed."""

    # How many cars sit in this class. Counted on read, never stored, for the
    # same reason a provider's average rating is: a stored count drifts the
    # moment a car is added or removed outside the one code path that maintains
    # it. This is the capacity ticket 26 enforces.
    vehicle_count: int = 0
