"""Request and response shapes for vehicles."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_plate(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class VehicleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plate: str = Field(min_length=1, max_length=20)

    @field_validator("plate")
    @classmethod
    def _strip_and_require_content(cls, value: str) -> str:
        return _clean_plate(value)


class VehicleUpdate(BaseModel):
    """The plate, and the class the car sits in.

    `vehicle_class_id` is here, unlike `provider_id` on a vehicle class, because
    reclassifying a car within the same fleet is a real thing an admin does — a
    car moves from Economy to Compact. Moving it to *another provider's* class is
    refused in the handler, since that is a sale, not a reclassification.
    """

    model_config = ConfigDict(extra="forbid")

    plate: str | None = Field(default=None, min_length=1, max_length=20)
    vehicle_class_id: int | None = Field(default=None, ge=1, le=2147483647)

    @field_validator("plate")
    @classmethod
    def _strip_and_require_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _clean_plate(value)


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_class_id: int
    plate: str
