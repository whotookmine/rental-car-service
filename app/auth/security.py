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


# A real bcrypt digest of a value nobody knows, verified against when the email
# is unrecognised. Logging in with an unknown address then costs the same as
# logging in with a wrong password, so response time does not reveal which
# addresses are registered. It is a constant rather than computed at import
# because generating it costs about 200ms of startup.
_ABSENT_USER_HASH = "$2b$12$w3yXRASp.0ZVO29eSu3wbuy/9yhllEugCWVKLqMFxvZfPjmUK1PoW"


def hash_password(plain_password: str) -> str:
    """Return a bcrypt digest of the given password."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a password against a stored digest."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        # An over-long password or a malformed digest. Neither can match.
        return False


def spend_a_password_check() -> None:
    """Burn the cost of a password check when there is no user to check against."""
    verify_password("not-a-real-password", _ABSENT_USER_HASH)


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


def read_access_token(token: str) -> str:
    """Return the subject of a valid token.

    Raises `jwt.InvalidTokenError` (which covers expiry, a bad signature, and a
    malformed token) if the token cannot be trusted.
    """
    payload = jwt.decode(
        token,
        get_settings().jwt_secret_key,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "exp"]},
    )
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise jwt.InvalidTokenError("token carries no usable subject")
    return subject
