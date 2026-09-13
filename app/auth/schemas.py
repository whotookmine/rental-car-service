"""Request and response shapes for authentication."""

import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.auth.models import UserRole
from app.auth.security import MAX_PASSWORD_BYTES

# Loose on purpose: non-empty, digits with optional spaces, hyphens, and a
# leading plus. No country-specific rules.
_TELEPHONE_PATTERN = re.compile(r"^\+?[\d\s-]+$")


class UserCreate(BaseModel):
    # Unknown fields are rejected rather than ignored, so an attempt to set
    # "role": "admin" fails loudly instead of appearing to succeed.
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    telephone: str = Field(min_length=1, max_length=40)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("name", "telephone")
    @classmethod
    def _strip_and_require_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("telephone")
    @classmethod
    def _telephone_shape(cls, value: str) -> str:
        if not _TELEPHONE_PATTERN.match(value) or not any(c.isdigit() for c in value):
            raise ValueError(
                "must contain digits, and may also contain spaces, hyphens, "
                "and a leading plus"
            )
        return value

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def _password_within_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"must be at most {MAX_PASSWORD_BYTES} bytes long")
        return value


class UserRead(BaseModel):
    """A user as the API reports them. Carries no password material by construction."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    telephone: str
    email: str
    role: UserRole


class AuthResponse(BaseModel):
    """An issued access token and the user it belongs to."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
