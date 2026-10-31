"""Request and response shapes for branches."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.providers.schemas import _TELEPHONE_PATTERN


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


def _require_content(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class BranchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=500)
    telephone: str = Field(min_length=1, max_length=40)

    @field_validator("name", "address")
    @classmethod
    def _strip_and_require_content(cls, value: str) -> str:
        return _require_content(value)

    @field_validator("telephone")
    @classmethod
    def _telephone_shape(cls, value: str) -> str:
        return _validate_telephone(value)


class BranchUpdate(BaseModel):
    """Only name, address, and telephone are editable.

    There is deliberately no `provider_id` here. A branch belongs to one provider
    for its whole life; leaving the field out is what enforces that.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    telephone: str | None = Field(default=None, min_length=1, max_length=40)

    @field_validator("name", "address")
    @classmethod
    def _strip_and_require_content(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_content(value)

    @field_validator("telephone")
    @classmethod
    def _telephone_shape(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_telephone(value)


class DeliveryRadiusSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kilometres: int = Field(ge=0)


class BranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    name: str
    address: str
    telephone: str
    delivery_radius_km: int | None
