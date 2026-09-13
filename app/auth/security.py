"""Password hashing and access token issuance.

bcrypt is used directly rather than through passlib: passlib's last release was
2020 and its bcrypt backend breaks against bcrypt 5.x, which it probes for a
`__about__` attribute that no longer exists. Pinning an old bcrypt to keep
passlib working would mean freezing the password hashing library, which is the
last dependency worth freezing.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

ALGORITHM = "HS256"

# bcrypt refuses anything longer; it is a property of the algorithm, not a
# policy choice, so the schema rejects over-long passwords before they reach it.
MAX_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Return a bcrypt digest of the given password."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def create_access_token(subject: str) -> tuple[str, int]:
    """Issue an access token for a subject, returning it and its lifetime in seconds."""
    settings = get_settings()
    issued_at = datetime.now(tz=timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)

    token = jwt.encode(
        {"sub": subject, "iat": issued_at, "exp": expires_at},
        settings.jwt_secret_key,
        algorithm=ALGORITHM,
    )
    return token, settings.access_token_expire_minutes * 60
