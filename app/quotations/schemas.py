"""Request and response shapes for quotations."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.bookings.schemas import validate_rental_period
from app.core.clock import today
from app.core.money import Money


class QuotationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_class_id: int = Field(ge=1, le=2147483647)
    pickup_branch_id: int = Field(ge=1, le=2147483647)
    dropoff_branch_id: int | None = Field(default=None, ge=1, le=2147483647)
    start_date: date
    end_date: date

    # Optional delivery. Mirrors booking creation: distance and address must
    # come as a pair or both be omitted. Only distance is needed for pricing.
    delivery_distance_km: int | None = Field(default=None, ge=0)
    delivery_address: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def _validate_period(self) -> "QuotationRequest":
        validate_rental_period(self.start_date, self.end_date)
        if self.start_date < today():
            raise ValueError("start_date must not be in the past")
        addr = self.delivery_address
        dist = self.delivery_distance_km
        if (addr is None) != (dist is None):
            raise ValueError(
                "delivery_address and delivery_distance_km must both be provided or both omitted"
            )
        return self


class QuotationLine(BaseModel):
    description: str
    amount: Money


class QuotationRead(BaseModel):
    lines: list[QuotationLine]
    total: Money
