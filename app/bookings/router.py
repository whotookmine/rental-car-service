"""Bookings. Creation is nested under the provider a booking is made with."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.auth.dependencies import get_current_user, require_registered_user
from app.auth.models import User
from app.bookings.dependencies import get_own_booking_or_404
from app.bookings.models import Booking
from app.bookings.rules import ensure_room_for_another_booking
from app.bookings.schemas import BookingCreate, BookingRead, BookingUpdate
from app.core.clock import today
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
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
    responses={
        403: {"description": "Admins do not hold bookings."},
        404: {"description": "Provider not found."},
        409: {"description": "The user already holds the maximum active bookings."},
    },
)
def create_booking(
    payload: BookingCreate,
    current_user: User = Depends(require_registered_user),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> BookingRead:
    ensure_room_for_another_booking(db, current_user.id)

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


@router.get(
    "/bookings",
    response_model=list[BookingRead],
    summary="List your own bookings",
    description=(
        "Returns the calling user's bookings, oldest rental period first. A user "
        "with no bookings receives an empty list."
    ),
)
def list_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BookingRead]:
    # Scoped to the caller in the query itself, so there is no way to widen it by
    # passing something. Ordered explicitly: without it PostgreSQL returns rows
    # in whatever order it likes, and that order changes between runs.
    bookings = db.scalars(
        select(Booking)
        .where(Booking.user_id == current_user.id)
        .order_by(Booking.start_date, Booking.id)
    ).unique()
    return [BookingRead.model_validate(b) for b in bookings]


@router.get(
    "/bookings/{booking_id}",
    response_model=BookingRead,
    summary="Fetch one of your own bookings",
    description=(
        "Answers 404 both for a booking that does not exist and for one belonging "
        "to another user, so that booking identifiers cannot be walked to measure "
        "how much other people are renting."
    ),
    responses={404: {"description": "Booking not found."}},
)
def get_booking(
    booking: Booking = Depends(get_own_booking_or_404),
) -> BookingRead:
    return BookingRead.model_validate(booking)


@router.put(
    "/bookings/{booking_id}",
    response_model=BookingRead,
    summary="Change the dates of one of your own bookings",
    description=(
        "Replaces the rental period. The same shape rules as creation apply — end "
        "on or after start, at most thirty days — but a start date in the past is "
        "allowed here, so a rental already underway can be extended. The provider "
        "cannot be changed: sending one is refused, not ignored."
    ),
    responses={
        404: {"description": "Booking not found."},
        409: {"description": "The owner already holds the maximum active bookings."},
    },
)
def update_booking(
    payload: BookingUpdate,
    booking: Booking = Depends(get_own_booking_or_404),
    db: Session = Depends(get_db),
) -> BookingRead:
    # Only re-check the cap when the edit would leave the booking active. A
    # booking that has ended and stays ended occupies no slot, so an owner at the
    # limit must still be able to correct its dates. The booking is excluded from
    # its own count, or an owner holding the maximum could never edit any of them.
    if payload.end_date >= today():
        ensure_room_for_another_booking(
            db, booking.user_id, excluding_booking_id=booking.id
        )

    booking.start_date = payload.start_date
    booking.end_date = payload.end_date
    db.commit()
    db.refresh(booking)

    return BookingRead.model_validate(booking)
