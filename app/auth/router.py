"""Registration. Login and logout arrive with their own ticket."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.schemas import AuthResponse, UserCreate, UserRead
from app.auth.security import create_access_token, hash_password
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


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
