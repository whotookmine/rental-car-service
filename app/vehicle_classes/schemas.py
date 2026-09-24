"""Request and response shapes for vehicle classes."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _require_content(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class VehicleClassCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)

    @field_validator("name", "description")
    @classmethod
    def _strip_and_require_content(cls, value: str) -> str:
        return _require_content(value)


class VehicleClassUpdate(BaseModel):
    """Only the name and the description are editable.

    There is deliberately no `provider_id` here. A class belongs to one provider
    for its whole life; leaving the field out is what enforces that, rather than
    accepting it and then refusing it.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("name", "description")
    @classmethod
    def _strip_and_require_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_content(value)


class VehicleClassRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    name: str
    description: str

    # How many cars sit in this class. Counted on read, never stored, for the
    # same reason a provider's average rating is: a stored count drifts the
    # moment a car is added or removed outside the one code path that maintains
    # it. This is the capacity ticket 26 enforces.
    vehicle_count: int = 0
