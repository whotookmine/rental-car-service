"""Request and response shapes for providers."""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

_TELEPHONE_PATTERN = re.compile(r"^\+?[\d\s-]+$")


def _validate_telephone(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    if not _TELEPHONE_PATTERN.match(stripped) or not any(c.isdigit() for c in stripped):
        raise ValueError(
            "must contain digits, and may also contain spaces, hyphens, "
            "and a leading plus"
        )
    return stripped


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=500)
    telephone: str = Field(min_length=1, max_length=40)

    @field_validator("name", "address")
    @classmethod
    def _strip_and_require_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("telephone")
    @classmethod
    def _telephone_shape(cls, value: str) -> str:
        return _validate_telephone(value)


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    telephone: str | None = Field(default=None, min_length=1, max_length=40)

    @field_validator("name", "address")
    @classmethod
    def _strip_and_require_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("telephone")
    @classmethod
    def _telephone_shape(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_telephone(value)


class ProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    telephone: str
    is_retired: bool

    # Computed at read time by aggregation; never stored. None means no reviews yet,
    # which is distinct from a zero average that would imply the provider is terrible.
    average_rating: float | None = None
    review_count: int = 0


class AvailabilityRow(BaseModel):
    """One vehicle class's availability for a requested rental period."""

    vehicle_class_id: int
    name: str
    free_count: int
