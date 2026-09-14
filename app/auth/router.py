"""Registration, login, logout, and the caller's own identity."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.auth.schemas import (
    AuthResponse,
    LoginRequest,
    LogoutResponse,
    UserCreate,
    UserRead,
)
from app.auth.security import (
    create_access_token,
    hash_password,
    spend_a_password_check,
    verify_password,
)
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _bad_credentials() -> HTTPException:
    # One message for both a wrong password and an unknown address, so that
    # registered addresses cannot be discovered by probing.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register and receive an access token",
    responses={409: {"description": "That email address is already registered."}},
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> AuthResponse:
    user = User(
        name=payload.name,
        telephone=payload.telephone,
        email=payload.email,
        password_hash=hash_password(payload.password),
        # Set here, never from the request. There is no path through the API
        # that produces an admin.
        role=UserRole.user,
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint on email is the real guard: checking first and
        # then inserting would leave a race between the two statements.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email address is already registered.",
        ) from None

    db.refresh(user)
    token, expires_in = create_access_token(str(user.id))
    return AuthResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in and receive an access token",
    responses={401: {"description": "The email or password is wrong."}},
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email))

    if user is None:
        # Spend the same time a real password check would, so that an unknown
        # address cannot be told apart from a wrong password by how long the
        # refusal takes.
        spend_a_password_check()
        raise _bad_credentials()

    if not verify_password(payload.password, user.password_hash):
        raise _bad_credentials()

    token, expires_in = create_access_token(str(user.id))
    return AuthResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.model_validate(user),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Log out (client-side)",
    description=(
        "Succeeds and invalidates nothing server-side. Access tokens are "
        "stateless and stay valid until they expire, so logging out means the "
        "client discarding its token. This is deliberate, not an oversight: see "
        "the architecture decision on stateless tokens. The residual window is "
        "bounded by the token lifetime, which is why that lifetime is short."
    ),
)
def logout(current_user: User = Depends(get_current_user)) -> LogoutResponse:
    return LogoutResponse(
        message=(
            "Logged out. Discard your access token; it remains valid until it "
            "expires."
        )
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="The registered user the access token belongs to",
)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
