"""Application configuration, read once from the environment.

Every setting is required except those with a default below. A missing required
value raises at import time, so the service fails loudly at startup rather than
serving requests with a half-configured runtime.
"""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# RFC 7518 section 3.2, for HS256.
MIN_JWT_SECRET_KEY_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLAlchemy URL for PostgreSQL. Required; there is no default, because a
    # silent fallback to a local socket is how you end up migrating the wrong
    # database.
    database_url: str = Field(alias="DATABASE_URL")

    # Signing key for access tokens. Required. No token code exists yet; the
    # value is validated here so a deployment cannot start without one.
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")

    # Access token lifetime, in minutes.
    access_token_expire_minutes: int = Field(
        default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES", gt=0
    )

    # Timezone that defines the business day for every date rule.
    business_timezone: str = Field(default="Asia/Bangkok", alias="BUSINESS_TIMEZONE")

    # Environment name: local | development | production.
    env: str = Field(default="local", alias="ENV")

    @field_validator("database_url")
    @classmethod
    def _database_url_must_be_postgresql(cls, value: str) -> str:
        if not value.startswith("postgresql"):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL "
                "(e.g. postgresql+psycopg://user:pass@host:port/dbname)"
            )
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def _jwt_secret_key_must_be_strong_enough(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("JWT_SECRET_KEY must not be empty")
        # RFC 7518 section 3.2: an HMAC key should be at least as long as the
        # hash it feeds. A short signing key is brute-forceable, and forging a
        # token would then defeat every authorisation rule in the service.
        if len(value.encode("utf-8")) < MIN_JWT_SECRET_KEY_BYTES:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_KEY_BYTES} bytes long; "
                'generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return value

    @field_validator("business_timezone")
    @classmethod
    def _business_timezone_must_be_a_real_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"BUSINESS_TIMEZONE is not a known timezone: {value!r}") from exc
        return value

    @property
    def business_tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.business_timezone)


@lru_cache
def get_settings() -> Settings:
    """The single Settings instance. Cached so the environment is read once."""
    return Settings()  # type: ignore[call-arg]
