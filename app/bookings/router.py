"""Bookings. Creation is nested under the provider a booking is made with."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.bookings.models import Booking
from app.bookings.schemas import BookingCreate, BookingRead
from app.db.session import get_db
from app.providers.models import Provider

router = APIRouter(tags=["bookings"])


@router.post(
    "/providers/{provider_id}/bookings",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Book a provider for a rental period",
    description=(
        "Creates a booking for the calling registered user. The provider is part "
        "of the path because a booking cannot exist without one, and it is fixed "
        "for the life of the booking."
    ),
    responses={404: {"description": "Provider not found."}},
)
def create_booking(
    provider_id: int,
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingRead:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found.",
        )

    booking = Booking(
        # From the token. A caller cannot book on someone else's behalf by
        # naming them, because the request has no say in who owns this.
        user_id=current_user.id,
        provider_id=provider.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return BookingRead.model_validate(booking)
