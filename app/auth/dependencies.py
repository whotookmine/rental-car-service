"""The guard that identifies the caller.

Every protected endpoint depends on `get_current_user`. The caller's identity
comes from the access token and nowhere else: never from a request body, a query
parameter, or a header a client can choose the meaning of. That is what stops
one user acting as another simply by naming them.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.security import read_access_token
from app.db.session import get_db

# auto_error=False so that a missing Authorization header reaches us and becomes
# a 401. Left to itself, HTTPBearer answers a missing header with 403, which
# says "you may not" when the truth is "I do not know who you are".
bearer_scheme = HTTPBearer(auto_error=False, description="Bearer access token")


def _unauthenticated() -> HTTPException:
    # One message for every failure mode -- absent, malformed, expired, or
    # naming a user who no longer exists. Distinguishing them would tell an
    # attacker which of their guesses was closest.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the registered user the access token belongs to."""
    if credentials is None:
        raise _unauthenticated()

    try:
        subject = read_access_token(credentials.credentials)
        user_id = int(subject)
    except (jwt.InvalidTokenError, ValueError):
        raise _unauthenticated() from None

    user = db.get(User, user_id)
    if user is None:
        raise _unauthenticated()

    return user
